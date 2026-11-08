#!/usr/bin/env bash
# setup_mech.sh — install A/B, grant espafd_tree (A,B) and espafd_tree_b (B only),
# fixtures X/Y/D2 (A, in espafd_tree) and XN (B, in espafd_tree_b).
set -u
ADB=adb; S=0.0.0.0:6528
HERE="$(cd "$(dirname "$0")" && pwd)"
sh() { $ADB -s $S shell "$@"; }
$ADB connect 0.0.0.0:6528 >/dev/null 2>&1 || true
$ADB -s $S install -r cdac_esp_endpoint_validation_20261022/07_side_effect_order/fixtures/app_diag/build/espafdtest-signed.apk >/dev/null 2>&1
$ADB -s $S install -r cdac_esp_endpoint_validation_20261022/01_fixtures/app_b/build/espafdtest-signed.apk >/dev/null 2>&1
bash "$HERE/saf_grant_create.sh" com.demo.espafdtest com.demo.espafdtest/.MainActivity espafd_tree >/dev/null 2>&1
sleep 2
bash "$HERE/saf_grant_existing.sh" com.demo.espafdtestb com.demo.espafdtestb/.MainActivity espafd_tree >/dev/null 2>&1
sleep 2
bash "$HERE/saf_grant_create.sh" com.demo.espafdtestb com.demo.espafdtestb/.MainActivity espafd_tree_b >/dev/null 2>&1
sleep 2
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
TREEB='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree_b'
for f in X:0123456789ABCD Y:YYYYYYYYYYYYYY; do
  name=${f%%:*}; content=${f#*:}
  $ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action create --es tree_uri '$TREE' --es name $name.bin --es content $content --es label fix_$name" >/dev/null 2>&1
  sleep 2
done
$ADB -s $S shell "am start -W -n com.demo.espafdtestb/.MainActivity --es action create --es tree_uri '$TREEB' --es name XN.bin --es content 0123456789ABCD --es label fix_XN" >/dev/null 2>&1
sleep 2
echo "grants_A=$($ADB -s $S shell 'run-as com.demo.espafdtest cat files/grants.txt' 2>/dev/null | tr '\n' ';')"
echo "grants_B=$($ADB -s $S shell 'run-as com.demo.espafdtestb cat files/grants.txt' 2>/dev/null | tr '\n' ';')"
$ADB -s $S shell 'stat -c "%n %s %d %i" /data/media/0/espafd_tree/X.bin /data/media/0/espafd_tree/Y.bin /data/media/0/espafd_tree_b/XN.bin'
