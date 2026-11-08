#!/usr/bin/env python3
"""Perf pilot analysis: per-boot/per-state stats, fixed quantile (R type-7),
pair-level deltas vs S0, pooled vs per-boot P95 (kept separate)."""
import csv, json, glob, os
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAMPLES = os.path.join(ROOT, "04_samples")

def quantile(sorted_vals, p):
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
    f = os.path.join(SAMPLES, batch, batch + ".csv")
    if not os.path.exists(f):
        return None
    rows = list(csv.DictReader(open(f)))
    valid = [r for r in rows if r.get("result") == "WRITE_OK" and int(r.get("open_ns", 0)) > 0]
    invalid = [r for r in rows if r not in valid]
    vals = sorted(int(r["open_ns"]) for r in valid)
    return dict(batch=batch, n=len(valid), invalid=len(invalid),
                invalid_results=sorted({r.get("result") for r in invalid}),
                median=quantile(vals, 0.5), p95=quantile(vals, 0.95),
                p25=quantile(vals, 0.25), p75=quantile(vals, 0.75),
                min=vals[0] if vals else None, max=vals[-1] if vals else None)

# expected formal batches (valid ones only)
batches = [
    "s0_p1_b1", "e_p1_b1_S1", "e_p1_b1_S2", "e_p1_b1_S3",
    "e_p2_b1_S3", "e_p2_b1_S1", "e_p2_b1_S2", "s0_p2_b2",
    "s0_p3_b3", "e_p3_b3_S2", "e_p3_b3_S3", "e_p3_b3_S1",
    "e_p4_b4_S1", "e_p4_b4_S3", "e_p4_b4_S2", "s0_p4_b4",
]
stats = {}
for b in batches:
    s = load(b)
    if s:
        stats[b] = s

# map to pairs
pairs = {1: {"s0": "s0_p1_b1", "en": {"S1": "e_p1_b1_S1", "S2": "e_p1_b1_S2", "S3": "e_p1_b1_S3"}},
         2: {"s0": "s0_p2_b2", "en": {"S1": "e_p2_b1_S1", "S2": "e_p2_b1_S2", "S3": "e_p2_b1_S3"}},
         3: {"s0": "s0_p3_b3", "en": {"S1": "e_p3_b3_S1", "S2": "e_p3_b3_S2", "S3": "e_p3_b3_S3"}},
         4: {"s0": "s0_p4_b4", "en": {"S1": "e_p4_b4_S1", "S2": "e_p4_b4_S2", "S3": "e_p4_b4_S3"}}}

report = {}
lines = []
lines.append("== per-boot per-state (median/P95 = type-7 interpolation; ns) ==")
for b in batches:
    s = stats[b]
    if not s:
        continue
    lines.append(f"{b:14s} n={s['n']} invalid={s['invalid']} median={s['median']:.0f} "
                 f"p25={s['p25']:.0f} p75={s['p75']:.0f} p95={s['p95']:.0f} "
                 f"min={s['min']} max={s['max']}")

lines.append("")
lines.append("== pair-level deltas vs S0 (median absolute ns and ratio) ==")
pair_rows = []
for pi in sorted(pairs):
    s0 = stats[pairs[pi]["s0"]]
    row = {"pair": pi, "s0_median": s0["median"]}
    lines.append(f"pair{pi} S0 median={s0['median']:.0f} (n={s0['n']})")
    for st in ["S1", "S2", "S3"]:
        s = stats[pairs[pi]["en"][st]]
        d = s["median"] - s0["median"]
        r = s["median"] / s0["median"]
        row[f"{st}_median"] = s["median"]
        row[f"{st}_delta_ns"] = d
        row[f"{st}_ratio"] = r
        lines.append(f"  {st}: median={s['median']:.0f}  delta={d:.0f}ns  ratio={r:.3f}  (n={s['n']}, invalid={s['invalid']})")
    pair_rows.append(row)

lines.append("")
lines.append("== summary across pairs (pair-level deltas) ==")
for st in ["S1", "S2", "S3"]:
    ds = [r[f"{st}_delta_ns"] for r in pair_rows]
    rs = [r[f"{st}_ratio"] for r in pair_rows]
    meds = [r[f"{st}_median"] for r in pair_rows]
    lines.append(f"{st}: per-boot medians={[f'{m:.0f}' for m in meds]} "
                 f"delta_mean={sum(ds)/len(ds):.0f}ns delta_min={min(ds):.0f} delta_max={max(ds):.0f} "
                 f"ratio_mean={sum(rs)/len(rs):.3f}")

lines.append("")
lines.append("== pooled (all 4 boots merged, labeled separately; NOT a 800-request independence claim) ==")
pooled = defaultdict(list)
for pi in sorted(pairs):
    for st in ["S1", "S2", "S3"]:
        rows = list(csv.DictReader(open(os.path.join(SAMPLES, pairs[pi]["en"][st], pairs[pi]["en"][st] + ".csv"))))
        pooled[st].extend(int(r["open_ns"]) for r in rows if r.get("result") == "WRITE_OK")
    rows0 = list(csv.DictReader(open(os.path.join(SAMPLES, pairs[pi]["s0"], pairs[pi]["s0"] + ".csv"))))
    pooled["S0"].extend(int(r["open_ns"]) for r in rows0 if r.get("result") == "WRITE_OK")
for st in ["S0", "S1", "S2", "S3"]:
    v = sorted(pooled[st])
    lines.append(f"{st}: n={len(v)} median={quantile(v,.5):.0f} p95={quantile(v,.95):.0f}")

out = os.path.join(ROOT, "05_stats", "analysis.txt")
open(out, "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
json.dump({k: {kk: vv for kk, vv in v.items()} for k, v in stats.items()},
          open(os.path.join(ROOT, "05_stats", "per_boot_stats.json"), "w"), indent=1)
json.dump(pair_rows, open(os.path.join(ROOT, "05_stats", "pair_rows.json"), "w"), indent=1)
print("\nwrote", out)
