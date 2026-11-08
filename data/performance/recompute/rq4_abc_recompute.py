#!/usr/bin/env python3
"""Offline recomputation for the historical SettingsProvider A/B/C + independent-denial D
experiment (cdac_rq4_prospective_performance_v2_20260807_101100).

Two layers:
 1) Replay of the FROZEN analysis script (04_analysis/ANALYSIS_SCRIPT.py), unmodified,
    in a temporary copy of the packaged tree; its regenerated CSVs are diffed against the
    packaged frozen outputs (PRIMARY_ESTIMATES_SUMMARY.csv, ARM_DESCRIPTIVE_STATISTICS.csv,
    BOOT_SPECIFIC_ESTIMATES.csv, DENIAL_LATENCY_STATISTICS.csv, EXCLUSIONS_AND_FAILURES.csv).
 2) An independent stdlib re-derivation from SCIENTIFIC_ROWS.csv of arm medians/IQRs,
    paired-block deltas, and D mean/P50/P95, cross-checked against the frozen values.
"""
import csv, filecmp, os, shutil, statistics, subprocess, sys, tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
ABC = PKG / "02_settingsprovider_abc"
OUT = HERE / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
FROZEN_ANALYSIS = ABC / "04_analysis"
lines = []

def q_type7(vals, p):
    n = len(vals)
    if n == 0:
        return None
    if n == 1:
        return vals[0]
    h = (n - 1) * p
    lo = int(h); hi = min(lo + 1, n - 1); frac = h - lo
    return vals[lo] + (vals[hi] - vals[lo]) * frac

# ---------- 1) frozen script replay in a temp copy ----------
lines.append("=== 1) replay of frozen 04_analysis/ANALYSIS_SCRIPT.py (unmodified) ===")
with tempfile.TemporaryDirectory(prefix="rq4_abc_replay_") as td:
    replay = Path(td) / "02_settingsprovider_abc"
    shutil.copytree(ABC, replay)
    for root, dirs, files in os.walk(replay):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o755)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)
    script = replay / "04_analysis" / "ANALYSIS_SCRIPT.py"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    lines.append(f"frozen script returncode={r.returncode}")
    if r.returncode != 0:
        lines.append("STDOUT:\n" + r.stdout[-2000:])
        lines.append("STDERR:\n" + r.stderr[-2000:])
    replay_analysis = replay / "04_analysis"
    for name in ["PRIMARY_ESTIMATES_SUMMARY.csv", "ARM_DESCRIPTIVE_STATISTICS.csv",
                 "BOOT_SPECIFIC_ESTIMATES.csv", "DENIAL_LATENCY_STATISTICS.csv",
                 "EXCLUSIONS_AND_FAILURES.csv", "PRIMARY_BLOCK_ESTIMATES.csv"]:
        frozen = FROZEN_ANALYSIS / name
        regen = replay_analysis / name
        if not frozen.exists() or not regen.exists():
            lines.append(f"{name}: frozen={frozen.exists()} regenerated={regen.exists()} -> SKIP_DIFF")
            continue
        same = filecmp.cmp(frozen, regen, shallow=False)
        lines.append(f"{name}: regenerated_bytes_equal_frozen={same}")
        if not same:
            fc = frozen.read_text(); rc = regen.read_text()
            for i, (a, b) in enumerate(zip(fc.splitlines(), rc.splitlines())):
                if a != b:
                    lines.append(f"  first diff line {i+1}: frozen={a[:160]!r} regen={b[:160]!r}")
                    break

# ---------- 2) independent stdlib re-derivation ----------
lines.append("")
lines.append("=== 2) independent re-derivation from SCIENTIFIC_ROWS.csv ===")
rows_by_boot = {}
for boot in ["02_boot_1", "03_boot_2"]:
    f = ABC / boot / "SCIENTIFIC_ROWS.csv"
    rrows = list(csv.DictReader(open(f)))
    rows_by_boot[boot] = rrows
    lines.append(f"{boot}: rows={len(rrows)} arms={dict(Counter(r['arm'] for r in rrows))} "
                 f"primary_eligible={dict(Counter(r['primary_eligible'] for r in rrows))} "
                 f"exclusions={dict(Counter(r['exclusion_reason'] for r in rrows))}")

def arm_latencies(boot_dirs, arm, eligible_only=True):
    out = []
    for b in boot_dirs:
        for r in rows_by_boot[b]:
            if r["arm"] == arm and (not eligible_only or r["primary_eligible"] == "yes"):
                out.append(int(r["latency_ns"]))
    return out

all_boots = ["02_boot_1", "03_boot_2"]
arm_stats = {}
for arm in ["A", "B", "C"]:
    vals = sorted(arm_latencies(all_boots, arm))
    med = q_type7(vals, 0.5)
    q25 = q_type7(vals, 0.25); q75 = q_type7(vals, 0.75)
    iqr = q75 - q25
    arm_stats[arm] = dict(n=len(vals), median=med, iqr=iqr, q25=q25, q75=q75)
    lines.append(f"arm {arm}: n={len(vals)} median={med/1e6:.6f} ms IQR={iqr/1e6:.6f} ms "
                 f"(q25={q25/1e6:.3f}, q75={q75/1e6:.3f})")

