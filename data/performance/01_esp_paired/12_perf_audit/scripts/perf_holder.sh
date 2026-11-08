#!/usr/bin/env bash
# perf_holder.sh <launcher> <side> <runtime> <attempt_log> <first_boot>
set -u
bash "$1" "$2" "$3" "$4" "$5"
rc=$?
echo "launcher_rc=$rc holder_started=$(date -Is)" >> "$4"
while :; do sleep 30; done
