#!/usr/bin/env bash
# run_timing_s0.sh <batch_label> — timing batch on the CDAC-stripped (S0) build.
# No iguardctl_test / no debugfs ablation on S0; identical workload otherwise.
set -u
ADB=adb; S=0.0.0.0:6528
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
X_URI="$TREE/document/primary%3Aespafd_tree%2FX.bin"
BATCH=$1
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../04_sampling/$BATCH"; mkdir -p "$OUT"
sh() { $ADB -s $S shell "$@"; }
TUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.esptiming uid:' | sed 's/.*uid://' | tr -d '\r')
{
  echo "state=S0 batch=$BATCH started=$(date -Is)"
  echo "timing_uid=$TUID build=stripped_CDAC_free"
} > "$OUT/meta.txt"
$ADB -s $S shell "am start -W -n com.demo.esptiming/.MainActivity --es action restore --es mode w --es label ${BATCH}_restore --es content 0123456789ABCD -d $X_URI" >/dev/null 2>&1
sleep 2
python3 "$HERE/file_state.py" "X.bin" "${BATCH}_S0_pre" "$OUT"
sh 'logcat -c; logcat -b kernel -c'
$ADB -s $S shell "am start -W -n com.demo.esptiming/.MainActivity --es action timed --es mode w --es state S0 --es label $BATCH --es content 0123456789ABCD --ei warmup 5 --ei record 20 --es out ${BATCH}.csv -d $X_URI" >/dev/null 2>&1
sleep 5
python3 "$HERE/file_state.py" "X.bin" "${BATCH}_S1_post" "$OUT"
$ADB -s $S shell "cat /sdcard/Android/data/com.demo.esptiming/files/timing/${BATCH}.csv" > "$OUT/${BATCH}.csv"
sh 'logcat -b kernel -d | grep -E "CDAC|iguard" | head -10' > "$OUT/${BATCH}_kernel_cdac_probe.txt"
sh 'logcat -d -s EspTiming:* | tail -6' > "$OUT/${BATCH}_applog.txt"
echo "state=S0 done -> $OUT (rows=$(wc -l < "$OUT/${BATCH}.csv"))"
