#!/usr/bin/env python3
import os, sys
WORK="three_version_r1_3boot_scope_alignment_20261102_100240"
RUNDISK="three_version_r1_3boot_scope_alignment_20261102_100240"
KDIR="cdac_esp_endpoint_validation_20261022/19_external_provider_qualification_20261026/artifacts/kernel_openkeychain_dist"
ADB="adb"

BOOTS=[
 dict(platform="A15", tag="a15_boot2", inst=2, port=6521, runid="A15R1-B2", comp=2,
      src="aosp15_cleanup_20261030_171705",
      host="aosp15_cleanup_20261030_171705/out_cdac_r1_cleanup_20261030/host/linux-x86",
      product="aosp15_cleanup_20261030_171705/out_cdac_r1_cleanup_20261030/target/product/vsoc_x86_64_only",
      fx="a15_cleanup_fix_and_porting_audit_closeout_20261030_171705/06_r1_regression/fx",
      use_hostpkg=True, r1="a15cdac_r14a", r2="a15cdac_rev"),
 dict(platform="A15", tag="a15_boot3", inst=3, port=6522, runid="A15R1-B3", comp=3,
      src="aosp15_cleanup_20261030_171705",
      host="aosp15_cleanup_20261030_171705/out_cdac_r1_cleanup_20261030/host/linux-x86",
      product="aosp15_cleanup_20261030_171705/out_cdac_r1_cleanup_20261030/target/product/vsoc_x86_64_only",
      fx="a15_cleanup_fix_and_porting_audit_closeout_20261030_171705/06_r1_regression/fx",
      use_hostpkg=True, r1="a15cdac_r14a", r2="a15cdac_rev"),
 dict(platform="A16", tag="a16_boot2", inst=97, port=6616, runid="R35-B2", comp=2,
      src="aosp16",
      host="aosp16/out/host/linux-x86",
      product="cdac_esp_endpoint_validation_20261022/19_external_provider_qualification_20261026/artifacts/C19_media",
      fx="35_r1_reversal_and_data_provenance_20261028/04_fixtures",
      policy_src="35_r1_reversal_and_data_provenance_20261028/05_artifacts/iguardctl_test",
      use_hostpkg=False, r1="cdac35_r14a", r2="cdac35_rev",
      apk_a="35_r1_reversal_and_data_provenance_20261028/04_fixtures/app_a/build/app_a-signed.apk",
      apk_b="35_r1_reversal_and_data_provenance_20261028/04_fixtures/app_b/build/app_b-signed.apk"),
 dict(platform="A16", tag="a16_boot3", inst=98, port=6617, runid="R35-B3", comp=3,
      src="aosp16",
      host="aosp16/out/host/linux-x86",
      product="cdac_esp_endpoint_validation_20261022/19_external_provider_qualification_20261026/artifacts/C19_media",
      fx="35_r1_reversal_and_data_provenance_20261028/04_fixtures",
      policy_src="35_r1_reversal_and_data_provenance_20261028/05_artifacts/iguardctl_test",
      apk_a="35_r1_reversal_and_data_provenance_20261028/04_fixtures/app_a/build/app_a-signed.apk",
      apk_b="35_r1_reversal_and_data_provenance_20261028/04_fixtures/app_b/build/app_b-signed.apk",
      use_hostpkg=False, r1="cdac35_r14a", r2="cdac35_rev"),
 dict(platform="A17", tag="a17_boot3", inst=99, port=6618, runid="A17R1-B3", comp=3,
      src="aosp17",
      host="aosp17/out_cdac_r1_20261029/host/linux-x86",
      product="aosp17/out_cdac_r1_20261029/target/product/vsoc_x86_64_only",
      fx="a17_r1_port_and_enforcement_20261029_174341/07_fixtures",
      policy_src="a17_r1_port_and_enforcement_20261029_174341/07_fixtures/iguardctl_test",
      use_hostpkg=False, r1="cdac35_r14a", r2="cdac35_rev"),
]

