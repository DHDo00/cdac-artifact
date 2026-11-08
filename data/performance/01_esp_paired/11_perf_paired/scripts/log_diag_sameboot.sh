#!/usr/bin/env bash
# log_diag_sameboot.sh — same-boot, same-rule-state (S2: no rule) log impact diagnosis.
# Fixed balanced order over 2 rounds: ON, OFF, OFF, ON. Each block: 20 warmup + 30 recorded.
# Records: timing CSV, kernel logcat line/byte counts, host kernel.log byte delta,
# switches readback. Security path (context publish / rule lookup / object check) stays ON.
set -u
ADB=adb; S=0.0.0.0:6528
TREE='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree'
X_URI="$TREE/document/primary%3Aespafd_tree%2FX.bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../01_diag_sameboot"; mkdir -p "$OUT"
sh() { $ADB -s $S shell "$@"; }
set_kernel_log() { # 1|0
  sh "mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true"
  sh "echo $1 > /sys/kernel/debug/iguard/verbose_audit"
}
set_fw_log() { # quiet|audit
  sh "setprop persist.debug.cdac.logging_mode $1"
  sleep 2
}
apply_cfg() { # cfg: on|off
  if [ "$1" = off ]; then set_kernel_log 0; set_fw_log quiet; else set_kernel_log 1; set_fw_log audit; fi
}
readback() {
  local k f
  k=$(sh 'cat /sys/kernel/debug/iguard/verbose_audit' | tr -d '\r')
  f=$(sh 'getprop persist.debug.cdac.logging_mode' | tr -d '\r')
  echo "verbose_audit=$k logging_mode=$f"
}
block() { # block_label cfg outfile
  local label=$1 cfg=$2 outfile=$3
  apply_cfg "$cfg"
  local rb; rb=$(readback)
  sh "$POLICY clear" >/dev/null
  # restore fixture X (outside timing)
  $ADB -s $S shell "am start -W -n com.demo.esptiming/.MainActivity --es action restore --es mode w --es label ${label}_restore --es content 0123456789ABCD -d $X_URI" >/dev/null 2>&1
  sleep 2
  HOSTK0=$(stat -c %s "${RUNTIME}/instance/instances/cvd-9/logs/kernel.log" 2>/dev/null || echo 0)
  sh 'logcat -b kernel -c; logcat -c' >/dev/null 2>&1
  $ADB -s $S shell "am start -W -n com.demo.esptiming/.MainActivity --es action timed --es mode w --es state S2 --es label $label --es content 0123456789ABCD --ei warmup 20 --ei record 30 --es out ${outfile}.csv -d $X_URI" >/dev/null 2>&1
  sleep 4
  HOSTK1=$(stat -c %s "${RUNTIME}/instance/instances/cvd-9/logs/kernel.log" 2>/dev/null || echo 0)
  $ADB -s $S shell "cat /sdcard/Android/data/com.demo.esptiming/files/timing/${outfile}.csv" > "$OUT/${outfile}.csv"
  local kl kb
  kl=$(sh 'logcat -b kernel -d | wc -l' | tr -d '\r')
  kb=$(sh 'logcat -b kernel -d | wc -c' | tr -d '\r')
  local fr
  fr=$(sh 'logcat -d | grep -cE "CDAC_BINDER_ENTRY|CDAC_ENDPOINT_RESOLVE"' | tr -d '\r')
  {
    echo "block=$label cfg=$cfg readback=$rb"
    echo "kernel_logcat_lines=$kl kernel_logcat_bytes=$kb fw_logcat_lines=$fr"
    echo "host_kernel_log_bytes_delta=$((HOSTK1-HOSTK0))"
  } > "$OUT/${label}_counts.txt"
  echo "block $label done rows=$(tail -n +2 "$OUT/${outfile}.csv" | wc -l)"
}
POLICY=/data/local/tmp/iguardctl_test
sh "$POLICY clear" >/dev/null
# fixed balanced order: R1 ON, R1 OFF, R2 OFF, R2 ON
block d1_on on  d1_on
block d1_off off d1_off
block d2_off off d2_off
block d2_on on  d2_on
apply_cfg on
echo "log diagnosis done -> $OUT"
