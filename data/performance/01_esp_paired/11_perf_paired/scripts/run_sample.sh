#!/usr/bin/env bash
# run_sample.sh <side:enabled|stripped> <S0|S1|S2|S3> <batch_label>
# One formal block: restore fixture, warmup 20 + record 200, pull CSV, record
# state flags / counters / framework-log probe. LOG_OFF for enabled states.
set -u
ADB=adb; S=0.0.0.0:6528
POLICY=/data/local/tmp/iguardctl_test
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
X_URI="$TREE/document/primary%3Aespafd_tree%2FX.bin"
SIDE=$1; STATE=$2; BATCH=$3
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../04_samples/$BATCH"; mkdir -p "$OUT"
sh() { $ADB -s $S shell "$@"; }
qc() { sh 'cat /sys/kernel/debug/iguard/quiet_counters' 2>/dev/null; }
AUID=""; XINO=""; XDEV=""; DEVRAW=""
if [ "$SIDE" = enabled ]; then
  AUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.espafdtest uid:' | sed 's/.*uid://' | tr -d '\r')
  XINO=$($ADB -s $S shell 'stat -c %i /data/media/0/espafd_tree/X.bin' | tr -d '\r')
  XDEV=$($ADB -s $S shell 'stat -c %d /data/media/0/espafd_tree/X.bin' | tr -d '\r')
  DEVRAW=$(( ((XDEV>>8)<<20) + (XDEV&255) ))
  sh 'mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true'
  sh 'echo 0 > /sys/kernel/debug/iguard/verbose_audit'
  case "$STATE" in
    S1) sh "$POLICY clear"; sh 'echo 1 > /sys/kernel/debug/iguard/ablate_disable_runtime; echo 1 > /sys/kernel/debug/iguard/ablate_disable_ctx'; RULE="clear_ablation";;
    S2) sh "$POLICY clear"; sh 'echo 0 > /sys/kernel/debug/iguard/ablate_disable_runtime; echo 0 > /sys/kernel/debug/iguard/ablate_disable_ctx'; RULE="clear";;
    S3) sh "$POLICY clear"; sh 'echo 0 > /sys/kernel/debug/iguard/ablate_disable_runtime; echo 0 > /sys/kernel/debug/iguard/ablate_disable_ctx'
         sh "$POLICY add service_id=5 op_id=401 caller_uid=$AUID operation=openAssetFile ino=$XINO s_dev=$DEVRAW i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 decision=deny reason=perf_A_X" > "$OUT/rule_add.txt"; RULE="deny_A_X";;
    *) echo "bad state"; exit 2;;
  esac
  sh 'cat /sys/kernel/debug/iguard/policy_dump' > "$OUT/policy_dump.txt" 2>/dev/null
  sh 'echo verbose_audit=$(cat /sys/kernel/debug/iguard/verbose_audit) runtime=$(cat /sys/kernel/debug/iguard/ablate_disable_runtime) ctx=$(cat /sys/kernel/debug/iguard/ablate_disable_ctx) logging_mode=$(getprop persist.debug.cdac.logging_mode)' > "$OUT/state_flags.txt"
else
  RULE="n/a_stripped"
  echo "verbose_audit=n/a runtime=n/a ctx=n/a logging_mode=n/a" > "$OUT/state_flags.txt"
fi
TUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.esptiming uid:' | sed 's/.*uid://' | tr -d '\r')
{
  echo "side=$SIDE state=$STATE batch=$BATCH started=$(date -Is)"
  echo "timing_uid=$TUID rule_target_uid=$AUID XINO=$XINO DEVRAW=$DEVRAW rule=$RULE"
} | tee "$OUT/meta.txt"
qc > "$OUT/qc_pre.txt" 2>/dev/null
# restore fixture (outside timing)
$ADB -s $S shell "am start -W -n com.demo.esptiming/.MainActivity --es action restore --es mode w --es label ${BATCH}_restore --es content 0123456789ABCD -d $X_URI" >/dev/null 2>&1
sleep 2
python3 "$HERE/file_state.py" "X.bin" "${BATCH}_S0_pre" "$OUT"
sh 'logcat -c; logcat -b kernel -c'
$ADB -s $S shell "am start -W -n com.demo.esptiming/.MainActivity --es action timed --es mode w --es state $STATE --es label $BATCH --es content 0123456789ABCD --ei warmup 20 --ei record 200 --es out ${BATCH}.csv -d $X_URI" >/dev/null 2>&1
sleep 6
python3 "$HERE/file_state.py" "X.bin" "${BATCH}_S1_post" "$OUT"
$ADB -s $S shell "cat /sdcard/Android/data/com.demo.esptiming/files/timing/${BATCH}.csv" > "$OUT/${BATCH}.csv"
sh 'logcat -b kernel -d | wc -l' > "$OUT/kernel_logcat_lines.txt"
sh 'logcat -d | grep -cE "CDAC_BINDER_ENTRY|CDAC_ENDPOINT_RESOLVE"' > "$OUT/fw_cdac_log_lines.txt"
qc > "$OUT/qc_post.txt" 2>/dev/null
if [ "$SIDE" = enabled ]; then
  sh "$POLICY clear" >/dev/null
  sh 'echo 0 > /sys/kernel/debug/iguard/ablate_disable_runtime; echo 0 > /sys/kernel/debug/iguard/ablate_disable_ctx'
fi
echo "sample $BATCH done rows=$(tail -n +2 "$OUT/${BATCH}.csv" | wc -l)"