LAUNCH_A15 = '''#!/bin/bash
# {tag}: launch A15 FIXED artifacts + shared CDAC 6.12 kernel. Instance #{inst}, ADB {port}.
set -euo pipefail
BASE={rundisk}/b{inst}
SRC={src}; HOST={host}; PRODUCT={product}
KDIR={kdir}; INSTANCE={inst}; ADB_PORT={port}
mkdir -p "$BASE/images" "$BASE/assembly" "$BASE/instance" "$BASE/early_tmp" "$BASE/home"
cp -a "$HOST/cvd-host_package/." "$BASE/home/"
while IFS= read -r -d '' art; do
  cp --reflink=auto --sparse=always --preserve=mode,timestamps "$art" "$BASE/images/"
done < <(find "$PRODUCT" -maxdepth 1 -type f \\( -name '*.img' -o -name 'bootloader' -o -name 'android-info.txt' -o -name 'fastboot-info.txt' -o -name 'build_fingerprint.txt' \\) ! -name '*debug.img' -print0)
mkdir -p "$BASE/i/instances/cvd-$INSTANCE"
truncate -s 8589934592 "$BASE/i/instances/cvd-$INSTANCE/userdata.img"
printf '%s\\n' "$SRC" > "$BASE/source-root.txt"
printf '%s\\n' "$PRODUCT" > "$BASE/product-source.txt"
printf '%s\\n' "$KDIR" > "$BASE/kernel-dir.txt"
cd /data2
env ANDROID_HOST_OUT="$BASE/home" ANDROID_PRODUCT_OUT="$BASE/images" \\
  CUTTLEFISH_CONFIG_FILE="$BASE/assembly/cuttlefish_config.json" CUTTLEFISH_INSTANCE=$INSTANCE \\
  HOME="$BASE/home" PATH="$BASE/home/bin:$PATH" \\
  setsid "$BASE/home/bin/launch_cvd" \\
  --report_anonymous_usage_stats=n --base_instance_num=$INSTANCE --num_instances=1 \\
  --resume=false --daemon --cpus=4 --memory_mb=4096 --smt=false \\
  --gpu_mode=guest_swiftshader --hwcomposer=none --enable_audio=false \\
  --start_webrtc=false --netsim=false --netsim_bt=false --netsim_uwb=false \\
  --enable_host_bluetooth=true --enable_host_nfc=false --enable_host_uwb=false \\
  --enable_wifi=false --enable_modem_simulator=false \\
  --start_gnss_proxy=false --use_sdcard=false --setupwizard_mode=DISABLED \\
  --data_policy=always_create --blank_data_image_mb=4096 \\
  --kernel_path="$KDIR/bzImage" --initramfs_path="$KDIR/initramfs.img" \\
  --system_image_dir="$BASE/images" --assembly_dir="$BASE/assembly" \\
  --instance_dir="$BASE/i" --early_tmp_dir="$BASE/early_tmp" \\
  < /dev/null > "$BASE/launch.log" 2>&1 &
echo $! > "$BASE/launch.pid"
echo "launched {tag} pid=$(cat "$BASE/launch.pid") instance=$INSTANCE adb_port=$ADB_PORT at $(date -Is)"
'''

LAUNCH_GEN = '''#!/bin/bash
# {tag}: launch {platform} frozen artifacts + shared CDAC 6.12 kernel. Instance #{inst}, ADB {port}.
set -euo pipefail
BASE={rundisk}/b{inst}
SRC={src}; HOST={host}; PRODUCT={product}
KDIR={kdir}; INSTANCE={inst}; ADB_PORT={port}
mkdir -p "$BASE/images" "$BASE/assembly" "$BASE/instance" "$BASE/early_tmp" "$BASE/home"
while IFS= read -r -d '' art; do
  cp --reflink=auto --sparse=always --preserve=mode,timestamps "$art" "$BASE/images/"
done < <(find "$PRODUCT" -maxdepth 1 -type f \\( -name '*.img' \\) ! -name 'userdata.img' ! -name '*debug.img' -print0)
mkdir -p "$BASE/i/instances/cvd-$INSTANCE"
truncate -s 8589934592 "$BASE/i/instances/cvd-$INSTANCE/userdata.img"
printf '%s\\n' "$SRC" > "$BASE/source-root.txt"
printf '%s\\n' "$PRODUCT" > "$BASE/product-source.txt"
printf '%s\\n' "$KDIR" > "$BASE/kernel-dir.txt"
env ANDROID_HOST_OUT="$HOST" ANDROID_PRODUCT_OUT="$BASE/images" \\
  CUTTLEFISH_CONFIG_FILE="$BASE/assembly/cuttlefish_config.json" CUTTLEFISH_INSTANCE=$INSTANCE \\
  HOME="$BASE/home" \\
  setsid "$HOST/bin/launch_cvd" \\
  --report_anonymous_usage_stats=n --base_instance_num=$INSTANCE --num_instances=1 \\
  --resume=false --daemon --cpus=4 --memory_mb=4096 --smt=false \\
  --gpu_mode=guest_swiftshader --hwcomposer=none --enable_audio=false \\
  --start_webrtc=false --netsim=false --netsim_bt=false --netsim_uwb=false \\
  --enable_host_bluetooth=true --enable_host_nfc=false --enable_host_uwb=false \\
  --enable_wifi=false --enable_tap_devices=false --enable_modem_simulator=false \\
  --start_gnss_proxy=false --use_sdcard=false --setupwizard_mode=DISABLED \\
  --data_policy=always_create --blank_data_image_mb=4096 \\
  --kernel_path="$KDIR/bzImage" --initramfs_path="$KDIR/initramfs.img" \\
  --system_image_dir="$BASE/images" --assembly_dir="$BASE/assembly" \\
  --instance_dir="$BASE/i" --early_tmp_dir="$BASE/early_tmp" \\
  < /dev/null > "$BASE/launch.log" 2>&1 &
echo $! > "$BASE/launch.pid"
echo "launched {tag} pid=$(cat "$BASE/launch.pid") instance=$INSTANCE adb_port=$ADB_PORT at $(date -Is)"
'''

