#!/usr/bin/env bash
# Compute the freeze-time SHA-256 manifest of all frozen inputs (run before sampling).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
{
  echo "# FREEZE_MANIFEST — freeze time: $(date -Is) (TZ Asia/Shanghai)"
  echo "# All scientific sampling starts AFTER these hashes are recorded."
  find 00_inputs 01_audit 02_source_semantics 04_protocol 05_fixtures 05_artifacts recompute \
       -type f ! -path '*/build/classes*' ! -path '*/build/dex*' ! -name '*.idsig' \
       ! -name 'base.apk' ! -name 'classes.dex' ! -name '*-unsigned.apk' | sort | \
    while IFS= read -r f; do printf '%s  %s\n' "$(sha256sum "$f" | awk '{print $1}')" "$f"; done
  for f in SCHEDULE.csv PROTOCOL.md BUILD_PROVENANCE.md 06_runtime/run_boot.py 06_runtime/launch_boot.sh 06_runtime/stop_boot.sh; do
    printf '%s  %s\n' "$(sha256sum "$f" | awk '{print $1}')" "$f"
  done
} > FREEZE_MANIFEST.txt
sha256sum FREEZE_MANIFEST.txt
