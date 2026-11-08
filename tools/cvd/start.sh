#!/usr/bin/env bash
# Launch an isolated copy using the configuration checked on 2026-09-18.
set -euo pipefail
if [[ $# != 2 ]]; then
  echo "Usage: $0 experimental|baseline /absolute/path/to/new/runtime" >&2
  exit 2
fi
mode="$1"
runtime="$2"
[[ "$runtime" == /* && ! -e "$runtime" ]] || { echo 'Use a new absolute runtime path.' >&2; exit 2; }
runtime="$(realpath -m -- "$runtime")"
if pgrep -x run_cvd >/dev/null; then
  echo 'An existing CVD is running; stop it before using instance 9.' >&2
  exit 2
fi
kernel_args=()
case "$mode" in
  experimental)
    source_root=aosp16
    product=cdac_matched_stripped_baseline_v1_20260818/source_enabled/android/out_matched_baseline/target/product/vsoc_x86_64_only
    kernel_dir=cdac_matched_stripped_baseline_v1_20260818/03_artifacts/kernel_enabled_dist
    kernel_args=(--kernel_path="$kernel_dir/bzImage" --initramfs_path="$kernel_dir/initramfs.img")
    ;;
  baseline)
    source_root=aosp_16_stock_perf_20260903_132126
    product="$source_root/out/target/product/vsoc_x86_64_only"
    ;;
  *) echo 'Choose experimental or baseline.' >&2; exit 2 ;;
esac
host="$source_root/out/host/linux-x86"
mkdir -p "$runtime/images" "$runtime/assembly" "$runtime/instance" "$runtime/early_tmp"
while IFS= read -r -d '' artifact; do
  cp --reflink=auto --sparse=always --preserve=mode,timestamps "$artifact" "$runtime/images/"
done < <(find "$product" -maxdepth 1 -type f ! -name '*.lock' ! -name userdata.img -print0)
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
for ((attempt=0; attempt<96; attempt++)); do
  "$adb_bin" connect 0.0.0.0:6528 >/dev/null 2>&1 || true
  completed="$(timeout 10 "$adb_bin" -s 0.0.0.0:6528 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  if [[ "$completed" == 1 ]]; then
    printf 'BOOT_COMPLETED=1\n' > "$runtime/boot_status.txt"
    echo "Started $mode. ADB: 0.0.0.0:6528. Log: $runtime/launch.log"
    echo "Stop: bash environments/stop.sh '$runtime'"
    exit 0
  fi
  if ! kill -0 "$launch_pid" 2>/dev/null; then
    break
  fi
  sleep 5
done
echo "Boot check failed. See $runtime/launch.log" >&2
bash environments/stop.sh "$runtime" || true
exit 1
