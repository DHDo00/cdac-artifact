#!/usr/bin/env bash
# run_c1.sh — 撤规恢复：A+X 规则拒止 -> clear -> A+X 恢复可用。动态 UID/ino。
set -u
ADB=adb; S=0.0.0.0:6528
POLICY=/data/local/tmp/iguardctl_test
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
X_URI="$TREE/document/primary%3Aespafd_tree%2FX.bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../01_controls/results/C1"; mkdir -p "$OUT"
sh() { $ADB -s $S shell "$@"; }
snap() { python3 "$HERE/file_state.py" "$1" "$2" "$OUT"; }
AUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.espafdtest uid:' | sed 's/.*uid://' | tr -d '\r')
XINO=$($ADB -s $S shell 'stat -c %i /data/media/0/espafd_tree/X.bin' | tr -d '\r')
XDEV=$($ADB -s $S shell 'stat -c %d /data/media/0/espafd_tree/X.bin' | tr -d '\r')
DEVRAW=$(( ((XDEV>>8)<<20) + (XDEV&255) ))
echo "AUID=$AUID XINO=$XINO XDEV=$XDEV DEVRAW=$DEVRAW" | tee "$OUT/meta.txt"
snap "X.bin" "C1_S0_pre"
sh "$POLICY add service_id=5 op_id=401 caller_uid=$AUID operation=openAssetFile ino=$XINO s_dev=$DEVRAW i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 decision=deny reason=c1_A_X_deny" | tee "$OUT/rule_add.txt"
sh 'logcat -c; logcat -b kernel -c'
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action write --es mode w --es label c1_deny --es content C1DENY-AAAAAAA -d $X_URI" >/dev/null 2>&1
sleep 2
$ADB -s $S shell 'run-as com.demo.espafdtest cat files/c1_deny.csv' > "$OUT/c1_deny_app.csv" 2>/dev/null
sh 'logcat -b kernel -d | grep -E "service_id=5 op_id=401|real-enforce|decision action|decision-apply|enforce-plan" | tail -12' > "$OUT/c1_deny_kernel.txt"
snap "X.bin" "C1_S1_after_deny"
sh "$POLICY clear" | tee "$OUT/rule_clear.txt"
sh 'cat /sys/kernel/debug/iguard/policy_dump' > "$OUT/policy_after_clear.txt"
sh 'logcat -c; logcat -b kernel -c'
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action write --es mode w --es label c1_recover --es content C1RECOVER-AAAA -d $X_URI" >/dev/null 2>&1
sleep 2
$ADB -s $S shell 'run-as com.demo.espafdtest cat files/c1_recover.csv' > "$OUT/c1_recover_app.csv" 2>/dev/null
sh 'logcat -b kernel -d | grep -E "service_id=5 op_id=401|real-enforce|decision action|decision-apply|enforce-plan" | tail -12' > "$OUT/c1_recover_kernel.txt"
snap "X.bin" "C1_S2_after_recover"
# restore X fixture
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action write --es mode w --es label c1_restore --es content 0123456789ABCD -d $X_URI" >/dev/null 2>&1
sleep 2
snap "X.bin" "C1_S3_after_restore"
echo "C1 done -> $OUT"
