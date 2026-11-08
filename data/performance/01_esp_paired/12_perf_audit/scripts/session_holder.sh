#!/usr/bin/env bash
# session_holder.sh — keep the exec session alive AFTER the launch script exits,
# so the harness does not reap the instance's process group/session.
# Usage: session_holder.sh <launcher.sh> <runtime_dir> <attempt.log>
set -u
LAUNCHER="$1"; RUNTIME="$2"; ATTEMPT="$3"
bash "$LAUNCHER" "$RUNTIME" "$ATTEMPT"
rc=$?
echo "launcher_rc=$rc holder_started=$(date -Is)" >> "$ATTEMPT"
while :; do
  sleep 30
done
