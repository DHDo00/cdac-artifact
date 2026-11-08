#!/usr/bin/env bash
set -euo pipefail
[[ $# == 1 ]] || { echo "Usage: $0 /absolute/runtime/path" >&2; exit 2; }
runtime="$1"
[[ "$runtime" == /* && -f "$runtime/source-root.txt" ]] || exit 2
runtime="$(realpath -m -- "$runtime")"
source_root="$(cat "$runtime/source-root.txt")"
host="$source_root/out_matched_baseline/host/linux-x86"
env ANDROID_HOST_OUT="$host" CUTTLEFISH_CONFIG_FILE="$runtime/assembly/cuttlefish_config.json" \
  CUTTLEFISH_INSTANCE=9 "$host/bin/stop_cvd"
