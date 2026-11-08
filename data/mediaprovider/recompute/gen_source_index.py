#!/usr/bin/env python3
"""Generate SOURCE_INDEX.csv for round 39: deliverable-level index (raw request
files are summarized per boot/dir rather than one row per file)."""
import csv, sys
from pathlib import Path

def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "39_mediaprovider_matrix_replication_20261029_230000")
    rows = [
        ("FINAL_REPORT.md", "结论、实际分母、逐 boot 结果、十项问答、偏离与缺口", "final"),
        ("PROTOCOL.md", "冻结协议（顶层副本）", "protocol"),
        ("04_protocol/PROTOCOL_FROZEN.md", "冻结协议（4 条规则全文、矩阵、判定 oracle）", "protocol"),
        ("04_protocol/PROTOCOL_AMENDMENT_20261029T2310.md", "执行顺序勘误（L 先于 M；非机制改动）", "protocol"),
        ("SCHEDULE.csv", "冻结排程 1,080 行；种子 2026102939", "schedule"),
        ("BUILD_PROVENANCE.md", "构建来源、运行时属性、与历史构建关系", "build"),
        ("BOOT_LEDGER.csv", "boot_id/fingerprint/UID/ino/URI/全量日志路径与哈希", "ledger"),
        ("REQUEST_LEDGER.csv", "全部实际调用（正式+预检+恢复；scientific 标记）", "ledger"),
        ("EVIDENCE_MAP.csv", "request id → 证据路径/行号与完整性状态", "evidence"),
        ("EXCLUSIONS.csv", "排除记录（零数据行）", "ledger"),
        ("FAILURES.md", "失败/异常/重试/超时（零项）", "ledger"),
        ("MISSING_ITEMS.md", "缺失项登记", "ledger"),
        ("summary/table7_per_boot.csv", "表 VII 逐 boot 计数", "summary"),
        ("summary/table7_pooled.csv", "表 VII pooled 计数", "summary"),
        ("summary/table8_per_boot.csv", "表 VIII 逐 boot 计数", "summary"),
        ("summary/table8_pooled.csv", "表 VIII pooled 计数", "summary"),
        ("tables_replacement.tex", "两张候选替换表 + 中英文结果段（不改主论文）", "paper"),
        ("analysis/requests_verified.csv", "1,080 条由 raw 重新判定的请求明细", "analysis"),
        ("analysis/checks.json", "离线复算结构检查（重复/加总/runner 对照）", "analysis"),
        ("recompute/gen_schedule.py", "排程生成器（离线可复现）", "script"),
        ("recompute/analyze.py", "逐请求离线复算与汇总（只读 raw）", "script"),
        ("recompute/pool_ledger.py", "ledger/EVIDENCE_MAP/BOOT_LEDGER 汇总", "script"),
        ("recompute/gen_tables_tex.py", "tables_replacement.tex 生成器", "script"),
        ("recompute/run_all.sh", "离线复算入口（解压后可直接运行）", "script"),
        ("06_runtime/run_boot.py", "采集 runner（adb 全部显式 -s serial）", "script"),
        ("06_runtime/launch_boot.sh", "cvd-39 启动脚本（C19 制品只读复用）", "script"),
        ("06_runtime/stop_boot.sh", "cvd-39 停止脚本", "script"),
        ("06_runtime/attempts.log", "启动尝试记录（3/3 ADB_OK）", "runtime"),
        ("05_fixtures/app_a/src/com/demo/espafdtest/MainActivity.java", "caller A 客户端源码（reqid 观测字段）", "source"),
        ("05_fixtures/app_a/src/com/demo/espafdtest/MainActivity.java.reqid.diff", "caller A 与历史源码逐行 diff", "source"),
        ("05_fixtures/app_b/src/com/demo/espafdtestb/MainActivity.java", "caller B 客户端源码", "source"),
        ("05_fixtures/app_b/src/com/demo/espafdtestb/MainActivity.java.reqid.diff", "caller B diff", "source"),
        ("05_fixtures/app_a/build/app_a-signed.apk", "caller A APK（冻结 sha）", "apk"),
        ("05_fixtures/app_b/build/app_b-signed.apk", "caller B APK（冻结 sha）", "apk"),
        ("05_fixtures/CLIENT_CHANGE_RECORD.md", "客户端变更与语义不变核对", "source"),
        ("05_fixtures/make_app_sources.py", "客户端源码生成器", "script"),
        ("05_fixtures/build_apks.sh", "APK 构建脚本", "script"),
        ("05_fixtures/FIXTURE_SHA256.txt", "夹具哈希", "hash"),
        ("05_artifacts/iguardctl_test", "策略工具（冻结 sha）", "artifact"),
        ("FREEZE_MANIFEST.txt", "采样前冻结输入 SHA-256", "hash"),
        ("SHA256SUMS.txt", "归档内容哈希清单（自外排除）", "hash"),
        ("01_audit/EXISTING_MEDIA_EVIDENCE_AUDIT.md", "历史 30/48 次批次定位与核对", "audit"),
        ("02_source_semantics/SOURCE_SEMANTICS.md", "API→Binder→标签→Provider→决策点映射", "audit"),
        ("00_inputs/INPUT_AND_VERSION_CHECK.md", "输入与环境核验", "audit"),
        ("03_preflight/PREFLIGHT_EVIDENCE.md", "预检证据位置与结论", "audit"),
        ("08_conclusions/RESULT_AND_LIMITATIONS.md", "结论与限制", "audit"),
    ]
    for b in (1, 2, 3):
        raw = root / "07_results" / f"boot{b}" / "raw"
        n_app = len(list(raw.glob("*-app" ))) + len(list(raw.glob("*_app.txt")))
        rows.append((f"07_results/boot{b}/raw/", f"boot{b} 逐请求原始证据（app/framework/kernel/am/backing/规则/计数；{n_app} 个请求窗口）", "raw"))
        rows.append((f"07_results/boot{b}/boot_ledger.csv", f"boot{b} 每请求记账（runner 侧）", "raw"))
        rows.append((f"07_results/boot{b}/objects.json", f"boot{b} UID/URI/backing/ino 对象记录", "raw"))
        rows.append((f"07_results/boot{b}/device_info/", f"boot{b} 设备属性/域/计数器", "raw"))
        rows.append((f"07_results/boot{b}/full_logcat.txt", f"boot{b} 完整 logcat（服务器侧；哈希见 BOOT_LEDGER.csv）", "raw"))
        rows.append((f"07_results/boot{b}/full_dmesg.txt", f"boot{b} 完整 dmesg（服务器侧）", "raw"))
    with open(root / "SOURCE_INDEX.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "description", "category"])
        w.writerows(rows)
    print(f"wrote {len(rows)} index rows")

if __name__ == "__main__":
    main()
