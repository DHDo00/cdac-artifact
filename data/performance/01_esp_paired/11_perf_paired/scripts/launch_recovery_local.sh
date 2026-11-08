#!/usr/bin/env bash
# launch_recovery_local.sh (2026-10-23, this round ONLY; original scripts untouched)
# Based on 04_runtime/launch_sidefx_local.sh. Artifacts, kernel args, SELinux and
# all guest-side security config are UNCHANGED. Changes vs original (one factor):
#   - boot-wait logic no longer breaks/kills the instance when launch_cvd's
#     FOREGROUND component exits after boot complete (normal with --daemon;
#     the daemon run_cvd keeps the VM alive).
#   - waits up to 60s AFTER the VIRTUAL_DEVICE_BOOT_COMPLETED marker for adb
#     before diagnosing "guest booted but adb unreachable" and stopping cleanly.
#   - stops immediately only on VIRTUAL_DEVICE_BOOT_FAILED.
#   - records a per-attempt attempt.log.
set -euo pipefail
if [[ $# != 2 ]]; then
  echo "Usage: $0 /absolute/path/to/new/runtime /absolute/path/to/attempt.log" >&2
  exit 2
fi
runtime="$1"; attempt_log="$2"
[[ "$runtime" == /* && ! -e "$runtime" ]] || { echo 'Use a new absolute runtime path.' >&2; exit 2; }
runtime="$(realpath -m -- "$runtime")"
if pgrep -x run_cvd >/dev/null; then
  echo 'An existing CVD is running; stop it before using instance 9.' >&2
  exit 2
fi
source_root=aosp16
product=cdac_esp_endpoint_validation_20261022/02_build/android_matchedimg_newsystem
kernel_dir=cdac_esp_endpoint_validation_20261022/02_build/kernel_esp_dist
kernel_args=(--kernel_path="$kernel_dir/bzImage" --initramfs_path="$kernel_dir/initramfs.img")
host="$source_root/out/host/linux-x86"
mkdir -p "$runtime/images" "$runtime/assembly" "$runtime/instance" "$runtime/early_tmp"
while IFS= read -r -d '' artifact; do
  cp --reflink=auto --sparse=always --preserve=mode,timestamps "$artifact" "$runtime/images/"
done < <(find "$product" -maxdepth 1 -type f ! -name '*.lock' ! -name userdata.img -print0)
mkdir -p "$runtime/instance/instances/cvd-9"
truncate -s 8589934592 "$runtime/instance/instances/cvd-9/userdata.img"
global_config=$HOME/.cuttlefish_config.json
saved_config="$runtime/previous-global-config-link"
if [[ -e "$global_config" || -L "$global_config" ]]; then
  [[ -L "$global_config" ]] || { echo 'Global config is not a symlink; refusing to replace it.' >&2; exit 2; }
  mv "$global_config" "$saved_config"
fi
restore_config() {
  if [[ -L "$global_config" && "$(readlink "$global_config")" == "$runtime/"* ]]; then
    unlink "$global_config"
  fi
  if [[ -L "$saved_config" && ! -e "$global_config" && ! -L "$global_config" ]]; then
    mv "$saved_config" "$global_config"
  fi
}
trap restore_config EXIT
printf '%s\n' "$source_root" > "$runtime/source-root.txt"
printf '%s\n' "$product" > "$runtime/product-source.txt"
start_ns=$(date +%s%N)
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
  --data_policy=always_create --blank_data_image_mb=4096 \
  --system_image_dir="$runtime/images" --assembly_dir="$runtime/assembly" \
  --instance_dir="$runtime/instance" --early_tmp_dir="$runtime/early_tmp" \
  "${kernel_args[@]}" > "$runtime/launch.log" 2>&1 &
launch_pid=$!
printf '%s\n' "$launch_pid" > "$runtime/launch.pid"
adb_bin=adb
{
  echo "attempt_start=$(date -Is)"
  echo "runtime=$runtime"
  echo "launch_pid=$launch_pid"
} >> "$attempt_log"
post_boot_seen=0
post_boot_wait=0
for ((attempt=0; attempt<96; attempt++)); do
  "$adb_bin" connect 0.0.0.0:6528 >/dev/null 2>&1 || true
  completed="$(timeout 10 "$adb_bin" -s 0.0.0.0:6528 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  if [[ "$completed" == 1 ]]; then
    printf 'BOOT_COMPLETED=1\n' > "$runtime/boot_status.txt"
    echo "attempt_end=$(date -Is) RESULT=ADB_OK attempts=$attempt" >> "$attempt_log"
    echo "Started recovery instance. ADB: 0.0.0.0:6528. Log: $runtime/launch.log"
    echo "Stop: bash environments/stop.sh '$runtime'"
    exit 0
  fi
  if grep -q "VIRTUAL_DEVICE_BOOT_FAILED" "$runtime/launch.log" 2>/dev/null; then
    echo "attempt_end=$(date -Is) RESULT=BOOT_FAILED attempts=$attempt" >> "$attempt_log"
    echo "VIRTUAL_DEVICE_BOOT_FAILED detected; stopping." >&2
    bash environments/stop.sh "$runtime" || true
    exit 1
  fi
  if [[ $post_boot_seen == 0 ]] && grep -q "VIRTUAL_DEVICE_BOOT_COMPLETED" "$runtime/launch.log" 2>/dev/null; then
    post_boot_seen=1
  fi
  if [[ $post_boot_seen == 1 ]]; then
    post_boot_wait=$((post_boot_wait+1))
    if [[ $post_boot_wait -ge 12 ]]; then
      echo "attempt_end=$(date -Is) RESULT=GUEST_BOOTED_ADB_UNREACHABLE post_boot_wait=$post_boot_wait" >> "$attempt_log"
      echo "Guest boot completed but adb unreachable (AdbdStarted-event loss suspected). Stopping." >&2
      bash environments/stop.sh "$runtime" || true
      exit 1
    fi
  fi
  sleep 5
done
echo "attempt_end=$(date -Is) RESULT=TIMEOUT attempts=96" >> "$attempt_log"
echo "Boot check timed out. See $runtime/launch.log" >&2
bash environments/stop.sh "$runtime" || true
exit 1
