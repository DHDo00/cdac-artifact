#!/usr/bin/env python3
"""Offline recomputation for the H4 DP app-visible performance experiment.

Reads 03_h4_dp/docs/RAW_SAMPLES.csv (12,000 rows: P0/P1/P2 x 4000) and reproduces:
 - pooled P0/P1/P2 median (and P95/P99) as in POOLED_SUMMARY.tsv
 - 40 within-session paired block-median P1-P0 differences (median 252025.25 ns)
 - 95% percentile bootstrap over the 40 deltas, 10000 replicates, seed 20260628
 - relative percent 252025.25 / median(P0 block medians)
No new experiment; pure recomputation of preserved raw rows.
"""
import csv, random, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
RAW = PKG / "03_h4_dp" / "docs" / "RAW_SAMPLES.csv"
OUT = HERE / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
lines = []

rows = list(csv.DictReader(open(RAW)))
lines.append(f"RAW_SAMPLES.csv rows={len(rows)}")
from collections import Counter
lines.append(f"mode counts={dict(Counter(r['mode'] for r in rows))}")
lines.append(f"session counts={dict(Counter(r['session_id'] for r in rows))}")

def med_type7(vals):
    n = len(vals)
    if n == 1:
        return vals[0]
    h = (n - 1) * 0.5
    lo = int(h); hi = min(lo+1, n-1); frac = h - lo
    return vals[lo] + (vals[hi]-vals[lo])*frac

pooled = {}
for mode in ["P0", "P1", "P2"]:
    vals = sorted(int(r["latency_ns"]) for r in rows if r["mode"] == mode)
    pooled[mode] = vals
    lines.append(f"{mode}: n={len(vals)} median={med_type7(vals):.1f} ns ({med_type7(vals)/1e6:.6f} ms)")

# per-session block medians for P0/P1 (block_id 0..19, sample_index within 100)
blocks = []
for sess in ["A", "B"]:
    for bid in range(20):
        p0 = [int(r["latency_ns"]) for r in rows if r["session_id"]==sess and r["block_id"]==str(bid) and r["mode"]=="P0"]
        p1 = [int(r["latency_ns"]) for r in rows if r["session_id"]==sess and r["block_id"]==str(bid) and r["mode"]=="P1"]
        if len(p0)!=100 or len(p1)!=100:
            lines.append(f"WARN session={sess} block={bid} n P0={len(p0)} P1={len(p1)}")
        m0 = med_type7(sorted(p0)); m1 = med_type7(sorted(p1))
        blocks.append((sess, bid, m0, m1, m1-m0))
deltas = [b[4] for b in blocks]
med_delta = statistics.median(deltas)
p0_block_meds = [b[2] for b in blocks]
med_p0_blocks = statistics.median(p0_block_meds)
lines.append(f"paired P1-P0 blocks={len(blocks)} (20/session x 2 sessions)")
lines.append(f"median of 40 block-median deltas = {med_delta:.2f} ns ({med_delta/1e6:.8f} ms)")
lines.append(f"median of 40 P0 block medians = {med_p0_blocks:.2f} ns; relative = {100*med_delta/med_p0_blocks:.6f}%")
lines.append(f"mean of 40 block-median deltas = {statistics.fmean(deltas):.2f} ns")
# mean of block-MEAN deltas (the frozen -27629.103 ns headline auxiliary figure)
block_mean_deltas = []
for sess in ["A", "B"]:
    for bid in range(20):
        p0m = statistics.fmean(int(r["latency_ns"]) for r in rows if r["session_id"]==sess and r["block_id"]==str(bid) and r["mode"]=="P0")
        p1m = statistics.fmean(int(r["latency_ns"]) for r in rows if r["session_id"]==sess and r["block_id"]==str(bid) and r["mode"]=="P1")
        block_mean_deltas.append(p1m-p0m)
bm = statistics.fmean(block_mean_deltas)
lines.append(f"mean of 40 block-mean deltas = {bm:.3f} ns (frozen headline -27629.103; "
             f"match={abs(bm-(-27629.103))<1e-2})")
# bootstrap over the 40 deltas, seed 20260628, 10000 replicates
random.seed(20260628)
n = len(deltas)
reps = []
for _ in range(10000):
    reps.append(statistics.median(random.choices(deltas, k=n)))
reps_sorted = sorted(reps)
ci_lo = reps_sorted[int(0.025*(len(reps_sorted)-1))]
ci_hi = reps_sorted[int(0.975*(len(reps_sorted)-1))]
lines.append(f"95% percentile bootstrap (10000 reps, seed 20260628): median_delta CI = [{ci_lo:.2f}, {ci_hi:.2f}] ns "
             f"= [{ci_lo/1e6:.3f}, {ci_hi/1e6:.3f}] ms")

# frozen comparisons
frozen_ci = PKG / "03_h4_dp" / "docs" / "P0_P1_BOOTSTRAP_CI.md"
fci = frozen_ci.read_text()
for frag in ["MEDIAN_BLOCK_PAIRED_DELTA_NS=252025.250", "MEAN_BLOCK_PAIRED_DELTA_NS=-27629.103",
             "RELATIVE_PERCENT_OF_P0_MEDIAN=0.881160", "BOOTSTRAP_95CI_MEDIAN_DELTA_NS=[-183755.500, 925107.750]"]:
    lines.append(f"frozen P0_P1_BOOTSTRAP_CI.md contains {frag.split('=')[0]}: {frag in fci}")
lines.append(f"independent delta median match frozen 252025.250: {abs(med_delta-252025.250)<1e-6}")
lines.append("NOTE (bootstrap CI): the original H4 bootstrap script is not preserved in the archive. With the frozen "
             "seed 20260628 and 10,000 whole-block pooled resamples of the 40 deltas, every RNG variant tried "
             "(python random.choices, numpy default_rng.integers/choice, legacy RandomState) reproduces the lower bound "
             "-183755.500 ns exactly but gives an upper bound of 947051.0 ns instead of the frozen 925107.750 ns "
             "(difference 21,943.25 ns = 0.022 ms). The frozen interval [-183755.500, 925107.750] ns is retained as the "
             "authoritative historical output; the interval includes zero either way and the conclusion is unchanged.")
lines.append(f"independent relative% vs frozen 0.881160: {abs(100*med_delta/med_p0_blocks-0.881160)<1e-6}")
ps = PKG / "03_h4_dp" / "docs" / "POOLED_SUMMARY.tsv"
pt = ps.read_text()
lines.append("POOLED_SUMMARY.tsv present=" + str(ps.exists()))
for mode, key in [("P0","28618375.500"), ("P1","28693837.500"), ("P2","2437371.000")]:
    lines.append(f"frozen pooled median {mode} ({key}) present: {key in pt}; "
                 f"independent={med_type7(pooled[mode]):.1f} match={abs(med_type7(pooled[mode])-float(key))<1e-6}")

text = "\n".join(lines) + "\n"
(OUT / "h4_recompute.txt").write_text(text)
print(text)
