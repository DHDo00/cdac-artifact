#!/usr/bin/env python3
"""Offline recomputation for round-21 rule-count scaling latency (N in {0,1,8,32,128}).

Replicates the frozen 07_analysis/analyze.py logic over the packaged 06_perf_raw CSVs:
 - valid WRITE_OK rows whose ino matches boot_cfg.json X (target object)
 - per-scale n/median/P95/min/max (type-7)
 - within-block paired T(N)-T(0) block-median differences (disturbed / config-invalid excluded)
 - bootstrap CI of the mean difference (random.Random(20261026), 10000 resamples, percentile [250,9750])
and compares against the frozen analysis.json / analysis.txt. No new experiment.
"""
import csv, json, math, random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
R21 = PKG / "04_rule_count_scaling"
PERF = R21 / "06_perf_raw"
OUT = HERE / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
SCALES = [0, 1, 8, 32, 128]
lines = []

def type7(sorted_vals, p):
    n = len(sorted_vals)
    if n == 0:
        return float("nan")
    if n == 1:
        return sorted_vals[0]
    h = (n - 1) * p
    lo = math.floor(h); hi = math.ceil(h)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] * (hi - h) + sorted_vals[hi] * (h - lo)

def load(boot):
    cfg = json.loads((R21 / "04_runtime" / f"boot{boot}" / "boot_cfg.json").read_text())
    X_ino = str(cfg["X"])
    rows = defaultdict(list)
    block_rows = {}
    meta = {}
    for f in sorted((PERF / f"boot{boot}").glob("boot*_N*.csv")):
        parts = f.name.split("_")
        b_idx = int(parts[1][1:])
        scale = int(parts[2][1:].split(".")[0])
        mfile = f.with_name(f"boot{boot}_b{b_idx:02d}_N{scale}") / "meta.json"
        try:
            m = json.loads(mfile.read_text())
        except Exception:
            m = {}
        meta[(b_idx, scale)] = m
        data = list(csv.DictReader(open(f)))
        ok = [float(r["open_ns"]) for r in data
              if r.get("result") == "WRITE_OK" and r.get("open_ns", "").lstrip("-").isdigit()
              and float(r["open_ns"]) >= 0 and r.get("ino") == X_ino]
        bad = [r for r in data if r.get("result") != "WRITE_OK" or r.get("ino") != X_ino]
        block_rows[(b_idx, scale)] = {"ok": ok, "bad": bad, "meta": m}
        rows[scale].extend(ok)
    return rows, block_rows, meta

def boot_summary(boot):
    rows, block_rows, meta = load(boot)
    out = {"boot": boot, "per_scale": {}}
    for s in SCALES:
        v = sorted(rows.get(s, []))
        out["per_scale"][str(s)] = dict(n=len(v), median=type7(v, 0.5), p95=type7(v, 0.95),
                                        min=v[0] if v else None, max=v[-1] if v else None)
    diffs = defaultdict(list)
    disturbed = set(); invalid = set()
    for b in range(1, 21):
        meta0 = meta.get((b, 0), {})
        if meta0.get("disturbed"):
            disturbed.add(b); continue
        if meta0.get("config_verified") is False:
            invalid.add((b, 0)); continue
        base = block_rows.get((b, 0), {}).get("ok", [])
        if not base:
            continue
        base_med = type7(sorted(base), 0.5)
        for s in SCALES:
            if s == 0:
                continue
            m = meta.get((b, s), {})
            if m.get("disturbed"):
                disturbed.add(b); continue
            if m.get("config_verified") is False:
                invalid.add((b, s)); continue
            ok = block_rows.get((b, s), {}).get("ok", [])
            if ok:
                diffs[s].append(type7(sorted(ok), 0.5) - base_med)
    out["paired"] = {}
    for s in SCALES:
        if s == 0:
            continue
        d = sorted(diffs[s]); n = len(d)
        ci = None
        if n >= 2:
            rng = random.Random(20261026)
            boots = [sum(rng.choice(d) for _ in range(n)) / n for _ in range(10000)]
            boots.sort(); ci = [boots[250], boots[9750]]
        out["paired"][str(s)] = dict(n=n, median=type7(d, 0.5), p95=type7(d, 0.95),
                                     min=d[0] if d else None, max=d[-1] if d else None,
                                     mean=sum(d)/n if n else None, bootstrap_mean_ci=ci)
    out["excluded"] = dict(disturbed_blocks=sorted(disturbed), invalid_configs=sorted(invalid))
    return out

b1 = boot_summary("1"); b2 = boot_summary("2")
frozen = json.loads((R21 / "07_analysis" / "analysis.json").read_text())

def approx(a, b, tol=1e-6):
    if a is None or b is None:
        return a == b
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))

lines.append("=== round-21 rule-count recomputation vs frozen analysis.json ===")
for boot, fresh in [("boot1", b1), ("boot2", b2)]:
    lines.append(f"--- {boot} ---")
    for s in SCALES:
        fs = frozen[boot]["per_scale"][str(s)]; ns = fresh["per_scale"][str(s)]
        lines.append(f"N={s}: n frozen={fs['n']} fresh={ns['n']} match={fs['n']==ns['n']}; "
                     f"median frozen={fs['median']} fresh={ns['median']} match={approx(fs['median'],ns['median'])}; "
                     f"p95 match={approx(fs['p95'],ns['p95'])}")
    for s in SCALES:
        if s == 0:
            continue
        fp = frozen[boot]["paired"][str(s)]; np_ = fresh["paired"][str(s)]
        lines.append(f"N={s}: n_blocks frozen={fp['n']} fresh={np_['n']} match={fp['n']==np_['n']}; "
                     f"median_delta_ms frozen={fp['median']/1e6:.4f} fresh={np_['median']/1e6:.4f} match={approx(fp['median'],np_['median'])}; "
                     f"bootstrap_mean_CI frozen={fp['bootstrap_mean_ci']} fresh={np_['bootstrap_mean_ci']} "
                     f"match={all(approx(a,b) for a,b in zip(fp['bootstrap_mean_ci'], np_['bootstrap_mean_ci']))}")
    lines.append(f"excluded frozen={frozen[boot]['excluded']} fresh={fresh['excluded']} match={frozen[boot]['excluded']==fresh['excluded']}")

# per-boot medians in ms for the paper's -3.34..+2.25 ms range
lines.append("")
lines.append("=== per-boot median of T(N)-T(0) block diffs (ms) ===")
for boot, fresh in [("boot1", b1), ("boot2", b2)]:
    vals = [fresh["paired"][str(s)]["median"]/1e6 for s in [1,8,32,128]]
    lines.append(f"{boot}: N=1,8,32,128 -> {[f'{v:.4f}' for v in vals]} ms (min={min(vals):.4f} max={max(vals):.4f})")

text = "\n".join(lines) + "\n"
(OUT / "rulecount_recompute.txt").write_text(text)
print(text)
