#!/usr/bin/env python3
"""Offline recomputation of the ESP paired performance experiment (round 11/12).

Reads the packaged raw CSV blocks under
01_esp_paired/11_perf_paired/04_samples/ and reproduces:
 - per-boot per-state n / invalid / median / P95 (R type-7 linear interpolation)
 - pair-level S0-vs-S1/S2/S3 median deltas and ratios
 - cross-pair summary: mean of per-boot median deltas, min-max range,
   mean of per-pair ratios, ratio of means (sum medians ratio)
 - pooled (800-request) median / P95 per state, kept distinct from pair-level
 - same-boot LOG_ON/LOG_OFF diagnostic block medians and console-byte drop.

No new experiments are run; this is pure statistics over preserved CSVs.
"""
import csv, json, os, statistics, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
SAMPLES = PKG / "01_esp_paired" / "11_perf_paired" / "04_samples"
DIAG = PKG / "01_esp_paired" / "11_perf_paired" / "01_diag_sameboot"
OUT = HERE / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

def q_type7(sorted_vals, p):
    """R type-7 quantile: h=(n-1)*p; interpolate between floor/ceil ranks."""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return sorted_vals[0]
    h = (n - 1) * p
    lo = int(h)
    hi = min(lo + 1, n - 1)
    frac = h - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac

def load(batch):
    f = SAMPLES / batch / (batch + ".csv")
    if not f.exists():
        return None
    rows = list(csv.DictReader(open(f)))
    valid = [r for r in rows if r.get("result") == "WRITE_OK" and int(r.get("open_ns", 0)) > 0]
    invalid = [r for r in rows if r not in valid]
    vals = sorted(int(r["open_ns"]) for r in valid)
    return dict(batch=batch, n=len(valid), invalid=len(invalid),
                median=q_type7(vals, 0.5), p95=q_type7(vals, 0.95),
                p25=q_type7(vals, 0.25), p75=q_type7(vals, 0.75),
                min=vals[0] if vals else None, max=vals[-1] if vals else None,
                invalid_results=sorted({r.get("result") for r in invalid}))

batches = [
    "s0_p1_b1", "e_p1_b1_S1", "e_p1_b1_S2", "e_p1_b1_S3",
    "e_p2_b1_S3", "e_p2_b1_S1", "e_p2_b1_S2", "s0_p2_b2",
    "s0_p3_b3", "e_p3_b3_S2", "e_p3_b3_S3", "e_p3_b3_S1",
    "e_p4_b4_S1", "e_p4_b4_S3", "e_p4_b4_S2", "s0_p4_b4",
]
pairs = {1: {"s0": "s0_p1_b1", "en": {"S1": "e_p1_b1_S1", "S2": "e_p1_b1_S2", "S3": "e_p1_b1_S3"}},
         2: {"s0": "s0_p2_b2", "en": {"S1": "e_p2_b1_S1", "S2": "e_p2_b1_S2", "S3": "e_p2_b1_S3"}},
         3: {"s0": "s0_p3_b3", "en": {"S1": "e_p3_b3_S1", "S2": "e_p3_b3_S2", "S3": "e_p3_b3_S3"}},
         4: {"s0": "s0_p4_b4", "en": {"S1": "e_p4_b4_S1", "S2": "e_p4_b4_S2", "S3": "e_p4_b4_S3"}}}

stats = {b: load(b) for b in batches}
lines = []
lines.append("=== per-boot per-state (median/P95 = R type-7; ns) ===")
for b in batches:
    s = stats[b]
    if not s:
        lines.append(f"{b}: MISSING FILE")
        continue
    lines.append(f"{b:14s} n={s['n']} invalid={s['invalid']} median={s['median']:.0f} "
                 f"p25={s['p25']:.0f} p75={s['p75']:.0f} p95={s['p95']:.0f} "
                 f"min={s['min']} max={s['max']}")

lines.append("")
lines.append("=== pair-level deltas vs S0 (median abs ns; ratio) ===")
pair_rows = []
for pi in sorted(pairs):
    s0 = stats[pairs[pi]["s0"]]
    lines.append(f"pair{pi} S0 median={s0['median']:.0f} (n={s0['n']})")
    row = {"pair": pi, "s0_median": s0["median"]}
    for st in ["S1", "S2", "S3"]:
        s = stats[pairs[pi]["en"][st]]
        d = s["median"] - s0["median"]
        r = s["median"] / s0["median"]
        row[f"{st}_median"] = s["median"]
        row[f"{st}_delta_ns"] = d
        row[f"{st}_ratio"] = r
        lines.append(f"  {st}: median={s['median']:.0f} delta={d:.0f}ns ratio={r:.6f} (n={s['n']}, invalid={s['invalid']})")
    pair_rows.append(row)