# paired block deltas: median of 5 per arm per (boot, block)
blocks = []
for b in all_boots:
    by_key = {}
    for r in rows_by_boot[b]:
        if r["arm"] in ("A", "B", "C") and r["primary_eligible"] == "yes":
            by_key.setdefault((r["block_id"], int(r["block_index"])), {}).setdefault(r["arm"], []).append(int(r["latency_ns"]))
    for (bid, bidx), arms in sorted(by_key.items(), key=lambda kv: kv[0][1]):
        med = {a: statistics.median(arms[a]) for a in ("A", "B", "C")}
        blocks.append((b, bid, med["A"], med["B"], med["C"]))
lines.append(f"complete paired A/B/C blocks: boot_1={sum(1 for x in blocks if x[0]=='02_boot_1')} "
             f"boot_2={sum(1 for x in blocks if x[0]=='03_boot_2')} total={len(blocks)}")
for name, fn in [("Delta_BA", lambda m: m[1] - m[0]),
                 ("Delta_CB", lambda m: m[2] - m[1]),
                 ("Delta_CA", lambda m: m[2] - m[0])]:
    deltas = [fn(x[2:]) for x in blocks]
    med = statistics.median(deltas)
    lines.append(f"pooled {name}: median_of_paired_block_differences={med:.1f} ns ({med/1e6:.6f} ms)")
    for b in all_boots:
        bd = [fn(x[2:]) for x in blocks if x[0] == b]
        lines.append(f"  {b}: n_blocks={len(bd)} median={statistics.median(bd):.1f} ns")

# independent denial D
dvals = sorted(arm_latencies(all_boots, "D"))
d_mean = statistics.fmean(dvals); d_p50 = q_type7(dvals, 0.5); d_p95 = q_type7(dvals, 0.95)
d_p99 = q_type7(dvals, 0.99)
lines.append(f"arm D (absolute denial latency): n={len(dvals)} mean={d_mean/1e6:.6f} ms "
             f"P50={d_p50/1e6:.6f} ms P95={d_p95/1e6:.6f} ms P99={d_p99/1e6:.6f} ms")

# warmup rows
warm = {}
for b in all_boots:
    rrows = list(csv.DictReader(open(ABC / b / "WARMUP_ROWS.csv")))
    warm[b] = rrows
    lines.append(f"{b} warmup rows={len(rrows)} arms={dict(Counter(r['arm'] for r in rrows))}")

# frozen anchor comparison
frozen_arm = list(csv.DictReader(open(FROZEN_ANALYSIS / "ARM_DESCRIPTIVE_STATISTICS.csv")))
lines.append("")
lines.append("=== frozen-vs-independent numeric comparison ===")
for arm in ["A", "B", "C"]:
    fr = [r for r in frozen_arm if r["scope"] == "pooled" and r["arm"] == arm][0]
    st = arm_stats[arm]
    lines.append(f"arm {arm}: frozen_median_ns={float(fr['median_ns']):.1f} independent={st['median']:.1f} "
                 f"match={abs(float(fr['median_ns'])-st['median']) < 1e-6}")
frozen_est = list(csv.DictReader(open(FROZEN_ANALYSIS / "PRIMARY_ESTIMATES_SUMMARY.csv")))
for row in frozen_est:
    if row["scope"] != "pooled":
        continue
    lines.append(f"{row['contrast']}: frozen_estimate_ns={float(row['estimate_ns']):.1f} "
                 f"ci=[{float(row['ci_low_ns']):.1f},{float(row['ci_high_ns']):.1f}] "
                 f"method={row['ci_method']} complete_blocks={row['complete_blocks']} reps={row['bootstrap_replicates']}")
frozen_den = list(csv.DictReader(open(FROZEN_ANALYSIS / "DENIAL_LATENCY_STATISTICS.csv")))
fr = [r for r in frozen_den if r["scope"] == "pooled"][0]
lines.append(f"D denial: frozen mean/P50/P95 = {float(fr['mean_ns'])/1e6:.3f}/{float(fr['median_P50_ns'])/1e6:.3f}/"
             f"{float(fr['P95_ns'])/1e6:.3f} ms; independent match mean={abs(float(fr['mean_ns'])-d_mean)<1e-6} "
             f"p50={abs(float(fr['median_P50_ns'])-d_p50)<1e-6} p95={abs(float(fr['P95_ns'])-d_p95)<1e-6}")
# IQR: no frozen IQR column exists; report independent values (anchor check only)
lines.append("IQR note: frozen archive has no IQR column; independent type-7 IQR computed above "
             "(anchor A/B/C 4.059/5.771/5.310 ms are rounded approximations).")

text = "\n".join(lines) + "\n"
(OUT / "rq4_abc_recompute.txt").write_text(text)
print(text)
