# MISSING_ITEMS.md — 缺失 / 未入包 / 冲突登记

按任务书口径区分：**已入包** / **找到未入包**（原路径+哈希可查，因体积未复制） /
**未找到** / **存在冲突**。不补造历史证据，不修改原始数据。

## 0. 通用
   已读取 WORKSPACE_LAYOUT.md、environments/README.md、source_archives/260918/README.md
   与各归档索引（作为适用说明替代）。

## 1. ESP 配对构建（round 10/11/12）
2. **guest boot_id 未记录（ESP round）= 未找到**。11 轮只保留 host 侧
   launch 时间/pid（runtime/*.log）、每次启动 fresh-userdata 的 X.bin inode
   （setup_history.txt）、kernel.log 文件哈希（10 轮 boot_log_hashes.txt）；
   未保存 `/proc/sys/kernel/random/boot_id` 的值。boot 身份/配对/顺序可由上述
   间接证据重建（见 01_esp_paired/11_perf_paired/04_samples/BOOT_STATE_PAIRING_MAP.csv），
   但不是逐 boot 的 boot_id 记录。（对照：H4 与 RQ4v2 A/B/C 两轮均记录了 boot id。）
3. **p4 首次尝试 200×SecurityException 原始行 = 未找到**。仅
   `04_samples/p4_failed_first_attempt/FAILURE_RECORD.txt` 保留（3 状态 × 200 行
   OPEN_FAIL SecurityException 的说明）；该 boot 的 guest timing CSV 未 pull、
   且 ENOSPC 清理时该运行目录 guest 日志未保留。失败记录单独保留、未混入合法样本；
   有效 Pair4-enabled 由同顺序重试 boot（e_p4_b4_*）补齐。
4. **ESP 预热行未序列化 = 已入包（说明）**。预热 20 行由 APK 执行但不写 CSV
   （MainActivity.java 仅记录 i>warmup 的行）；预热计数见 run_sample.sh 参数
   `--ei warmup 20 --ei record 200`。
5. **12 轮 ERRATA 自列缺口（已保留）**：首次 p2_s0 launch.log（两次失败尝试）、
   连续 df/ENOSPC 快照（满盘时刻仅 ~1 分钟窗口间接界定）、r16 原始 guest 日志
   （磁盘满时未复制成功）。见 12_perf_audit/02_disk_timeline/DISK_TIMELINE.md。
6. **framework logging_mode 对已加载进程不即时生效（已核证并记录）**：
   setup_side.sh 对 com.android.externalstorage 做 force-stop，使 quiet 属性在
   provider 重载时生效；S1 的 ablate_disable_runtime/ctx 为内核 debugfs 布尔、
   逐请求读取，无需进程重启，每块 state_flags.txt 有读回证据。

## 2. SettingsProvider A/B/C（RQ4 v2）
7. **COUNTER_BASELINE_AND_DELTA.csv = 找到未入包**。
   02_boot_1/03_boot_2 各 10.9 MB，为逐 trial 计数器基线/增量审计（辅助证据，
   非计时行）。
8. **PRE_STATE_SNAPSHOTS.csv = 找到未入包**。各 2.6 MB，逐 trial 预状态快照。
9. **LOG_WATERMARK_AUDIT.csv = 找到未入包**。各 1.3 MB。
10. **逐 block 的 configuration.json / cleanup.json / counters_after_workload.json
    = 找到未入包**（约 1000×3 个，合计 ~6 MB）。保留的是每 block 的
    app.csv（原始计时行）、arm_freeze_state.json、arm_freeze_watermark.json、
    policy_dump_after_workload.txt。
    以上文件的原始路径、大小、SHA-256 均登记在 SOURCE_INDEX.csv。
11. **A/B/C 的 IQR 无冻结列 = 已入包（说明）**。冻结分析只输出 median/P95/P99；
    4.059/5.771/5.310 ms 由本轮从 SCIENTIFIC_ROWS.csv 独立重算（type-7 q75−q25）。

## 3. H4 DP
12. **H4 bootstrap 脚本 = 未找到**。目录只保留输出（P0_P1_BOOTSTRAP_CI.md、
    P0_P1_BLOCK_PAIRED_DELTAS.tsv、POOLED_SUMMARY.tsv）；COMMAND_HISTORY.txt 是
    adb 采集命令，无分析脚本。因此 95% CI 无法逐位复算：用冻结 seed 20260628、
    10000 次整块 pooled 重采样，下界 −183755.500 ns 逐位一致，上界为 947051.0 ns
    （冻结 925107.750 ns，差 +0.022 ms）。冻结 CI 保留为权威历史输出，两者都跨零，
    结论不变（见 recompute/outputs/h4_recompute.txt）。
13. **H4 raw/（21 MB 逐块 am_start/status 文本）= 找到未入包**。核心原始计时行
    已全量入包（RAW_SAMPLES.csv 12000 行 + raw_blocks/ 156 个逐块 CSV）。

## 4. 规则规模（round 21）与并发（round 26）
14. **21 轮 04_runtime 镜像/日志（275 MB）、05_correctness 全量 policy_dump
    （6.7 MB）= 找到未入包**。已入包：06_perf_raw 全量 200 个计时 CSV +
    perf_ledger.jsonl ×2 + 每配置 install.json/policy_dump（含 40 个 N128 读回）、
    07_analysis、协议/规则生成器、04_runtime 的 boot_cfg/prep/setup json、
    05_correctness_minimal（csv/jsonl/summary + 代表 policy_dump）。
15. **26 轮 04_runtime（7.3 GB）= 找到未入包**。已入包 05_results 全量
    （PER_REQUEST_LEDGER.csv、OVERLAP_TABLE.csv、wXX app_rows/fw/kern/qc）。
16. **并发批无逐请求应用侧时延 = 存在缺口（如实登记，不补测）**。ledger 只有
    服务端 epoch 时间戳（fw_enter/fw_exit/decision/enforce），无
    elapsedRealtimeNanos 应用侧时延列；归属 160/160 正确（40 DENY_PASS +
    120 ALLOW_PASS）。并发正确性与性能、H4 同补丁空策略与无 CDAC 基线分别报告。

## 5. 构建与来源
17. **12 轮 04_builds 完整 system 树与镜像（7.9 GB）、l_build.log（27 MB）=
    找到未入包**。已入包 nprime_vs_l_tree.diff、两侧 artifact SHA256SUMS.txt、
    android-info/build_fingerprint；l_system_tree/nprime_system_tree/l_artifacts/
    nprime_artifacts 的原始路径/哈希登记在 SOURCE_INDEX.csv。
18. **完整源码树 / 多 GB 镜像一律未复制**（任务书要求）。S0 排除 CDAC 的实际范围
    由 v1 配对工程的“共享文件 1,749,478 字节逐字节一致 + 0 未授权差异 + marker 0”
    审计给出（MATCHED_BUILDS.md），不是把同工件内“关闭裁决”当 CDAC-free。

## 6. 论文表述需要修正的点（不修改论文，仅列出）
19. **pooled P95 锚点 10.80/13.40/14.00/14.60 ms 与精确值不一致**：
    精确值 10.819647/13.423468/14.028540/14.614968 ms，两位小数应为
    10.82/13.42/14.03/14.61 ms。凡引用 10.80/13.40/14.00/14.60 处应更正。
20. **LOG_ON 块中位数“20.8–23.6 ms”与精确值 20.426/23.427 ms 有 <0.4 ms 出入；
    LOG_OFF “6.3–7.0 ms”与精确值 6.213/7.022 ms 有 <0.1 ms 出入**，建议引用
    精确值或一致四舍五入。
21. **fig_runtime_cost.pdf（A/B/C 数据）未被任何打包论文 tex 引用**；当前论文
    RQ4 只使用 fig4_h4_performance_final.pdf + ESP “Pristine matched baseline”
    段 + 规则规模段。若要在正文/附录引用 fig_runtime_cost，需要另行完成全文整合
    （本轮不做）。
22. **任务书“RQ3 性能”与论文章节编号的对应**：当前论文 RQ3=转发边界（10/10），
    性能=RQ4；本包锚点分别落在 evaluation_completed.r34b_baseline.tex 的
    “RQ4: Application-Visible Latency”、“Pristine matched baseline”、
    “Rule-count scaling” 三段。报告时建议按论文真实编号引用。
