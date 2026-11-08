#!/usr/bin/env bash
# setup_side.sh <enabled|stripped> — install timing+A APKs, grant espafd_tree to
# both, create X.bin (14 bytes). Used on each fresh boot (fresh userdata).
set -u
ADB=adb; S=0.0.0.0:6528
SIDE=$1
HERE="$(cd "$(dirname "$0")" && pwd)"
sh() { $ADB -s $S shell "$@"; }
$ADB connect 0.0.0.0:6528 >/dev/null 2>&1 || true
$ADB -s $S install -r "$HERE/../../10_controls_matched_builds_timing_20261023/03_timing_app/build/esp-timing-signed.apk" >/dev/null 2>&1
$ADB -s $S install -r cdac_esp_endpoint_validation_20261022/07_side_effect_order/fixtures/app_diag/build/espafdtest-signed.apk >/dev/null 2>&1
if [ "$SIDE" = enabled ]; then
  $ADB -s $S install -r cdac_esp_endpoint_validation_20261022/01_fixtures/app_b/build/espafdtest-signed.apk >/dev/null 2>&1
  $ADB -s $S push cdac_esp_afd_wrapper_runtime_validation_20261022/01_device_preflight/iguardctl_test /data/local/tmp/iguardctl_test >/dev/null 2>&1
  sh 'chmod 755 /data/local/tmp/iguardctl_test'
  # make framework logging_mode take effect: property is read at class load and
  # addChangeCallback was observed not to deliver; restart the provider process.
  sh 'am force-stop com.android.externalstorage'
fi
# grant: timing creates the tree, A reuses it
bash "$HERE/saf_grant_create.sh" com.demo.esptiming com.demo.esptiming/.MainActivity espafd_tree >/dev/null 2>&1
sleep 2
g1=$(sh 'cat /sdcard/Android/data/com.demo.esptiming/files/grants.txt 2>/dev/null')
bash "$HERE/saf_grant_existing.sh" com.demo.espafdtest com.demo.espafdtest/.MainActivity espafd_tree >/dev/null 2>&1
sleep 2
g2=$(sh 'run-as com.demo.espafdtest cat files/grants.txt 2>/dev/null')
# fixture X via A
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action create --es tree_uri '$TREE' --es name X.bin --es content 0123456789ABCD --es label fix_X" >/dev/null 2>&1
sleep 2
stat=$($ADB -s $S shell 'stat -c "%s %d %i" /data/media/0/espafd_tree/X.bin' | tr -d '\r')
echo "side=$SIDE timing_grant=[$g1] A_grant=[$g2] X_stat=[$stat]"
echo "$SIDE|$g1|$g2|$stat" >> "$HERE/../runtime/setup_history.txt"
