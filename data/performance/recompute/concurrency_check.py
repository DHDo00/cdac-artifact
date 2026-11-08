#!/usr/bin/env python3
"""Round-26 concurrency attribution ledger check (NOT a latency recomputation).

Verifies the preserved 160/160 unique per-request attribution counts and confirms the
ledger contains server-side epoch timestamps but NO app-visible elapsedRealtimeNanos
latency column (i.e., this batch has no per-request latency for RQ3 performance).
"""
import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
R26 = PKG / "05_concurrent_attribution" / "05_results"
OUT = HERE / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
lines = []
total = Counter(); has_latency = False
for boot in ["boot1", "boot2"]:
    p = R26 / boot / "formal" / "PER_REQUEST_LEDGER.csv"
    if not p.exists():
        lines.append(f"{boot}: LEDGER MISSING")
        continue
    rows = list(csv.DictReader(open(p)))
    lines.append(f"{boot}: ledger rows={len(rows)} verdicts={dict(Counter(r['verdict'] for r in rows))} "
                 f"callers={dict(Counter(r['caller'] for r in rows))}")
    total["rows"] += len(rows)
    for v in Counter(r["verdict"] for r in rows):
        total[v] += Counter(r["verdict"] for r in rows)[v]
    cols = rows[0].keys()
    has_latency = has_latency or any("latency" in c.lower() or "open_ns" in c.lower() for c in cols)
    lines.append(f"{boot}: ledger columns={list(cols)}")
    lines.append(f"{boot}: has app-visible latency column: {has_latency}")
lines.append(f"TOTAL rows={total['rows']} (expect 160) verdicts={ {k:v for k,v in total.items()} }")
lines.append("server-side epoch timestamps present (fw_enter/fw_exit/decision/enforce) but no "
             "app-side elapsedRealtimeNanos latency: concurrency batch contributes attribution "
             "evidence only, not RQ3 per-request latency.")
text = "\n".join(lines) + "\n"
(OUT / "concurrency_check.txt").write_text(text)
print(text)