WAIT = '''#!/bin/bash
# wait_boot.sh — wait for boot_completed on {port}
set -u
ADB=adb; PORT={port}; MAX=${{1:-180}}
BASE={rundisk}/b{inst}
$ADB start-server >/dev/null 2>&1 || true
for ((i=0;i<MAX;i++)); do
  $ADB connect 0.0.0.0:$PORT >/dev/null 2>&1 || true
  completed="$(timeout 10 $ADB -s 0.0.0.0:$PORT shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r' || true)"
  if [ "$completed" = "1" ]; then
    echo "BOOT_COMPLETED=1 attempts=$i at $(date -Is)" | tee "$BASE/boot_status.txt"; exit 0
  fi
  if grep -q "VIRTUAL_DEVICE_BOOT_FAILED" "$BASE/launch.log" 2>/dev/null; then
    echo "BOOT_FAILED at $(date -Is)" > "$BASE/boot_status.txt"; exit 1
  fi
  sleep 5
done
echo "BOOT_TIMEOUT at $(date -Is)" > "$BASE/boot_status.txt"; exit 1
'''

PREFLIGHT = '''#!/bin/bash
# run_preflight.sh — empty-policy preflight for {tag} (instance #{inst}, ADB {port}).
set -u
W={work}
OUT="$W/runs/{tag}/preflight"; mkdir -p "$OUT"
ADB=adb; S=0.0.0.0:{port}
POLICY=/data/local/tmp/iguardctl_test
FX={fx}; POLICY_SRC={policy_src}
sh() {{ $ADB -s $S shell "$@"; }}
note() {{ echo "[$(date -Is)] $*" | tee -a "$OUT/ledger.log"; }}
FW_GREP='CDAC_ENDPOINT_RESOLVE|CDAC_CONTEXT_ENTER|CDAC_CONTEXT_EXIT|CDAC_FRAMEWORK_CONTEXT_PUBLISH|CDAC_BINDER_VFS_JOIN|CDAC_BINDER_PUSH|CDAC_BINDER_POP|CDAC_BINDER_STACK_MISMATCH|CDAC_CONTEXT_STACK_MISMATCH|iguard_ctx: decision|decision-apply|enforce-plan|real-enforce|perf seq|avc:|CDAC_BINDER_ENTRY'
capfw() {{ local label=$1; sh 'logcat -d' 2>/dev/null | grep -E "$FW_GREP" > "$OUT/${{label}}_framework.txt" || true; }}
probe() {{ local label=$1 pkg=$2 uri=$3 marker=$4
  sh 'logcat -c'
  $ADB -s $S shell "am start -W -n $pkg/.MainActivity --es cmd read_cpc --es uri '$uri' --es marker '$marker'" > "$OUT/${{label}}_am.txt" 2>&1
  sleep 2
  sh 'logcat -d -s CDAC27_PATH:I' > "$OUT/${{label}}_app.txt" 2>/dev/null
  capfw "$label"
  grep -m1 -E 'READ_CPC ok|RESULT fail' "$OUT/${{label}}_app.txt" || echo "no result $label"
}}
$ADB start-server >/dev/null 2>&1; $ADB connect $S >/dev/null 2>&1
note "{tag} preflight start"
sh 'getprop ro.build.fingerprint' > "$OUT/fingerprint.txt"
sh 'getprop ro.build.version.release' > "$OUT/release.txt"
sh 'getprop ro.build.version.sdk' > "$OUT/sdk.txt"
sh 'getprop ro.build.version.codename' > "$OUT/codename.txt"
sh 'getprop ro.build.id' > "$OUT/build_id.txt"
sh 'getprop ro.build.version.security_patch' > "$OUT/security_patch.txt"
sh 'getenforce' > "$OUT/selinux_mode.txt"
sh 'uname -r' > "$OUT/kernel_rel.txt"
sh 'cat /proc/version' > "$OUT/proc_version.txt"
sh 'cat /proc/sys/kernel/random/boot_id' > "$OUT/boot_id.txt"
sh 'ls -lZ /dev/iguard_ctl' > "$OUT/dev_iguard_ctl_lsZ.txt"
sh 'lsmod' > "$OUT/lsmod.txt"
$ADB -s $S install -r "{apk_a}" >> "$OUT/ledger.log" 2>&1
$ADB -s $S install -r "{apk_b}" >> "$OUT/ledger.log" 2>&1
$ADB -s $S root >/dev/null 2>&1; sleep 1
sh 'id -Z' > "$OUT/shell_context_post_root.txt"
sh wm dismiss-keyguard || true
sh 'setprop persist.debug.cdac.logging_mode audit'
sh 'mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null; echo 1 > /sys/kernel/debug/iguard/verbose_audit'
sh 'cat /sys/kernel/debug/iguard/verbose_audit' > "$OUT/verbose_audit.txt"
sh 'cat /sys/kernel/debug/iguard/quiet_counters' > "$OUT/initial_qc.txt" 2>/dev/null || true
sh 'cat /sys/kernel/debug/iguard/policy_dump' > "$OUT/initial_policy_dump.txt" 2>/dev/null || true
$ADB -s $S push "$POLICY_SRC" /data/local/tmp/iguardctl_test >/dev/null 2>&1
sh 'chmod 755 /data/local/tmp/iguardctl_test'
$ADB -s $S shell pm grant com.demo.espafdtestb android.permission.READ_MEDIA_IMAGES >> "$OUT/ledger.log" 2>&1
uidA=$(sh 'cmd package list packages -U' | grep '^package:com.demo.espafdtest uid:' | sed 's/.*uid://' | tr -d '\\r')
uidB=$(sh 'cmd package list packages -U' | grep '^package:com.demo.espafdtestb uid:' | sed 's/.*uid://' | tr -d '\\r')
note "uidA=$uidA uidB=$uidB"
for nm in image1 image2; do
  sh 'logcat -c'
  $ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es cmd make_image --es name $nm" >/dev/null 2>&1
  sleep 2
  sh 'logcat -d -s CDAC27_PATH:I' > "$OUT/make_$nm.txt"
  capfw "make_$nm"
  URI=$(grep -m1 'MAKE_IMAGE ok' "$OUT/make_$nm.txt" | sed -E 's/.*uri=(content:[^ ]*).*/\\1/' | tr -d '\\r')
  DATA=$(grep -m1 'MAKE_IMAGE ok' "$OUT/make_$nm.txt" | sed -E 's/.*data=(\\/storage[^ ]*).*/\\1/' | tr -d '\\r')
  if [ "$nm" = image1 ]; then URI_X=$URI; DATA_X=$DATA; else URI_Y=$URI; DATA_Y=$DATA; fi
  note "make_$nm URI=$URI DATA=$DATA"
  test -n "$URI" || {{ note "FAIL make $nm no URI"; exit 2; }}
done
BACK_X=${{DATA_X/\\/storage\\/emulated\\/0/\\/data\\/media\\/0}}
BACK_Y=${{DATA_Y/\\/storage\\/emulated\\/0/\\/data\\/media\\/0}}
INO_X=$(sh "stat -c %i '$BACK_X'" | tr -d '\\r')
INO_Y=$(sh "stat -c %i '$BACK_Y'" | tr -d '\\r')
sh "stat -c 'ino=%i size=%s mode=%a dev=%d mtime=%y' '$BACK_X'" > "$OUT/backing_X_stat.txt"
sh "stat -c 'ino=%i size=%s mode=%a dev=%d mtime=%y' '$BACK_Y'" > "$OUT/backing_Y_stat.txt"
sh "cat '$BACK_X' | sha256sum" > "$OUT/backing_X_sha.txt"
sh "cat '$BACK_Y' | sha256sum" > "$OUT/backing_Y_sha.txt"
# control-plane round trip (su management path)
sh "$POLICY add service_id=6 op_id=501 caller_uid=999999 operation=openFile ino=999999 s_dev=45 i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason={tag}_ctrl" > "$OUT/ctrl_rule_add.txt"
sleep 1; sh 'cat /sys/kernel/debug/iguard/policy_dump' > "$OUT/ctrl_rule_dump.txt" 2>/dev/null || true
sh "$POLICY clear" > "$OUT/ctrl_rule_clear.txt"
sleep 1; sh 'cat /sys/kernel/debug/iguard/policy_dump' > "$OUT/ctrl_rule_dump_clear.txt" 2>/dev/null || true
# empty-policy probes
for i in 1 2 3; do note "E_AX_$i"; probe "E_AX_$i" com.demo.espafdtest "$URI_X" CDAC25GPSMARK_AAAA; done
for i in 1 2 3; do note "E_BX_$i"; probe "E_BX_$i" com.demo.espafdtestb "$URI_X" CDAC25GPSMARK_AAAA; done
APPDEV_X=''
if [ -f "$OUT/E_AX_1_app.txt" ]; then APPDEV_X=$(grep -m1 'READ_CPC ok' "$OUT/E_AX_1_app.txt" | sed -nE 's/.*dev=([0-9]+):([0-9]+).*/\\1:\\2/p' | tr -d '\\r'); fi
if [ -n "$APPDEV_X" ]; then MAJ=${{APPDEV_X%%:*}}; MIN=${{APPDEV_X##*:}}; if [ "$MAJ" = 0 ]; then SDEV_X=$MIN; else SDEV_X=$(( MAJ*1048576 + MIN )); fi; else SDEV_X=45; fi
sh 'ps -A -o PID,NAME' > "$OUT/ps_all.txt"
for pkg in com.demo.espafdtest com.demo.espafdtestb com.android.providers.media.module; do
  pid=$(sh "pidof $pkg" | tr -d '\\r')
  if [ -n "$pid" ]; then sh "cat /proc/$pid/attr/current" > "$OUT/proc_attr_${{pkg}}.txt"; fi
done
sh 'cat /sys/kernel/debug/iguard/quiet_counters' > "$OUT/final_qc.txt" 2>/dev/null || true
sh 'cat /sys/kernel/debug/iguard/policy_dump' > "$OUT/final_policy_dump.txt" 2>/dev/null || true
cat > "$OUT/uris.env" <<ENV
URI_X='$URI_X'
URI_Y='$URI_Y'
BACK_X='$BACK_X'
BACK_Y='$BACK_Y'
INO_X='$INO_X'
INO_Y='$INO_Y'
uidA='$uidA'
uidB='$uidB'
SDEV_X='$SDEV_X'
APPDEV_X='$APPDEV_X'
ENV
note "{tag} preflight end (APPDEV_X=$APPDEV_X SDEV_X=$SDEV_X)"
'''

