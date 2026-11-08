#!/usr/bin/env bash
# mech_run.sh <N|L|C> <boot_id> — execute the frozen N/L/C mechanism comparison.
# Dynamic UIDs/objects; all raw rows saved; development attempts not mixed.
set -u
ADB=adb; S=0.0.0.0:6528
POLICY=/data/local/tmp/iguardctl_test
MECH=$1; BID=$2
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../03_mech_compare/results/${MECH}_${BID}"; mkdir -p "$OUT"
sh() { $ADB -s $S shell "$@"; }
snap() { python3 "$HERE/file_state.py" "$1" "$2" "$OUT"; }
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
TREEB='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree_b'
XU="$TREE/document/primary%3Aespafd_tree%2FX.bin"
YU="$TREE/document/primary%3Aespafd_tree%2FY.bin"
D2U="$TREE/document/primary%3Aespafd_tree%2FD2.bin"
XNU="$TREEB/document/primary%3Aespafd_tree_b%2FXN.bin"
write() { # pkg uri label payload mode
  sh 'logcat -c'
  $ADB -s $S shell "am start -W -n $1/.MainActivity --es action write --es mode ${5:-w} --es label $3 --es content $4 -d $2" >/dev/null 2>&1
  sleep 2
  $ADB -s $S shell "run-as $1 cat files/$3.csv" > "$OUT/$3_app.csv" 2>/dev/null || true
  sh 'logcat -d | grep -E "L_POLICY_DENY" | tail -3' > "$OUT/$3_l_log.txt" 2>/dev/null
}
AUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.espafdtest uid:' | sed 's/.*uid://' | tr -d '\r')
BUID=$($ADB -s $S shell 'cmd package list packages -U' | grep '^package:com.demo.espafdtestb uid:' | sed 's/.*uid://' | tr -d '\r')
XINO=$($ADB -s $S shell 'stat -c %i /data/media/0/espafd_tree/X.bin' | tr -d '\r')
XDEV=$($ADB -s $S shell 'stat -c %d /data/media/0/espafd_tree/X.bin' | tr -d '\r')
DEVRAW=$(( ((XDEV>>8)<<20) + (XDEV&255) ))
echo "MECH=$MECH BID=$BID AUID=$AUID BUID=$BUID XINO=$XINO DEVRAW=$DEVRAW" | tee "$OUT/meta.txt"
install_policy() { # subject uid target doc-or-file
  case "$MECH" in
    L) DOC="primary:espafd_tree/$2.bin"; sh "setprop persist.lab.lpolicy '$1|$DOC'" ;;
    C)
      if [ "$2" = "X" ]; then
        sh "$POLICY add service_id=5 op_id=401 caller_uid=$1 operation=openAssetFile ino=$XINO s_dev=$DEVRAW i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 decision=deny reason=mech_${MECH}_$2" >> "$OUT/policy.log"
      else
        INO2=$($ADB -s $S shell "stat -c %i /data/media/0/espafd_tree/$2.bin" | tr -d '\r')
        sh "$POLICY add service_id=5 op_id=401 caller_uid=$1 operation=openAssetFile ino=$INO2 s_dev=$DEVRAW i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 decision=deny reason=mech_${MECH}_$2" >> "$OUT/policy.log"
      fi ;;
    N) echo "N: no policy surface; request treated as native allow" >> "$OUT/policy.log" ;;
  esac
  sleep 1
}
clear_policy() {
  case "$MECH" in
    L) sh "setprop persist.lab.lpolicy ''" ;;
    C) sh "$POLICY clear" >> "$OUT/policy.log" ;;
    N) : ;;
  esac
  sleep 1
}
readback_policy() {
  case "$MECH" in
    L) sh 'getprop persist.lab.lpolicy' | tr -d '\r' ;;
    C) sh 'cat /sys/kernel/debug/iguard/policy_dump' | grep -c "would-deny" | tr -d '\r' ;;
    N) echo "N/A" ;;
  esac
}
# core sequence x3
for i in 1 2 3; do
  clear_policy
  write com.demo.espafdtest "$XU" "${MECH}_${i}_c1_AX_nopol" "C1-AX-AAAAAAAAAA" w
  install_policy "$AUID" "X"
  snap "X.bin" "${MECH}_${i}_c2_S0"
  write com.demo.espafdtest "$XU" "${MECH}_${i}_c2_AX_pol" "C2-AX-BBBBBBBBBB" w
  snap "X.bin" "${MECH}_${i}_c2_S1"
  write com.demo.espafdtest "$YU" "${MECH}_${i}_c3_AY_pol" "C3-AY-CCCCCCCCCC" w
  write com.demo.espafdtestb "$XU" "${MECH}_${i}_c4_BX_pol" "C4-BX-DDDDDDDDDD" w
  echo "rep=$i policy_readback=$(readback_policy)" >> "$OUT/policy.log"
  clear_policy
done
# minimal sequence (L/C only; N records N/A)
if [ "$MECH" != "N" ]; then
  install_policy "$AUID" "X"
  write com.demo.espafdtest "$XU" "${MECH}_m1_AX_deny" "M1-DENY-AAAAAAAA" w
  clear_policy
  write com.demo.espafdtest "$XU" "${MECH}_m2_AX_recover" "M2-RECOVER-AAAAAA" w
  install_policy "$BUID" "X"
  write com.demo.espafdtestb "$XU" "${MECH}_m3_BX_deny" "M3-B-DENY-AAAAAA" w
  write com.demo.espafdtest "$XU" "${MECH}_m4_AX_allow" "M4-A-ALLOW-AAAAAA" w
  clear_policy
  write com.demo.espafdtest "$XNU" "${MECH}_m5_native_deny" "M5-NATIVE-AAAAAA" w
else
  echo "N minimal-sequence=N/A (no policy surface)" >> "$OUT/policy.log"
fi
# truncation diagnostic: D2.bin 16 bytes
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action create --es tree_uri '$TREE' --es name D2.bin --es content 0123456789ABCDEF --es label ${MECH}_d2init" >/dev/null 2>&1
sleep 2
# control: no policy, wt
clear_policy
snap "D2.bin" "${MECH}_t_ctl_S0"
write com.demo.espafdtest "$D2U" "${MECH}_t_ctl_wt" "D2C" wt
snap "D2.bin" "${MECH}_t_ctl_S1"
# restore 16B, then policy A+D2, wt
write com.demo.espafdtest "$D2U" "${MECH}_t_restore" "0123456789ABCDEF" w
snap "D2.bin" "${MECH}_t_pol_S0"
install_policy "$AUID" "D2"
write com.demo.espafdtest "$D2U" "${MECH}_t_pol_wt" "D2D" wt
snap "D2.bin" "${MECH}_t_pol_S1"
snap "D2.bin" "${MECH}_t_pol_S2"
clear_policy
echo "mech_run $MECH done -> $OUT"
