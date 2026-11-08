#!/usr/bin/env bash
# Offline recomputation entry point. Runs everything against the PACKAGED data only.
# Does not start CVDs, does not build, does not modify any historical archive.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="$(dirname "$HERE")"
OUT="$HERE/outputs"
mkdir -p "$OUT"
echo "== [1/6] replay original round-11 analyze.py in a scratch copy =="
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -a "$PKG/01_esp_paired/11_perf_paired" "$TMP/11_perf_paired"
python3 "$TMP/11_perf_paired/05_stats/analyze.py" >/dev/null
diff -q "$TMP/11_perf_paired/05_stats/analysis.txt" \
     "$PKG/01_esp_paired/11_perf_paired/05_stats/analysis.txt" \
  && echo "analysis.txt: replayed bytes identical to frozen" \
  || echo "analysis.txt: DIFF (see outputs/esp_recompute.txt)"
diff -q "$TMP/11_perf_paired/05_stats/per_boot_stats.json" \
     "$PKG/01_esp_paired/11_perf_paired/05_stats/per_boot_stats.json" \
  && echo "per_boot_stats.json: replayed bytes identical" || true
diff -q "$TMP/11_perf_paired/05_stats/pair_rows.json" \
     "$PKG/01_esp_paired/11_perf_paired/05_stats/pair_rows.json" \
  && echo "pair_rows.json: replayed bytes identical" || true

echo "== [2/6] ESP paired + LOG diag recompute =="
python3 "$HERE/esp_recompute.py" | tail -30
echo "== [3/6] SettingsProvider A/B/C + D recompute (frozen script replay + independent) =="
python3 "$HERE/rq4_abc_recompute.py" | tail -40
echo "== [4/6] H4 DP recompute =="
python3 "$HERE/h4_recompute.py" | tail -25
echo "== [5/6] rule-count scaling recompute =="
python3 "$HERE/rulecount_recompute.py" | tail -14
echo "== [6/6] concurrency attribution ledger check =="
python3 "$HERE/concurrency_check.py" | tail -5
echo "== ALL DONE: see outputs/*.txt =="
