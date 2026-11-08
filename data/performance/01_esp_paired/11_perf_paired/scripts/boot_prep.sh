#!/usr/bin/env bash
# boot_prep.sh <side> — wait for boot_completed + settle (uptime>=180s), set
# framework logging_mode=quiet BEFORE first provider use on enabled, verify state.
set -u
ADB=adb; S=0.0.0.0:6528
SIDE=$1
sh() { $ADB -s $S shell "$@"; }
$ADB connect 0.0.0.0:6528 >/dev/null 2>&1 || true
if [ "$SIDE" = enabled ]; then
  sh 'setprop persist.debug.cdac.logging_mode quiet'
fi
for ((i=0;i<80;i++)); do
  bc=$(timeout 8 "$ADB" -s $S shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
  up=$(timeout 8 "$ADB" -s $S shell cat /proc/uptime 2>/dev/null | cut -d' ' -f1 | cut -d. -f1 | tr -d '\r' || true)
  if [ "$bc" = 1 ] && [ -n "$up" ] && [ "${up:-0}" -ge 180 ]; then
    echo "settled boot_completed=1 uptime=$up side=$SIDE"
    if [ "$SIDE" = enabled ]; then
      sh 'mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true; echo 0 > /sys/kernel/debug/iguard/verbose_audit'
      sh 'echo prep verbose_audit=$(cat /sys/kernel/debug/iguard/verbose_audit) logging_mode=$(getprop persist.debug.cdac.logging_mode) selinux=$(getenforce) iguard_ctl=$(test -c /dev/iguard_ctl && echo yes || echo no)'
    else
      sh 'echo prep selinux=$(getenforce) iguard_ctl=$(test -c /dev/iguard_ctl && echo yes || echo no)'
    fi
    exit 0
  fi
  sleep 5
done
echo "boot_prep timeout boot_completed=$bc uptime=$up" >&2
exit 1