lines.append("")
lines.append("=== cross-pair summary ===")
summary = {}
for st in ["S1", "S2", "S3"]:
    ds = [r[f"{st}_delta_ns"] for r in pair_rows]
    rs = [r[f"{st}_ratio"] for r in pair_rows]
    meds = [r[f"{st}_median"] for r in pair_rows]
    s0s = [r["s0_median"] for r in pair_rows]
    mean_d = sum(ds) / len(ds)
    mean_pair_ratio = sum(rs) / len(rs)
    ratio_of_means = sum(meds) / sum(s0s)
    summary[st] = dict(delta_mean_ns=mean_d, delta_min_ns=min(ds), delta_max_ns=max(ds),
                       mean_of_pair_ratios=mean_pair_ratio, ratio_of_means=ratio_of_means,
                       per_boot_medians=meds)
    lines.append(f"{st}: per-boot medians={[f'{m:.0f}' for m in meds]}")
    lines.append(f"     delta_mean={mean_d:.0f}ns ({mean_d/1e6:.6f} ms) delta_min={min(ds):.0f} delta_max={max(ds):.0f} "
                 f"range_ms=[{min(ds)/1e6:.3f},{max(ds)/1e6:.3f}]")
    lines.append(f"     mean_of_pair_ratios={mean_pair_ratio:.6f} ratio_of_means={ratio_of_means:.6f}")

lines.append("")
lines.append("=== pooled (4 boots merged; NOT 800-request independence) ===")
pooled = {st: [] for st in ["S0", "S1", "S2", "S3"]}
for pi in sorted(pairs):
    for st in ["S1", "S2", "S3"]:
        f = SAMPLES / pairs[pi]["en"][st] / (pairs[pi]["en"][st] + ".csv")
        pooled[st].extend(int(r["open_ns"]) for r in csv.DictReader(open(f)) if r.get("result") == "WRITE_OK")
    f = SAMPLES / pairs[pi]["s0"] / (pairs[pi]["s0"] + ".csv")
    pooled["S0"].extend(int(r["open_ns"]) for r in csv.DictReader(open(f)) if r.get("result") == "WRITE_OK")
pooled_stats = {}
for st in ["S0", "S1", "S2", "S3"]:
    v = sorted(pooled[st])
    med = q_type7(v, 0.5); p95 = q_type7(v, 0.95)
    pooled_stats[st] = dict(n=len(v), median=med, p95=p95)
    lines.append(f"{st}: n={len(v)} median={med:.0f} ({med/1e6:.6f} ms) p95={p95:.0f} ({p95/1e6:.6f} ms)")
# mean of per-boot medians (to keep distinct from pooled median)
lines.append("")
lines.append("=== mean of per-boot medians vs pooled median (kept distinct) ===")
for st, names in [("S0", [pairs[p]["s0"] for p in pairs]),
                  ("S1", [pairs[p]["en"]["S1"] for p in pairs]),
                  ("S2", [pairs[p]["en"]["S2"] for p in pairs]),
                  ("S3", [pairs[p]["en"]["S3"] for p in pairs])]:
    mbm = statistics.mean([stats[n]["median"] for n in names])
    lines.append(f"{st}: mean_of_per_boot_medians={mbm:.0f} pooled_median={pooled_stats[st]['median']:.0f}")

# diagnostic LOG_ON/LOG_OFF blocks (same boot, S2, 30 rows per block)
lines.append("")
lines.append("=== same-boot LOG_ON/LOG_OFF diagnostic (4 blocks x 30 rows; medians in ns) ===")
diag_med = {}
for b in ["d1_on", "d1_off", "d2_off", "d2_on"]:
    f = DIAG / (b + ".csv")
    rows = list(csv.DictReader(open(f)))
    vals = sorted(int(r["open_ns"]) for r in rows if r.get("result") == "WRITE_OK")
    med = q_type7(vals, 0.5)
    diag_med[b] = med
    lines.append(f"{b}: n={len(rows)} median={med:.0f} ({med/1e6:.3f} ms)")
