#!/usr/bin/env bash
# Offline scope-binding recompute. Run from the package root:
#   bash recompute/run_all.sh
# Stdlib Python only. Reads ref_correction/originals + inputs_extra; never
# touches the historical archives or the paper.
set -u
PKG="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PKG" || exit 1
echo "== 1/3 scope recompute (corrected semantics + paper binding) =="
python3 recompute/recompute_scope.py || { echo "RECOMPUTE_FAIL"; exit 2; }
echo "== 2/3 derived tables =="
python3 recompute/build_deliverables.py || { echo "DELIVERABLES_FAIL"; exit 3; }
echo "== 3/3 self-checks =="
python3 recompute/checks_scope.py | tee outputs/CHECK_LOG.txt || { echo "CHECKS_FAIL"; exit 4; }
echo "RECOMPUTE_OK"