MATRIX = '''#!/bin/bash
# run_matrix.sh — formal 30-request B0-B3 matrix for {tag} (ADB {port}).
set -u
W={work}; OUT="$W/runs/{tag}/matrix"; mkdir -p "$OUT"
ADB=adb; S=0.0.0.0:{port}
POLICY=/data/local/tmp/iguardctl_test
ENVFILE="$W/runs/{tag}/preflight/uris.env"
sh() {{ $ADB -s $S shell "$@"; }}
note() {{ echo "[$(date -Is)] $*" | tee -a "$OUT/ledger.log"; }}
FW_GREP='CDAC_ENDPOINT_RESOLVE|CDAC_CONTEXT_ENTER|CDAC_CONTEXT_EXIT|CDAC_FRAMEWORK_CONTEXT_PUBLISH|CDAC_BINDER_VFS_JOIN|CDAC_BINDER_PUSH|CDAC_BINDER_POP|CDAC_BINDER_STACK_MISMATCH|CDAC_CONTEXT_STACK_MISMATCH|iguard_ctx: decision|decision-apply|enforce-plan|real-enforce|perf seq|avc:|CDAC_BINDER_ENTRY|CDAC_BINDER_NO_CONTEXT'
probe() {{ local label=$1 pkg=$2 uri=$3 marker=$4
  sh 'logcat -c'
  $ADB -s $S shell "am start -W -n $pkg/.MainActivity --es cmd read_cpc --es uri '$uri' --es marker '$marker'" > "$OUT/${{label}}_am.txt" 2>&1
  sleep 2
  sh 'logcat -d -s CDAC27_PATH:I' > "$OUT/${{label}}_app.txt" 2>/dev/null
  sh 'logcat -d' 2>/dev/null | grep -E "$FW_GREP" > "$OUT/${{label}}_framework.txt" || true
  sh 'dmesg 2>/dev/null' | grep -E 'iguard|CDAC_' | tail -120 > "$OUT/${{label}}_kernel.txt" || true
  if grep -m1 -E 'READ_CR ok|READ_CPC ok|RESULT fail' "$OUT/${{label}}_app.txt" >/dev/null 2>&1; then
    grep -m1 -E 'READ_CR ok|READ_CPC ok|RESULT fail' "$OUT/${{label}}_app.txt"
  else echo "no app result line for $label"; fi
}}
qc_snap() {{ sh 'cat /sys/kernel/debug/iguard/quiet_counters' > "$OUT/$1_qc.txt" 2>/dev/null || true; }}
dump_snap() {{ sh 'cat /sys/kernel/debug/iguard/policy_dump' > "$OUT/$1.txt" 2>/dev/null || true; }}
backing_snap() {{ local label=$1
  sh "stat -c 'ino=%i size=%s mode=%a dev=%d mtime=%y' '$BACK_X'" > "$OUT/${{label}}_backingX.txt" 2>/dev/null
  sh "stat -c 'ino=%i size=%s mode=%a dev=%d mtime=%y' '$BACK_Y'" > "$OUT/${{label}}_backingY.txt" 2>/dev/null
  sh "cat '$BACK_X' | sha256sum" > "$OUT/${{label}}_backingX.sha" 2>/dev/null
  sh "cat '$BACK_Y' | sha256sum" > "$OUT/${{label}}_backingY.sha" 2>/dev/null
}}
$ADB start-server >/dev/null 2>&1; $ADB connect $S >/dev/null 2>&1
source "$ENVFILE"
: "${{SDEV_X:=45}}"
echo "MATRIX START $(date -Is) uidA=$uidA uidB=$uidB INO_X=$INO_X INO_Y=$INO_Y URI_X=$URI_X SDEV_X=$SDEV_X" | tee "$OUT/ledger.log"
sh 'getprop ro.build.fingerprint' > "$OUT/fingerprint.txt"
sh 'getprop ro.build.version.release' > "$OUT/release.txt"
sh 'getprop ro.build.version.sdk' > "$OUT/sdk.txt"
sh 'getenforce' > "$OUT/selinux_mode.txt"
sh 'uname -r' > "$OUT/kernel_rel.txt"
sh 'cat /proc/version' > "$OUT/proc_version.txt"
sh 'cat /proc/sys/kernel/random/boot_id' > "$OUT/boot_id.txt"
sh 'cat /sys/kernel/debug/iguard/quiet_counters' > "$OUT/initial_qc.txt" 2>/dev/null || true
sh 'cat /sys/kernel/debug/iguard/policy_dump' > "$OUT/initial_policy_dump.txt" 2>/dev/null || true
sh 'logcat -G 64M' > "$OUT/logcat_resize.txt" 2>&1 || true
$ADB -s $S logcat -v threadtime > "$OUT/logcat_stream.txt" 2>&1 &
echo $! > "$OUT/logcat_stream.pid"
$ADB -s $S shell 'dmesg -w' > "$OUT/dmesg_stream.txt" 2>&1 &
echo $! > "$OUT/dmesg_stream.pid"
echo "STREAMS_STARTED $(date -Is)" | tee -a "$OUT/ledger.log"
sleep 2
uidA_now=$(sh 'cmd package list packages -U' | grep '^package:com.demo.espafdtest uid:' | sed 's/.*uid://' | tr -d '\\r')
uidB_now=$(sh 'cmd package list packages -U' | grep '^package:com.demo.espafdtestb uid:' | sed 's/.*uid://' | tr -d '\\r')
note "uidA_now=$uidA_now uidB_now=$uidB_now"
sh 'ps -A -o PID,NAME' > "$OUT/ps_all.txt"
for pkg in com.demo.espafdtest com.demo.espafdtestb com.android.providers.media.module; do
  pid=$(sh "pidof $pkg" | tr -d '\\r')
  if [ -n "$pid" ]; then sh "cat /proc/$pid/attr/current" > "$OUT/proc_attr_${{pkg}}.txt"; fi
done
qc_snap setup_pre; backing_snap setup
note "B0 start (no rule)"
for i in 1 2 3; do note "B0_AX_$i"; probe "B0_AX_$i" com.demo.espafdtest "$URI_X" CDAC25GPSMARK_AAAA | tee -a "$OUT/B0_results.txt"; done
for i in 1 2 3; do note "B0_BX_$i"; probe "B0_BX_$i" com.demo.espafdtestb "$URI_X" CDAC25GPSMARK_AAAA | tee -a "$OUT/B0_results.txt"; done
pidb=$(sh "pidof com.demo.espafdtestb" | tr -d '\\r')
if [ -n "$pidb" ]; then sh "cat /proc/$pidb/attr/current" > "$OUT/proc_attr_com.demo.espafdtestb.txt"; fi
qc_snap b0_post; backing_snap b0
note "B1 install R1 (caller=A)"
sh "$POLICY add service_id=6 op_id=501 caller_uid=$uidA operation=openFile ino=$INO_X s_dev=$SDEV_X i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason={r1}" > "$OUT/b1_rule_add.txt"
sleep 1; dump_snap b1_rule_dump; qc_snap b1_pre; backing_snap b1_pre
for i in 1 2 3; do note "B1_AX_$i"; probe "B1_AX_$i" com.demo.espafdtest "$URI_X" CDAC25GPSMARK_AAAA | tee -a "$OUT/B1_results.txt"; done
for i in 1 2 3; do note "B1_BX_$i"; probe "B1_BX_$i" com.demo.espafdtestb "$URI_X" CDAC25GPSMARK_AAAA | tee -a "$OUT/B1_results.txt"; done
for i in 1 2 3; do note "B1_AY_$i"; probe "B1_AY_$i" com.demo.espafdtest "$URI_Y" CDAC25GPSMARK_BBBB | tee -a "$OUT/B1_results.txt"; done
qc_snap b1_post; backing_snap b1_post
sh "$POLICY clear" > "$OUT/b1_rule_clear.txt"; sleep 1; dump_snap b1_rule_dump_clear
note "B2 install R2 reversed (caller=B)"
sh "$POLICY add service_id=6 op_id=501 caller_uid=$uidB operation=openFile ino=$INO_X s_dev=$SDEV_X i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason={r2}" > "$OUT/b2_rule_add.txt"
sleep 1; dump_snap b2_rule_dump; qc_snap b2_pre; backing_snap b2_pre
for i in 1 2 3; do note "B2_BX_$i"; probe "B2_BX_$i" com.demo.espafdtestb "$URI_X" CDAC25GPSMARK_AAAA | tee -a "$OUT/B2_results.txt"; done
for i in 1 2 3; do note "B2_AX_$i"; probe "B2_AX_$i" com.demo.espafdtest "$URI_X" CDAC25GPSMARK_AAAA | tee -a "$OUT/B2_results.txt"; done
for i in 1 2 3; do note "B2_BY_$i"; probe "B2_BY_$i" com.demo.espafdtestb "$URI_Y" CDAC25GPSMARK_BBBB | tee -a "$OUT/B2_results.txt"; done
qc_snap b2_post; backing_snap b2_post
sh "$POLICY clear" > "$OUT/b2_rule_clear.txt"; sleep 1; dump_snap b2_rule_dump_clear
note "B3 revoke start"
for i in 1 2 3; do note "B3_AX_$i"; probe "B3_AX_$i" com.demo.espafdtest "$URI_X" CDAC25GPSMARK_AAAA | tee -a "$OUT/B3_results.txt"; done
for i in 1 2 3; do note "B3_BX_$i"; probe "B3_BX_$i" com.demo.espafdtestb "$URI_X" CDAC25GPSMARK_AAAA | tee -a "$OUT/B3_results.txt"; done
qc_snap b3_post; backing_snap b3_post; dump_snap final_policy_dump
for pkg in com.demo.espafdtest com.demo.espafdtestb com.android.providers.media.module; do
  pid=$(sh "pidof $pkg" | tr -d '\\r')
  if [ -n "$pid" ]; then sh "cat /proc/$pid/attr/current" > "$OUT/proc_attr_end_${{pkg}}.txt"; fi
done
kill $(cat "$OUT/logcat_stream.pid") 2>/dev/null || true
kill $(cat "$OUT/dmesg_stream.pid") 2>/dev/null || true
echo "MATRIX END $(date -Is)" | tee -a "$OUT/ledger.log"
echo "--- app results summary ---"
grep -hE 'READ_CR ok|READ_CPC ok|RESULT fail' "$OUT"/B*_app.txt 2>/dev/null | sed 's/^[0-9-]* [0-9:.]* *[0-9]* *[0-9]* I CDAC27_PATH: //' | sort
echo "--- final counters ---"
cat "$OUT/b3_post_qc.txt" 2>/dev/null | grep -E 'file_open_deny|context_push_ok|context_pop_ok|file_open_join|file_open_no_context' | head
'''

