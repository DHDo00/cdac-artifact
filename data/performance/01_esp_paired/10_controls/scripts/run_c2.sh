#!/usr/bin/env bash
# run_c2.sh — 调用者策略反转：规则 caller 从 A 改为 B（对象/操作不变）。
# 期望：B→X 拒止；A→X（规则仍在）放行。动态 UID。
set -u
ADB=adb; S=0.0.0.0:6528
POLICY=/data/local/tmp/iguardctl_test
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
X_URI="$TREE/document/primary%3Aespafd_tree%2FX.bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../01_controls/results/C2"; mkdir -p "$OUT"
sh() { $ADB -s $S shell "$@"; }
snap() { python3 "$HERE/file_state.py" "$1" "$2" "$OUT"; }
AUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.espafdtest uid:' | sed 's/.*uid://' | tr -d '\r')
BUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.espafdtestb uid:' | sed 's/.*uid://' | tr -d '\r')
XINO=$($ADB -s $S shell 'stat -c %i /data/media/0/espafd_tree/X.bin' | tr -d '\r')
XDEV=$($ADB -s $S shell 'stat -c %d /data/media/0/espafd_tree/X.bin' | tr -d '\r')
DEVRAW=$(( ((XDEV>>8)<<20) + (XDEV&255) ))
echo "AUID=$AUID BUID=$BUID XINO=$XINO DEVRAW=$DEVRAW" | tee "$OUT/meta.txt"
sh "$POLICY add service_id=5 op_id=401 caller_uid=$BUID operation=openAssetFile ino=$XINO s_dev=$DEVRAW i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 decision=deny reason=c2_B_X_deny" | tee "$OUT/rule_add.txt"
snap "X.bin" "C2_S0_pre"
# B -> X (expect deny)
sh 'logcat -c; logcat -b kernel -c'
$ADB -s $S shell "am start -W -n com.demo.espafdtestb/.MainActivity --es action write --es mode w --es label c2_B --es content C2B-DENY-AAAAA -d $X_URI" >/dev/null 2>&1
sleep 2
$ADB -s $S shell 'run-as com.demo.espafdtestb cat files/c2_B.csv' > "$OUT/c2_B_app.csv" 2>/dev/null
sh 'logcat -b kernel -d | grep -E "service_id=5 op_id=401|real-enforce|decision action|decision-apply|enforce-plan" | tail -12' > "$OUT/c2_B_kernel.txt"
snap "X.bin" "C2_S1_after_B_deny"
# A -> X (expect allow while rule present)
sh 'logcat -c; logcat -b kernel -c'
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action write --es mode w --es label c2_A --es content C2A-ALLOW-AAAA -d $X_URI" >/dev/null 2>&1
sleep 2
$ADB -s $S shell 'run-as com.demo.espafdtest cat files/c2_A.csv' > "$OUT/c2_A_app.csv" 2>/dev/null
sh 'logcat -b kernel -d | grep -E "service_id=5 op_id=401|real-enforce|decision action|decision-apply|enforce-plan" | tail -12' > "$OUT/c2_A_kernel.txt"
snap "X.bin" "C2_S2_after_A_allow"
sh "$POLICY clear" | tee "$OUT/rule_clear.txt"
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action write --es mode w --es label c2_restore --es content 0123456789ABCD -d $X_URI" >/dev/null 2>&1
sleep 2
snap "X.bin" "C2_S3_after_restore"
echo "C2 done -> $OUT"