on_meds = [diag_med["d1_on"], diag_med["d2_on"]]
off_meds = [diag_med["d1_off"], diag_med["d2_off"]]
lines.append(f"LOG_ON block medians: {on_meds[0]/1e6:.3f}-{on_meds[1]/1e6:.3f} ms")
lines.append(f"LOG_OFF block medians: {off_meds[0]/1e6:.3f}-{off_meds[1]/1e6:.3f} ms")
def count_int(path, key):
    for ln in open(path):
        if ln.startswith(key + "="):
            return int(ln.split("=", 1)[1].strip())
    return None
on_kb = [count_int(DIAG / "d1_on_counts.txt", "host_kernel_log_bytes_delta"),
         count_int(DIAG / "d2_on_counts.txt", "host_kernel_log_bytes_delta")]
off_kb = [count_int(DIAG / "d1_off_counts.txt", "host_kernel_log_bytes_delta"),
          count_int(DIAG / "d2_off_counts.txt", "host_kernel_log_bytes_delta")]
lines.append(f"LOG_ON host kernel.log byte delta/30 req: {on_kb}")
lines.append(f"LOG_OFF host kernel.log byte delta/30 req: {off_kb}")
for i in range(2):
    red = 100.0 * (1 - off_kb[i] / on_kb[i])
    lines.append(f"  block{i+1}: console byte reduction = {red:.2f}%")

text = "\n".join(lines) + "\n"
(OUT / "esp_recompute.txt").write_text(text)
print(text)

# compare with frozen round-11 analysis.txt
frozen = PKG / "01_esp_paired" / "11_perf_paired" / "05_stats" / "analysis.txt"
checks = []
# anchors expressed as (label, frozen_string_fragment)
anchors = [
    ("S2 delta_mean", "delta_mean=2724800ns"),
    ("S3 delta_mean", "delta_mean=2262454ns"),
    ("S2 ratio_mean", "ratio_mean=1.916"),
    ("S3 ratio_mean", "ratio_mean=1.756"),
    ("pooled S0 median", "S0: n=800 median=3045218"),
    ("pooled S1 median", "S1: n=800 median=6237511"),
    ("pooled S2 median", "S2: n=800 median=5735940"),
    ("pooled S3 median", "S3: n=800 median=5385918"),
    ("pooled S0 p95", "p95=10819647"),
    ("pooled S1 p95", "p95=13423468"),
    ("pooled S2 p95", "p95=14028540"),
    ("pooled S3 p95", "p95=14614968"),
]
frozen_txt = frozen.read_text() if frozen.exists() else ""
cmp_lines = ["=== comparison vs frozen 11_perf 05_stats/analysis.txt ==="]
for label, frag in anchors:
    cmp_lines.append(f"{label}: frozen_has={frag in frozen_txt} recomputed={'yes'}")
cmp_text = "\n".join(cmp_lines) + "\n"
(OUT / "esp_compare_frozen.txt").write_text(cmp_text)
print(cmp_text)

# machine-readable outputs
with open(OUT / "esp_per_boot_stats.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["batch","n","invalid","median_ns","p25_ns","p75_ns","p95_ns","min_ns","max_ns"])
    for b in batches:
        s = stats[b]; w.writerow([b, s["n"], s["invalid"], round(s["median"]), round(s["p25"]), round(s["p75"]), round(s["p95"]), s["min"], s["max"]])
with open(OUT / "esp_pair_deltas.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["pair","state","s0_median_ns","state_median_ns","delta_ns","ratio"])
    for r in pair_rows:
        for st in ["S1","S2","S3"]:
            w.writerow([r["pair"], st, r["s0_median"], r[f"{st}_median"], r[f"{st}_delta_ns"], round(r[f"{st}_ratio"],6)])
with open(OUT / "esp_summary.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["state","delta_mean_ns","delta_min_ns","delta_max_ns","mean_of_pair_ratios","ratio_of_means"])
    for st in ["S1","S2","S3"]:
        x = summary[st]; w.writerow([st, round(x["delta_mean_ns"]), round(x["delta_min_ns"]), round(x["delta_max_ns"]), round(x["mean_of_pair_ratios"],6), round(x["ratio_of_means"],6)])
with open(OUT / "esp_pooled.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["state","n","median_ns","median_ms","p95_ns","p95_ms"])
    for st in ["S0","S1","S2","S3"]:
        x = pooled_stats[st]; w.writerow([st, x["n"], round(x["median"]), round(x["median"]/1e6,6), round(x["p95"]), round(x["p95"]/1e6,6)])
print("wrote outputs/esp_*.csv + esp_recompute.txt")