STOP = """#!/bin/bash
# stop.sh — stop instance #{inst} only.
set -u
BASE={rundisk}/b{inst}
if [ -d "$BASE/home/bin" ]; then
  STOPBIN="$BASE/home/bin/stop_cvd"; STOPHOST="$BASE/home"
else
  STOPBIN={host}/bin/stop_cvd; STOPHOST={host}
fi
env ANDROID_HOST_OUT="$STOPHOST" ANDROID_PRODUCT_OUT="$BASE/images" \
  CUTTLEFISH_CONFIG_FILE="$BASE/assembly/cuttlefish_config.json" CUTTLEFISH_INSTANCE={inst} \
  HOME="$BASE/home" "$STOPBIN" 2>&1 | tail -3
echo "stop attempted at $(date -Is)"
"""

LEDGER = '''#!/usr/bin/env python3
# build_ledger.py <results_dir> <ino_x> <ino_y> <sdev_x_str> <uidA> <uidB>
import csv, os, re, sys, collections
out=sys.argv[1]; INO_X=sys.argv[2]; INO_Y=sys.argv[3]; SDEV=sys.argv[4]; UIDA=sys.argv[5]; UIDB=sys.argv[6]
RUNID="{runid}"; BOOT="{boot}"; REASONS=({reasons})
blocks={{"B0":["B0_AX_1","B0_AX_2","B0_AX_3","B0_BX_1","B0_BX_2","B0_BX_3"],
 "B1":["B1_AX_1","B1_AX_2","B1_AX_3","B1_BX_1","B1_BX_2","B1_BX_3","B1_AY_1","B1_AY_2","B1_AY_3"],
 "B2":["B2_BX_1","B2_BX_2","B2_BX_3","B2_AX_1","B2_AX_2","B2_AX_3","B2_BY_1","B2_BY_2","B2_BY_3"],
 "B3":["B3_AX_1","B3_AX_2","B3_AX_3","B3_BX_1","B3_BX_2","B3_BX_3"]}}
block_rule={{"B0":None,"B1":"{r1}","B2":"{r2}","B3":None}}
block_expect={{"B0_AX":"allow_orig","B0_BX":"allow_redacted","B1_AX":"deny","B1_BX":"allow_redacted","B1_AY":"allow_orig_y",
 "B2_BX":"deny","B2_AX":"allow_orig","B2_BY":"allow_redacted_y","B3_AX":"allow_orig","B3_BX":"allow_redacted"}}
def read(fn):
    p=os.path.join(out,fn)
    return open(p,encoding="utf-8",errors="replace").read() if os.path.exists(p) else ""
rows=[]
for block,labels in blocks.items():
    for lab in labels:
        app=read(lab+"_app.txt"); fw=read(lab+"_framework.txt")
        m=re.search(r'READ_CPC ok uri=(\\S+) bytes=(\\d+) dev=(\\S+) ino=(\\d+) marker=(\\S+) marker_present=(\\w+) sha256=([0-9a-f]{{64}})',app)
        fail=re.search(r'RESULT fail cmd=read_cpc err=(.+)',app)
        app_result="ALLOW" if m else ("FAIL" if fail else "NO_RESULT")
        app_err=fail.group(1) if fail else ""
        bytes_read=m.group(2) if m else ""
        app_sha=m.group(7) if m else ""
        marker_present=m.group(6) if m else ""
        enter=re.search(r'CDAC_CONTEXT_ENTER context_id=(\\d+) caller_uid=(\\d+) caller_pid=(\\d+) server_pid=(\\d+) server_tid=(\\d+).*?service_id=(\\d+) op_id=(\\d+) operation=(\\S+) transaction_code=(\\d+)',fw)
        pub5=re.search(r'CDAC_FRAMEWORK_CONTEXT_PUBLISH context_id=(\\d+) msg_type=5 .*?service_id=(\\d+) op_id=(\\d+) operation=(\\S+) result=(\\w+)',fw)
        joins=re.findall(r'CDAC_BINDER_VFS_JOIN source=UNIFIED_BINDER_HOOK seq=(\\d+).*?caller_uid=(\\d+).*?service_id=(\\d+) op_id=(\\d+).*?op=(\\S+) file_cookie=(\\d+) ino=(\\d+) s_dev=(\\S+) i_mode=(\\S+) f_flags=(\\S+)',fw)
        decs=re.findall(r'iguard_ctx: decision seq=(\\d+) action=([\\w-]+) matched=(\\d) reason=(\\S+) rule_src=(\\w+) specificity=(\\d+).*?caller_uid=(\\d+).*?operation=(\\S+) path_tail=(\\S+) obj_ino=(\\d+) obj_s_dev=(\\S+) obj_i_mode=(\\S+) obj_f_flags=(\\S+)',fw)
        enforce=re.search(r'real-enforce seq=(\\d+).*?caller_uid=(\\d+) caller_pid=(\\d+) service_id=(\\d+) op_id=(\\d+) service=(\\S+) op=(\\S+) path_tail=(\\S+) errno=(-?\\d+) verdict=(\\S+)',fw)
        dec_match=None
        for d in decs:
            if d[2]=="1": dec_match=d
        enforce_ok=bool(enforce) and enforce.group(9)=='-13' and enforce.group(10)=='deny-now'
        pref=re.sub(r'_\\d+$','',lab)
        exp=block_expect.get(pref,"?")
        verdict=""
        if exp=="deny":
            app_fail_eacces=app_result=="FAIL" and "EACCES" in app_err
            pub5_ok=bool(pub5) and pub5.group(5)=="ok"
            rule_ok=(dec_match is not None and dec_match[3] in REASONS and dec_match[9]==INO_X and dec_match[10]==SDEV)
            verdict="DENY_PASS" if (app_fail_eacces and pub5_ok and rule_ok and enforce_ok and app_result=="FAIL") else "DENY_CHECK"
        elif exp.startswith("allow"):
            verdict="ALLOW_PASS" if (app_result=="ALLOW" and not enforce_ok) else "ALLOW_CHECK"
        else:
            verdict="UNCLASSIFIED"
        rows.append({{"run_id":RUNID,"boot":BOOT,"block":block,"label":lab,
          "rule_version":block_rule[block] or "none",
          "client_pkg":"com.demo.espafdtest" if not lab.startswith(("B0_BX","B1_BX","B2_BX","B2_BY","B3_BX")) else "com.demo.espafdtestb",
          "client_uid":UIDA if not lab.startswith(("B0_BX","B1_BX","B2_BX","B2_BY","B3_BX")) else UIDB,
          "entry":"txn14 openFile","service_id":enter.group(6) if enter else "","op_id":enter.group(7) if enter else "",
          "operation":enter.group(8) if enter else "","context_id":enter.group(1) if enter else "",
          "pub_msg5":pub5.group(5) if pub5 else "","server_pid":enter.group(4) if enter else "","server_tid":enter.group(5) if enter else "",
          "join_count":len(joins),"join_ino":joins[-1][6] if joins else "","join_s_dev":joins[-1][7] if joins else "","join_f_flags":joins[-1][9] if joins else "",
          "matched":dec_match[2] if dec_match else "0","matched_reason":dec_match[3] if dec_match else "",
          "matched_obj":(dec_match[9]+"/"+dec_match[10]) if dec_match else "",
          "real_enforce_errno":enforce.group(9) if enforce else "","real_enforce_verdict":enforce.group(10) if enforce else "",
          "app_result":app_result,"app_err":app_err,
          "fd_delivered":"0" if app_result=="FAIL" else ("1" if app_result=="ALLOW" else "?"),
          "bytes_read":bytes_read,"marker_present":marker_present,"app_sha":app_sha,
          "verdict":verdict,"expect":exp,"app_file":lab+"_app.txt","fw_file":lab+"_framework.txt"}})
with open(os.path.join(out,"PER_REQUEST_LEDGER.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("ledger rows:",len(rows))
print(collections.Counter(r["verdict"] for r in rows))
for r in rows:
    if not r["verdict"].endswith("PASS"):
        print("CHECK:",r["label"],r["verdict"],r["expect"],r["app_result"],r["matched_reason"],r["real_enforce_verdict"],r["pub_msg5"])
'''

