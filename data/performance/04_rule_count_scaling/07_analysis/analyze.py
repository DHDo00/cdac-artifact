#!/usr/bin/env python3
"""Frozen analysis for round-21 rule-count scaling (protocol §10)."""
import csv, json, math, sys
from collections import defaultdict
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
PERF = WS / "06_perf_raw"
CORR = WS / "05_correctness"
OUT = WS / "07_analysis"
OUT.mkdir(parents=True, exist_ok=True)
SCALES = [0, 1, 8, 32, 128]


def type7_quantile(sorted_vals, p):
    n = len(sorted_vals)
    if n == 0:
        return float("nan")
    if n == 1:
        return sorted_vals[0]
    h = (n - 1) * p
    lo = math.floor(h)
    hi = math.ceil(h)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] * (hi - h) + sorted_vals[hi] * (h - lo)


def load_perf_rows(boot):
    cfg = json.loads((WS / "04_runtime" / f"boot{boot}" /
                      "boot_cfg.json").read_text())
    X_ino = str(cfg["X"])
    rows = defaultdict(list)   # scale -> list of open_ns
    block_rows = {}            # (block, scale) -> [open_ns]
    meta = {}
    for f in sorted((PERF / f"boot{boot}").glob("boot*_N*.csv")):
        name = f.name
        parts = name.split("_")
        b = int(parts[0].replace("boot", ""))
        b_idx = int(parts[1][1:])
        scale = int(parts[2][1:].split(".")[0])
        mfile = f.with_name(f"boot{b}_b{b_idx:02d}_N{scale}") / "meta.json"
        try:
            m = json.loads(mfile.read_text())
        except Exception:
            m = {}
        meta[(b_idx, scale)] = m
        rows[scale]  # touch
        data = list(csv.DictReader(open(f)))
        ok = [float(r["open_ns"]) for r in data
              if r.get("result") == "WRITE_OK" and
              r.get("open_ns", "").lstrip("-").isdigit() and
              float(r["open_ns"]) >= 0 and r.get("ino") == X_ino]
        bad = [r for r in data if r.get("result") != "WRITE_OK"
               or r.get("ino") != X_ino]
        block_rows[(b_idx, scale)] = {"ok": ok, "bad": bad,
                                      "meta": m}
        rows[scale].extend(ok)
    return rows, block_rows, meta


def boot_summary(boot):
    rows, block_rows, meta = load_perf_rows(boot)
    out = {"boot": boot}
    out["per_scale"] = {}
    for s in SCALES:
        v = sorted(rows.get(s, []))
        out["per_scale"][s] = {
            "n": len(v), "median": type7_quantile(v, 0.5),
            "p95": type7_quantile(v, 0.95), "min": v[0] if v else None,
            "max": v[-1] if v else None}
    # paired diffs per block (exclude disturbed / config-invalid from primary)
    diffs = defaultdict(list)
    disturbed_blocks = set()
    invalid_cfg = set()
    for b in range(1, 21):
        meta0 = meta.get((b, 0), {})
        if meta0.get("disturbed"):
            disturbed_blocks.add(b)
            continue
        if meta0.get("config_verified") is False:
            invalid_cfg.add((b, 0))
            continue
        base = block_rows.get((b, 0), {}).get("ok", [])
        if not base:
            continue
        base_med = type7_quantile(sorted(base), 0.5)
        for s in SCALES:
            if s == 0:
                continue
            m = meta.get((b, s), {})
            if m.get("disturbed"):
                disturbed_blocks.add(b)
                continue
            if m.get("config_verified") is False:
                invalid_cfg.add((b, s))
                continue
            ok = block_rows.get((b, s), {}).get("ok", [])
            if ok:
                diffs[s].append(type7_quantile(sorted(ok), 0.5) - base_med)
    out["paired"] = {}
    for s in SCALES:
        if s == 0:
            continue
        d = sorted(diffs[s])
        n = len(d)
        boot_ci = None
        if n >= 2:
            rng = __import__("random").Random(20261026)
            boots = []
            for _ in range(10000):
                samp = [rng.choice(d) for _ in range(n)]
                boots.append(sum(samp) / n)
            boots.sort()
            boot_ci = [boots[250], boots[9750]]
        out["paired"][s] = {"n": n, "diffs": d,
                            "median": type7_quantile(d, 0.5),
                            "p95": type7_quantile(d, 0.95),
                            "min": d[0] if d else None,
                            "max": d[-1] if d else None,
                            "mean": sum(d) / n if n else None,
                            "bootstrap_mean_ci": boot_ci}
    out["excluded"] = {"disturbed_blocks": sorted(disturbed_blocks),
                       "invalid_configs": sorted(invalid_cfg)}
    out["block_raw"] = {}
    for key, val in block_rows.items():
        b, s = key
        out["block_raw"][f"b{b}_N{s}"] = {
            "n_ok": len(val["ok"]), "n_bad": len(val["bad"]),
            "median": type7_quantile(sorted(val["ok"]), 0.5)}
    return out


def main():
    b1 = boot_summary("1")
    b2 = boot_summary("2")
    report = []
    report.append("# CDAC round-21 rule-count scaling — analysis")
    for boot in (b1, b2):
        report.append(f"\n## boot{boot['boot']} per-scale (valid WRITE_OK rows, "
                      f"open_ns, type-7)")
        report.append("| N | n | median_ms | P95_ms | min_ms | max_ms |")
        report.append("|---|---|---|---|---|---|")
        for s in SCALES:
            p = boot["per_scale"][s]
            report.append(f"| {s} | {p['n']} | {p['median']/1e6:.4f} | "
                          f"{p['p95']/1e6:.4f} | {p['min']/1e6:.4f} | "
                          f"{p['max']/1e6:.4f} |")
        report.append(f"\n### boot{boot['boot']} paired per-block T(N)-T(0) "
                      f"(block median diff, ns->ms)")
        report.append("| N | n_blocks | median_ms | P95_ms | min_ms | max_ms | "
                      "bootstrap_mean_CI_ms |")
        report.append("|---|---|---|---|---|---|---|")
        for s in SCALES:
            if s == 0:
                continue
            p = boot["paired"][s]
            ci = p["bootstrap_mean_ci"]
            ci_s = (f"{ci[0]/1e6:.4f}..{ci[1]/1e6:.4f}" if ci else "n/a")
            report.append(f"| {s} | {p['n']} | {p['median']/1e6:.4f} | "
                          f"{p['p95']/1e6:.4f} | {p['min']/1e6:.4f} | "
                          f"{p['max']/1e6:.4f} | {ci_s} |")
        report.append(f"\nexcluded (boot{boot['boot']}): disturbed_blocks="
                      f"{boot['excluded']['disturbed_blocks']} "
                      f"invalid_configs={boot['excluded']['invalid_configs']}")
    report.append("\n## interpretation (frozen framing)")
    report.append("- N=0 = empty-rule reference on the SAME CDAC artifact; not a "
                  "no-CDAC baseline.")
    report.append("- end-to-end T(N)-T(0) is not pure kernel lookup cost.")
    report.append("- no splicing with round-12 old-artifact deltas.")
    report.append("- noise-dominated differences are reported as 'current "
                  "measurement did not resolve', never as zero cost.")
    (OUT / "analysis.txt").write_text("\n".join(report) + "\n")
    json.dump({"boot1": b1, "boot2": b2}, open(OUT / "analysis.json", "w"),
              indent=1)
    print("\n".join(report))


if __name__ == "__main__":
    main()
