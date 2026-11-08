#!/usr/bin/env bash
# Offline recomputation for round 39. Runs from the round directory (or an
# extracted copy) and derives summaries only from raw per-request material.
# Does not need any running instance or external archive.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "== gen_schedule reproducibility check =="
python3 recompute/gen_schedule.py /tmp/schedule_regen_$$.csv >/dev/null
sha_a=$(sha256sum SCHEDULE.csv | awk '{print $1}')
sha_b=$(sha256sum /tmp/schedule_regen_$$.csv | awk '{print $1}')
rm -f /tmp/schedule_regen_$$.csv
if [ "$sha_a" != "$sha_b" ]; then
  echo "SCHEDULE REGEN MISMATCH: $sha_a vs $sha_b" >&2
  exit 3
fi
echo "SCHEDULE regeneration identical: $sha_a"
echo "== analyze (verdicts re-derived from raw only) =="
python3 recompute/analyze.py --root "$ROOT"
echo "== pool ledgers =="
python3 recompute/pool_ledger.py --root "$ROOT"
echo "== recompute done =="
