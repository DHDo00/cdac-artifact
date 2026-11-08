#!/usr/bin/env bash
# func_check_logoff.sh — minimal functionality check under the PERF log config
# (kernel verbose_audit=0; framework logging_mode=quiet). Security semantics must
# be unchanged; verification uses quiet_counters deltas + app results + policy_dump.
set -u
ADB=adb; S=0.0.0.0:6528
POLICY=/data/local/tmp/iguardctl_test
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
X_URI="$TREE/document/primary%3Aespafd_tree%2FX.bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../02_function_check"; mkdir -p "$OUT"
sh() { $ADB -s $S shell "$@"; }
qc() { sh 'cat /sys/kernel/debug/iguard/quiet_counters'; }
AUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.espafdtest uid:' | sed 's/.*uid://' | tr -d '\r')
BUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.espafdtestb uid:' | sed 's/.*uid://' | tr -d '\r')
XINO=$($ADB -s $S shell 'stat -c %i /data/media/0/espafd_tree/X.bin' | tr -d '\r')
XDEV=$($ADB -s $S shell 'stat -c %d /data/media/0/espafd_tree/X.bin' | tr -d '\r')
DEVRAW=$(( ((XDEV>>8)<<20) + (XDEV&255) ))
sh 'mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true'
sh 'echo 0 > /sys/kernel/debug/iguard/verbose_audit'
sh 'setprop persist.debug.cdac.logging_mode quiet'
{
  echo "AUID=$AUID BUID=$BUID XINO=$XINO DEVRAW=$DEVRAW"
  echo "verbose_audit=$(sh 'cat /sys/kernel/debug/iguard/verbose_audit') logging_mode=$(sh 'getprop persist.debug.cdac.logging_mode')"
} | tee "$OUT/meta.txt"
sh "$POLICY clear" >/dev/null
qc > "$OUT/qc_before.txt"
# 1) A+X rule -> deny
sh "$POLICY add service_id=5 op_id=401 caller_uid=$AUID operation=openAssetFile ino=$XINO s_dev=$DEVRAW i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 decision=deny reason=logoff_check_A_X" | tee "$OUT/rule_add.txt"
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action write --es mode w --es label lc_A --es content LC-A-DENY-AAAA -d $X_URI" >/dev/null 2>&1
sleep 2
$ADB -s $S shell 'run-as com.demo.espafdtest cat files/lc_A.csv' > "$OUT/lc_A_app.csv" 2>/dev/null
qc > "$OUT/qc_after_A_deny.txt"
# 2) same rule -> B legal write (allow)
$ADB -s $S shell "am start -W -n com.demo.espafdtestb/.MainActivity --es action write --es mode w --es label lc_B --es content LC-B-ALLOW-AAAA -d $X_URI" >/dev/null 2>&1
sleep 2
$ADB -s $S shell 'run-as com.demo.espafdtestb cat files/lc_B.csv' > "$OUT/lc_B_app.csv" 2>/dev/null
qc > "$OUT/qc_after_B_allow.txt"
# 3) clear -> A recovers
sh "$POLICY clear" | tee "$OUT/rule_clear.txt"
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action write --es mode w --es label lc_A2 --es content 0123456789ABCD -d $X_URI" >/dev/null 2>&1
sleep 2
$ADB -s $S shell 'run-as com.demo.espafdtest cat files/lc_A2.csv' > "$OUT/lc_A2_app.csv" 2>/dev/null
qc > "$OUT/qc_after_A_recover.txt"
echo "function check done -> $OUT"
