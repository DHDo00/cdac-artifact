#!/usr/bin/env bash
# launch_perf_common.sh <enabled|stripped> <runtime> <attempt_log> <first_boot>
# Boot an enabled or stripped perf side. first_boot=1 provisions a blank userdata
# (always_create); first_boot=0 REUSES the existing per-instance userdata.img
# (data_policy=use_existing) so SAF grants/apps/fixture persist across boots of the
# same side (reboot, not factory-reset). session-holder required externally.
set -euo pipefail
SIDE=$1; runtime=$2; attempt_log=$3; FIRST=$4
[[ "$runtime" == /* ]] || { echo 'absolute runtime path required'; exit 2; }
if [[ $FIRST == 1 ]]; then [[ ! -e "$runtime" ]] || { echo 'first boot needs a new runtime dir'; exit 2; }; fi
runtime="$(realpath -m -- "$runtime")"
if pgrep -x run_cvd >/dev/null; then echo 'an existing CVD is running'; exit 2; fi
if [[ $SIDE == enabled ]]; then
  source_root=aosp16
  product=cdac_esp_endpoint_validation_20261022/02_build/android_matchedimg_newsystem
  kernel_dir=cdac_esp_endpoint_validation_20261022/02_build/kernel_esp_dist
  host="$source_root/out/host/linux-x86"
  kernel_args=(--kernel_path="$kernel_dir/bzImage" --initramfs_path="$kernel_dir/initramfs.img")
else
  V1=cdac_matched_stripped_baseline_v1_20260818
  source_root=$V1/source_stripped/android
  product=$V1/source_stripped/android/out_matched_baseline/target/product/vsoc_x86_64_only
  kernel_dir=$V1/03_artifacts/kernel_stripped_dist
  host="$source_root/out_matched_baseline/host/linux-x86"
  kernel_args=(--kernel_path="$kernel_dir/bzImage" --initramfs_path="$kernel_dir/initramfs.img")
fi
mkdir -p "$runtime/images" "$runtime/assembly" "$runtime/instance" "$runtime/early_tmp"
while IFS= read -r -d '' artifact; do
  cp --reflink=auto --sparse=always --preserve=mode,timestamps "$artifact" "$runtime/images/"
done < <(find "$product" -maxdepth 1 -type f ! -name '*.lock' ! -name userdata.img -print0)
mkdir -p "$runtime/instance/instances/cvd-9"
if [[ $FIRST == 1 ]]; then
  truncate -s 8589934592 "$runtime/instance/instances/cvd-9/userdata.img"
  data_policy=always_create
else
  data_policy=use_existing
fi
global_config=$HOME/.cuttlefish_config.json
saved_config="$runtime/previous-global-config-link"
if [[ -e "$global_config" || -L "$global_config" ]]; then
  [[ -L "$global_config" ]] || { echo 'global config is not a symlink'; exit 2; }
  mv "$global_config" "$saved_config"
fi
restore_config() {
  if [[ -L "$global_config" && "$(readlink "$global_config")" == "$runtime/"* ]]; then unlink "$global_config"; fi
  if [[ -L "$saved_config" && ! -e "$global_config" && ! -L "$global_config" ]]; then mv "$saved_config" "$global_config"; fi
}
trap restore_config EXIT
printf '%s\n' "$source_root" > "$runtime/source-root.txt"
printf '%s\n' "$product" > "$runtime/product-source.txt"
env ANDROID_HOST_OUT="$host" ANDROID_PRODUCT_OUT="$runtime/images" \
  CUTTLEFISH_CONFIG_FILE="$runtime/assembly/cuttlefish_config.json" CUTTLEFISH_INSTANCE=9 \
  "$host/bin/launch_cvd" \
  --report_anonymous_usage_stats=n --base_instance_num=9 --num_instances=1 \
  --resume=false --daemon --cpus=4 --memory_mb=4096 --smt=false \
  --gpu_mode=guest_swiftshader --hwcomposer=none --enable_audio=false \
  --start_webrtc=false --netsim=false --netsim_bt=false --netsim_uwb=false \
  --enable_host_bluetooth=true --enable_host_nfc=false --enable_host_uwb=false \
  --enable_wifi=false --enable_tap_devices=false --enable_modem_simulator=false \
  --start_gnss_proxy=false --use_sdcard=false --setupwizard_mode=DISABLED \
  --data_policy=$data_policy --blank_data_image_mb=4096 \
  --system_image_dir="$runtime/images" --assembly_dir="$runtime/assembly" \
  --instance_dir="$runtime/instance" --early_tmp_dir="$runtime/early_tmp" \
  "${kernel_args[@]}" > "$runtime/launch.log" 2>&1 &
launch_pid=$!
printf '%s\n' "$launch_pid" > "$runtime/launch.pid"
{
  echo "attempt_start=$(date -Is)"; echo "runtime=$runtime"; echo "launch_pid=$launch_pid"
  echo "side=$SIDE first_boot=$FIRST data_policy=$data_policy"
} >> "$attempt_log"
adb_bin=adb
post_boot_seen=0; post_boot_wait=0
for ((attempt=0; attempt<96; attempt++)); do
  "$adb_bin" connect 0.0.0.0:6528 >/dev/null 2>&1 || true
  completed="$(timeout 10 "$adb_bin" -s 0.0.0.0:6528 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  if [[ "$completed" == 1 ]]; then
    printf 'BOOT_COMPLETED=1\n' > "$runtime/boot_status.txt"
    echo "attempt_end=$(date -Is) RESULT=ADB_OK attempts=$attempt" >> "$attempt_log"
    echo "Started $SIDE perf instance (first_boot=$FIRST). ADB: 0.0.0.0:6528"
    exit 0
  fi
  if grep -q "VIRTUAL_DEVICE_BOOT_FAILED" "$runtime/launch.log" 2>/dev/null; then
    echo "attempt_end=$(date -Is) RESULT=BOOT_FAILED attempts=$attempt" >> "$attempt_log"
    exit 1
  fi
  if [[ $post_boot_seen == 0 ]] && grep -q "VIRTUAL_DEVICE_BOOT_COMPLETED" "$runtime/launch.log" 2>/dev/null; then post_boot_seen=1; fi
  if [[ $post_boot_seen == 1 ]]; then
    post_boot_wait=$((post_boot_wait+1))
    if [[ $post_boot_wait -ge 12 ]]; then echo "attempt_end=$(date -Is) RESULT=GUEST_BOOTED_ADB_UNREACHABLE" >> "$attempt_log"; exit 1; fi
  fi
  sleep 5
done
echo "attempt_end=$(date -Is) RESULT=TIMEOUT" >> "$attempt_log"
exit 1
