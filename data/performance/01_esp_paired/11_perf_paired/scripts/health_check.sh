#!/usr/bin/env bash
# health_check.sh — consecutive health checks over the failure window.
# Usage: health_check.sh <runtime_dir> <n_checks> <interval_s> <out_log>
# Each check: adb device state, sys.boot_completed, guest uptime, kernel log
# advancing (non-blocking logcat), /dev/iguard_ctl present, SELinux enforcing.
set -u
RUNTIME="$1"; N="$2"; IV="$3"; OUT="$4"
ADB=adb; S=0.0.0.0:6528
mkdir -p "$(dirname "$OUT")"
: > "$OUT"
for ((i=1; i<=N; i++)); do
  TS=$(date +%H:%M:%S)
  "$ADB" connect 0.0.0.0:6528 >/dev/null 2>&1 || true
  BC=$("$ADB" -s $S shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
  UP=$(timeout 8 "$ADB" -s $S shell cat /proc/uptime 2>/dev/null | tr -d '\r' || true)
  DEV=$(timeout 8 "$ADB" -s $S shell 'test -c /dev/iguard_ctl && echo yes || echo no' 2>/dev/null | tr -d '\r' || true)
  SEL=$(timeout 8 "$ADB" -s $S shell getenforce 2>/dev/null | tr -d '\r' || true)
  KTAIL=$(timeout 8 "$ADB" -s $S shell 'logcat -b kernel -d -t 1' 2>/dev/null | head -1 | cut -c1-90 | tr -d '\r' || true)
  printf '%s check=%d boot_completed=%s uptime=%s iguard_ctl=%s selinux=%s kernel_adv=%s\n' \
    "$TS" "$i" "$BC" "${UP%% *}" "$DEV" "$SEL" "$KTAIL" >> "$OUT"
  sleep "$IV"
done
echo "health_checks_done n=$N" >> "$OUT"
cat "$OUT"