for b in BOOTS:
    d=os.path.join(WORK,"runs",b["tag"])
    os.makedirs(d,exist_ok=True)
    ctx=dict(work=WORK, rundisk=RUNDISK, kdir=KDIR, **b)
    ctx["rundir"]="/data2"
    if b["use_hostpkg"]:
        launch=LAUNCH_A15.format(**ctx)
    else:
        launch=LAUNCH_GEN.format(**ctx)
    ctx["policy_src"]=b.get("policy_src", b["fx"]+"/iguardctl_test")
    ctx["apk_a"]=b.get("apk_a", b["fx"]+"/app_a-signed.apk")
    ctx["apk_b"]=b.get("apk_b", b["fx"]+"/app_b-signed.apk")
    open(os.path.join(d,"launch.sh"),"w").write(launch)
    open(os.path.join(d,"wait_boot.sh"),"w").write(WAIT.format(**ctx))
    open(os.path.join(d,"run_preflight.sh"),"w").write(PREFLIGHT.format(**ctx))
    open(os.path.join(d,"run_matrix.sh"),"w").write(MATRIX.format(**ctx))
    open(os.path.join(d,"stop.sh"),"w").write(STOP.format(**ctx))
    reasons='"'+b["r1"]+'","'+b["r2"]+'"'
    ctx["reasons"]=reasons
    ctx["boot"]=f"{b['platform']} comparison_boot_index={b['comp']} ({b['tag']})"
    open(os.path.join(d,"build_ledger.py"),"w").write(LEDGER.format(**ctx))
    for f in ["launch.sh","wait_boot.sh","run_preflight.sh","run_matrix.sh","stop.sh","build_ledger.py"]:
        os.chmod(os.path.join(d,f),0o755)
    print("generated", b["tag"])
