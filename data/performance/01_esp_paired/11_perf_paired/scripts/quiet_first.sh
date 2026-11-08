#!/usr/bin/env bash
# quiet_first.sh — set framework logging_mode=quiet as early as possible after
# adb comes up, BEFORE installs/grants load provider processes.
set -u
ADB=adb; S=0.0.0.0:6528
for i in $(seq 1 60); do
  $ADB connect 0.0.0.0:6528 >/dev/null 2>&1 || true
  p=$(timeout 6 "$ADB" -s $S shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
  if [ -n "$p" ]; then
    $ADB -s $S shell 'setprop persist.debug.cdac.logging_mode quiet'
    echo "quiet_first set logging_mode=$( $ADB -s $S shell getprop persist.debug.cdac.logging_mode | tr -d '\r') boot_completed=$p"
    exit 0
  fi
  sleep 3
done
echo "quiet_first timeout"; exit 1
