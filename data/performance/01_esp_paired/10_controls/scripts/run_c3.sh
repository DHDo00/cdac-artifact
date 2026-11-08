#!/usr/bin/env bash
# run_c3.sh — 原生拒绝保持：A 打开其未持有 grant 的 espafd_tree_b/XN.bin。
# 对照 (a) CDAC 机制开、无规则；(b) 判定路径消融（runtime+ctx ablation，
# 静态规则与全部钩子仍保留）。断言原生拒绝不被 CDAC 改写为放行。
set -u
ADB=adb; S=0.0.0.0:6528
POLICY=/data/local/tmp/iguardctl_test
TREEB_URI='content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree_b/document/primary%3Aespafd_tree_b%2FXN.bin'
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../01_controls/results/C3"; mkdir -p "$OUT"
sh() { $ADB -s $S shell "$@"; }
set_ablation() {
  sh "mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true"
  sh "echo $1 > /sys/kernel/debug/iguard/ablate_disable_runtime"
  sh "echo $1 > /sys/kernel/debug/iguard/ablate_disable_ctx"
  local r c
  r=$(sh 'cat /sys/kernel/debug/iguard/ablate_disable_runtime' | tr -d '\r')
  c=$(sh 'cat /sys/kernel/debug/iguard/ablate_disable_ctx' | tr -d '\r')
  local want=$([ "$1" = "1" ] && echo Y || echo N)
  echo "runtime=$r ctx=$c want=$want"
  if [ "$r" != "$want" ] || [ "$c" != "$want" ]; then echo "ABLATION_APPLY_FAILED want=$want got=$r/$c"; exit 2; fi
}
sh "$POLICY clear" > "$OUT/policy_clear_before.txt"
# (a) CDAC on, no rule
sh 'logcat -c; logcat -b kernel -c'
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action write --es mode w --es label c3_native_on --es content C3-NATIVE-AAAA -d $TREEB_URI" >/dev/null 2>&1
sleep 2
$ADB -s $S shell 'run-as com.demo.espafdtest cat files/c3_native_on.csv' > "$OUT/c3_on_app.csv" 2>/dev/null
sh 'logcat -b kernel -d | grep -E "service_id=5 op_id=401|real-enforce|decision action" | tail -8' > "$OUT/c3_on_kernel.txt"
sh 'dumpsys activity providers 2>/dev/null | grep -c iguard' > /dev/null || true
# (b) decision-path ablation (runtime policy + ctx publish off; hooks remain)
set_ablation 1 | tee "$OUT/ablation_state.txt"
sh 'logcat -c; logcat -b kernel -c'
$ADB -s $S shell "am start -W -n com.demo.espafdtest/.MainActivity --es action write --es mode w --es label c3_native_ablated --es content C3-ABLATE-AAAA -d $TREEB_URI" >/dev/null 2>&1
sleep 2
$ADB -s $S shell 'run-as com.demo.espafdtest cat files/c3_native_ablated.csv' > "$OUT/c3_ablated_app.csv" 2>/dev/null
sh 'logcat -b kernel -d | grep -E "service_id=5 op_id=401|real-enforce|decision action|ablation" | tail -12' > "$OUT/c3_ablated_kernel.txt"
# restore ablation off
set_ablation 0 | tee -a "$OUT/ablation_state.txt"
sh "$POLICY clear" > "$OUT/policy_clear_after.txt"
echo "C3 done -> $OUT"
