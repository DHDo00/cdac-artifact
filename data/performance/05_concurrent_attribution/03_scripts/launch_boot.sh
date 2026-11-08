#!/usr/bin/env bash
# launch_boot.sh <runtime> <attempt_log> — boot cvd-26 on validated ESP 5/401 artifacts.
# Does NOT touch ~/.cuttlefish_config.json (coordinated with other rounds); holds session alive.
set -euo pipefail
runtime=$1; attempt_log=$2
[[ "$runtime" == /* ]] || { echo 'absolute runtime path required'; exit 2; }
runtime="$(realpath -m -- "$runtime")"
if pgrep -af "run_cvd" | grep -q "base_instance_num=26"; then echo 'cvd-26 already running'; exit 2; fi
source_root=aosp16
product=cdac_esp_endpoint_validation_20261022/02_build/android_matchedimg_newsystem
kernel_dir=cdac_esp_endpoint_validation_20261022/02_build/kernel_esp_dist
host="$source_root/out/host/linux-x86"
kernel_args=(--kernel_path="$kernel_dir/bzImage" --initramfs_path="$kernel_dir/initramfs.img")
mkdir -p "$runtime/images" "$runtime/assembly" "$runtime/instance" "$runtime/early_tmp"
while IFS= read -r -d '' artifact; do
  cp --reflink=auto --sparse=always --preserve=mode,timestamps "$artifact" "$runtime/images/"
done < <(find "$product" -maxdepth 1 -type f ! -name '*.lock' ! -name userdata.img -print0)
mkdir -p "$runtime/instance/instances/cvd-26"
truncate -s 8589934592 "$runtime/instance/instances/cvd-26/userdata.img"
printf '%s\n' "$source_root" > "$runtime/source-root.txt"
printf '%s\n' "$product" > "$runtime/product-source.txt"
env ANDROID_HOST_OUT="$host" ANDROID_PRODUCT_OUT="$runtime/images" \
  CUTTLEFISH_CONFIG_FILE="$runtime/assembly/cuttlefish_config.json" CUTTLEFISH_INSTANCE=26 \
  "$host/bin/launch_cvd" \
  --report_anonymous_usage_stats=n --base_instance_num=26 --num_instances=1 \
  --resume=false --daemon --cpus=4 --memory_mb=4096 --smt=false \
  --gpu_mode=guest_swiftshader --hwcomposer=none --enable_audio=false \
  --start_webrtc=false --netsim=false --netsim_bt=false --netsim_uwb=false \
  --enable_host_bluetooth=true --enable_host_nfc=false --enable_host_uwb=false \
  --enable_wifi=false --enable_tap_devices=false --enable_modem_simulator=false \
  --start_gnss_proxy=false --use_sdcard=false --setupwizard_mode=DISABLED \
  --data_policy=always_create --blank_data_image_mb=4096 \
  --system_image_dir="$runtime/images" --assembly_dir="$runtime/assembly" \
  --instance_dir="$runtime/instance" --early_tmp_dir="$runtime/early_tmp" \
  "${kernel_args[@]}" > "$runtime/launch.log" 2>&1 &
launch_pid=$!
printf '%s\n' "$launch_pid" > "$runtime/launch.pid"
{
  echo "attempt_start=$(date -Is)"; echo "runtime=$runtime"; echo "launch_pid=$launch_pid"
  echo "side=enabled_esp_5_401 instance=26"
} >> "$attempt_log"
adb_bin=adb
booted=0
for ((attempt=0; attempt<120; attempt++)); do
  "$adb_bin" connect 0.0.0.0:6545 >/dev/null 2>&1 || true
  completed="$(timeout 10 "$adb_bin" -s 0.0.0.0:6545 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  if [[ "$completed" == 1 ]]; then
    printf 'BOOT_COMPLETED=1\n' > "$runtime/boot_status.txt"
    echo "attempt_end=$(date -Is) RESULT=ADB_OK attempts=$attempt" >> "$attempt_log"
    booted=1
    break
  fi
  if grep -q "VIRTUAL_DEVICE_BOOT_FAILED" "$runtime/launch.log" 2>/dev/null; then
    echo "attempt_end=$(date -Is) RESULT=BOOT_FAILED" >> "$attempt_log"; break
  fi
  sleep 5
done
if [[ $booted == 0 ]]; then echo "attempt_end=$(date -Is) RESULT=TIMEOUT" >> "$attempt_log"; fi
while :; do sleep 30; done
