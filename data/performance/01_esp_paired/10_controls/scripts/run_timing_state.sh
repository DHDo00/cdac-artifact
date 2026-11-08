#!/usr/bin/env bash
# run_timing_state.sh <S1|S2|S3> <batch_label> — 5 warmup + 20 recorded legal
# requests through the ESP timing APK (com.demo.esptiming, uid dynamic).
# Fixture restore, rule install and CSV pull are all OUTSIDE the timed interval.
set -u
ADB=adb; S=0.0.0.0:6528
POLICY=/data/local/tmp/iguardctl_test
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
X_URI="$TREE/document/primary%3Aespafd_tree%2FX.bin"
STATE=$1; BATCH=$2
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../04_sampling/$BATCH"; mkdir -p "$OUT"
sh() { $ADB -s $S shell "$@"; }
AUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.espafdtest uid:' | sed 's/.*uid://' | tr -d '\r')
TUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.esptiming uid:' | sed 's/.*uid://' | tr -d '\r')
XINO=$($ADB -s $S shell 'stat -c %i /data/media/0/espafd_tree/X.bin' | tr -d '\r')
XDEV=$($ADB -s $S shell 'stat -c %d /data/media/0/espafd_tree/X.bin' | tr -d '\r')
DEVRAW=$(( ((XDEV>>8)<<20) + (XDEV&255) ))
sh 'mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true'
# state setup
case "$STATE" in
  S2) sh "$POLICY clear"; sh 'echo 0 > /sys/kernel/debug/iguard/ablate_disable_runtime; echo 0 > /sys/kernel/debug/iguard/ablate_disable_ctx'; RULE=clear ;;
  S3) sh "$POLICY clear"; sh 'echo 0 > /sys/kernel/debug/iguard/ablate_disable_runtime; echo 0 > /sys/kernel/debug/iguard/ablate_disable_ctx'
       sh "$POLICY add service_id=5 op_id=401 caller_uid=$AUID operation=openAssetFile ino=$XINO s_dev=$DEVRAW i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 decision=deny reason=timing_A_X" > "$OUT/rule_add.txt"; RULE=deny_A_X ;;
  S1) sh "$POLICY clear"; sh 'echo 1 > /sys/kernel/debug/iguard/ablate_disable_runtime; echo 1 > /sys/kernel/debug/iguard/ablate_disable_ctx'; RULE=clear_ablation ;;
  *) echo "unknown state $STATE"; exit 2 ;;
esac
sh 'cat /sys/kernel/debug/iguard/policy_dump' > "$OUT/policy_dump.txt"
sh 'echo runtime=$(cat /sys/kernel/debug/iguard/ablate_disable_runtime) ctx=$(cat /sys/kernel/debug/iguard/ablate_disable_ctx) verbose_audit=$(cat /sys/kernel/debug/iguard/verbose_audit)' > "$OUT/state_flags.txt"
{
  echo "state=$STATE batch=$BATCH started=$(date -Is)"
  echo "timing_uid=$TUID rule_target_uid=$AUID XINO=$XINO DEVRAW=$DEVRAW rule=$RULE"
} > "$OUT/meta.txt"
# restore X fixture to known 14-byte content (outside timing)
$ADB -s $S shell "am start -W -n com.demo.esptiming/.MainActivity --es action restore --es mode w --es label ${BATCH}_restore --es content 0123456789ABCD -d $X_URI" >/dev/null 2>&1
sleep 2
python3 "$HERE/file_state.py" "X.bin" "${BATCH}_S0_pre" "$OUT"
# timed batch: 5 warmup + 20 recorded
sh 'logcat -c; logcat -b kernel -c'
$ADB -s $S shell "am start -W -n com.demo.esptiming/.MainActivity --es action timed --es mode w --es state $STATE --es label $BATCH --es content 0123456789ABCD --ei warmup 5 --ei record 20 --es out ${BATCH}.csv -d $X_URI" >/dev/null 2>&1
sleep 5
python3 "$HERE/file_state.py" "X.bin" "${BATCH}_S1_post" "$OUT"
$ADB -s $S shell "cat /sdcard/Android/data/com.demo.esptiming/files/timing/${BATCH}.csv" > "$OUT/${BATCH}.csv"
sh 'logcat -b kernel -d | grep -E "service_id=5 op_id=401|real-enforce|decision action|perf|ablation" | tail -40' > "$OUT/${BATCH}_kernel.txt"
sh 'logcat -d -s EspTiming:* | tail -6' > "$OUT/${BATCH}_applog.txt"
sh 'cat /sys/kernel/debug/iguard/quiet_counters' > "$OUT/${BATCH}_quiet_counters.txt"
# cleanup rule/ablation after state
sh "$POLICY clear" >/dev/null
sh 'echo 0 > /sys/kernel/debug/iguard/ablate_disable_runtime; echo 0 > /sys/kernel/debug/iguard/ablate_disable_ctx'
echo "state=$STATE done -> $OUT (rows=$(wc -l < "$OUT/${BATCH}.csv"))"
