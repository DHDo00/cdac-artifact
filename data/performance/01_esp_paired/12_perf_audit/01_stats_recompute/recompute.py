#!/usr/bin/env python3
"""Independent recomputation of 11_perf_paired_20261024 from RAW CSVs only.
Fixed quantile: R type-7 linear interpolation. Pair mapping from frozen protocol.
Outputs: per-boot stats, pair deltas, summary, pooled (labeled separately)."""
import csv, json, os
BASE = "cdac_esp_endpoint_validation_20261022/11_perf_paired_20261024/04_samples"
PROTO = {
 1: {"S0": "s0_p1_b1", "S1": "e_p1_b1_S1", "S2": "e_p1_b1_S2", "S3": "e_p1_b1_S3"},
 2: {"S0": "s0_p2_b2", "S1": "e_p2_b1_S1", "S2": "e_p2_b1_S2", "S3": "e_p2_b1_S3"},
 3: {"S0": "s0_p3_b3", "S1": "e_p3_b3_S1", "S2": "e_p3_b3_S2", "S3": "e_p3_b3_S3"},
 4: {"S0": "s0_p4_b4", "S1": "e_p4_b4_S1", "S2": "e_p4_b4_S2", "S3": "e_p4_b4_S3"},
}
def q(sorted_vals, p):
    n = len(sorted_vals)
    if n == 0: return None
    if n == 1: return sorted_vals[0]
    h = (n - 1) * p; lo = int(h); hi = min(lo+1, n-1); f = h-lo
    return sorted_vals[lo] + (sorted_vals[hi]-sorted_vals[lo]) * f
def load(batch):
    f = os.path.join(BASE, batch, batch + ".csv")
    rows = list(csv.DictReader(open(f)))
    valid = sorted(int(r["open_ns"]) for r in rows if r.get("result") == "WRITE_OK" and int(r.get("open_ns", 0)) > 0)
    invalid = [r for r in rows if r not in rows or True][:0]  # recompute below
    invalid = [r for r in rows if not (r.get("result") == "WRITE_OK" and int(r.get("open_ns", 0)) > 0)]
    return dict(batch=batch, n=len(valid), invalid=len(invalid), invalid_results=sorted({r.get('result') for r in invalid}),
                median=q(valid,.5), p25=q(valid,.25), p75=q(valid,.75), p95=q(valid,.95), min=valid[0] if valid else None, max=valid[-1] if valid else None, vals=valid)
out = []
out.append("== per-boot / per-state (type-7 quantiles, ns) ==")
boot = {}
for pi in sorted(PROTO):
    for st in ["S0","S1","S2","S3"]:
        s = load(PROTO[pi][st]); boot[(pi,st)] = s
        out.append(f"pair{pi} {st}: n={s['n']} invalid={s['invalid']} median={s['median']:.0f} p95={s['p95']:.0f} min={s['min']} max={s['max']}")
out.append("")
out.append("== pair deltas (enabled median - S0 median) ==")
rows=[]
for pi in sorted(PROTO):
    s0 = boot[(pi,"S0")]["median"]
    row={"pair":pi,"S0_median_ns":s0}
    out.append(f"pair{pi} S0 median={s0:.0f}")
    for st in ["S1","S2","S3"]:
        m = boot[(pi,st)]["median"]; d=m-s0; r=m/s0
        row[f"{st}_median_ns"]=m; row[f"{st}_delta_ns"]=d; row[f"{st}_ratio"]=r
        out.append(f"  {st}: median={m:.0f} delta={d:.0f}ns ratio={r:.4f}")
    rows.append(row)
out.append("")
out.append("== summary across pairs ==")
for st in ["S1","S2","S3"]:
    ds=[r[f"{st}_delta_ns"] for r in rows]; rs=[r[f"{st}_ratio"] for r in rows]; ms=[r[f"{st}_median_ns"] for r in rows]
    out.append(f"{st}: delta_mean={sum(ds)/len(ds):.0f} delta_range=[{min(ds):.0f},{max(ds):.0f}] "
               f"mean_of_pair_ratios={sum(rs)/len(rs):.4f} ratio_of_means={sum(ms)/len(ms)/(sum(r['S0_median_ns'] for r in rows)/len(rows)):.4f} "
               f"per_boot_medians={[f'{m:.0f}' for m in ms]}")
out.append("")
out.append("== pooled across boots (separate definition; NOT an independence claim) ==")
pool={}
for st in ["S0","S1","S2","S3"]:
    v=[]
    for pi in sorted(PROTO): v += boot[(pi,st)]["vals"]
    v.sort(); pool[st]=v
    out.append(f"{st}: n={len(v)} median={q(v,.5):.0f} p95={q(v,.95):.0f}")
out.append("")
out.append("== per-boot median summary vs pooled median (must not be conflated) ==")
for st in ["S0","S1","S2","S3"]:
    ms=[boot[(pi,st)]['median'] for pi in sorted(PROTO)]
    out.append(f"{st}: mean_of_per_boot_medians={sum(ms)/len(ms):.0f} pooled_median={q(pool[st],.5):.0f}")
text="\n".join(out)+"\n"
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"recompute_output.txt"),"w").write(text)
json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"pair_rows.json"),"w"), indent=1)
print(text)
