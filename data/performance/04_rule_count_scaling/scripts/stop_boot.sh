#!/usr/bin/env bash
# stop_boot.sh <runtime> — stop cvd-21 cleanly
set -euo pipefail
runtime="$1"
source_root="$(cat "$runtime/source-root.txt")"
host="$source_root/out/host/linux-x86"
env ANDROID_HOST_OUT="$host" CUTTLEFISH_CONFIG_FILE="$runtime/assembly/cuttlefish_config.json" \
  CUTTLEFISH_INSTANCE=21 "$host/bin/stop_cvd" || true
echo "stop_cvd rc=$? at $(date -Is)" >> "$runtime/stop.log"
