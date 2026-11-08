# CDAC 性能评估最终报告 — 日志诊断 + 配置冻结 + 4 对多启动测量（2026-10-24）

目录：11_perf_paired_20261024/（独立；历史制品/记录/统计未改）。
实例：诊断 enabled boot + 4×enabled + 4×stripped（共 9 次启动），全部经
session-holder 稳定运行，SELinux Enforcing，配对顺序按冻结协议交替。

## 直接回答

### 1. 日志是否解释了此前明显变慢，解释到什么程度？
- 是，几乎全部。同一 enabled 启动、同一规则状态（S2 无规则）、同一 APK 与合法写：
  LOG_ON（kernel verbose_audit=Y + framework audit）块中位数 20.8–23.6ms、
  每 30 请求写内核控制台 ~1.4MB（≈46KB/请求）；LOG_OFF（verbose_audit=N）块
  中位数 6.3–7.0ms、控制台量 ~44KB/30 请求（≈96% 减少）。
- 解释程度：此前 28.6ms vs 6.33ms 的 ~22ms 差距中，~15–17ms 是内核观测日志
  （生成、格式化与控制台输出同时关闭，非仅停采集）；剩余 ~2–3ms 为真实机制
  成本（与多启动 S0 对照一致）。framework 侧日志（logcat）在诊断中未显示可测
  影响（kernel-off 后即达 S0 水平，framework 文本行仍在流）。
- 门控审计：内核每请求 CDAC 日志全部由 verbose_audit 控制（iguard_vinfo 短路
  + binder.c/iguard_ctx.c 显式 gating）；framework 由 persist.debug.cdac.logging_mode
  控制（quiet 跳过每次尝试的 Log.i，保留计数与 /dev/iguard_ctl 发布）。实测
  framework 属性对已加载 provider 进程不即时生效（callback 未触发），正式 boot
  中每 200 请求仍有 ~442 行 framework CDAC 文本；因其成本未测出，如实保留并记录。

### 2. 性能配置下安全功能是否保持？
- 保持。LOG_OFF 下最小功能检查：A+X 规则 → App FNF 且 quiet_counters
  file_open_deny 0→1；同规则 B→X 成功；clear 后 A 恢复成功；context push/pop
  计数全程平衡（fail=0）。上下文发布、规则查找、对象检查、真实拒止均在。
- S1 的消融开关只关运行时规则查找与上下文发布，静态机制与全部钩子仍保留。

### 3. 匹配多启动条件下的额外耗时是多少？
（4 对启动，每状态每 boot 预热 20 + 记录 200；中位数，type-7 分位）
- S0（完全无 CDAC）逐 boot 中位数：3.33 / 2.71 / 3.13 / 3.03 ms。
- S2（完整 CDAC，无规则）逐 boot 中位数：5.55 / 6.67 / 5.29 / 5.58 ms；
  对 S0 的绝对差异 2.23 / 3.96 / 2.16 / 2.55 ms（均值 2.72ms），
  相对 1.67 / 2.46 / 1.69 / 1.84（均值 1.92×）。
- S3（完整 CDAC，含规则，合法请求不命中拒绝规则）：5.21 / 5.73 / 5.55 / 4.75 ms；
  差异 1.89 / 3.02 / 2.42 / 1.71 ms（均值 2.26ms），相对均值 1.76×。
- S1（部分消融，辅助解释）：6.54 / 7.13 / 5.46 / 6.00 ms；差异均值 3.23ms。
- 结论：**主部署成本以 S0→S2 计，约为 +2.2–2.7ms（中位数，约 1.9×）**；
  S1 未比 S2 更快，说明剩余成本主要不在运行时规则查找或调用者上下文发布，
  而在所有 enabled 状态共有的钩子/审计机制。S2 与 S3 中位数接近且 3/4 对中
  S3≤S2，差异在启动噪声内——**在本实验精度下未分辨**，不表述为零成本。

### 4. 结果的波动和限制是什么？
- 波动：S0 boot 间中位数 2.71–3.33ms（~19% 相对差）；S2 boot 间 5.29–6.67ms；
  P95 各 boot 10.3–17.4ms。同 boot 内 200 请求不是独立系统重复，跨 boot 才是
  波动主来源。
- 限制：仅 4 对启动（小样本，无正式置信区间，逐 pair 报告全部分布）；单一
  ESP 写路径/单文件/单授权/单 APK；LOG_OFF 固定（kernel quiet），framework
  quiet 未完全生效（~442 文本行/200 请求，未测出影响）；p4 的 enabled 首启
  因 SAF 自动化失败被判无效（200×SecurityException 全部保留），由同顺序重试
  boot 补齐，失败记录单独保存。合并样本（pooled）P95 与各 boot P95 分别列出
  （pooled S0 10.82ms / S2 14.03ms / S3 14.61ms），不混用。
- decision_ns / policy add-clear cost 单独保存（内部成本），未计入应用开销。

### 5. 是否已经足以回应审稿人的真实性能基线问题？
- 对“ESP 写路径正常请求的相对部署开销”这一核心问题：已具备可回答证据——
  同基础配对构建、两侧启动审计、日志影响已分离、4 对交替多启动、每状态
  n=200×4。审稿口径建议：正常请求中位数额外开销约 +2.3ms（S2 对 S0，跨 boot
  范围 2.2–2.7ms，相对约 1.9×），并明确“S2 与 S3 未分辨、S1 不更快”的组成
  事实；同时声明 4 对与单工作负载的小样本限制。
- 尚不满足（不宣称）：稳定 P95、正式置信区间、更多端点/规模、拒绝路径计时
  （本轮未测）。这些列为后续正式性能实验，本轮不扩大。

## 交付物
- 00_log_audit/LOG_GATING_AUDIT.md（门控审计：无需内核补丁）
- 01_diag_sameboot/（同 boot ON/OFF 对照 4 块×30 + 日志条数/字节）
- 02_function_check/（LOG_OFF 下最小功能检查与 quiet_counters 增量）
- 03_protocol_frozen/PERF_PROTOCOL.md（正式采集前冻结）
- 04_samples/（16 个有效状态块 + p4 失败记录；全部原始 CSV）
- 05_stats/analyze.py、analysis.txt、per_boot_stats.json、pair_rows.json
- runtime/：启动日志、setup 历史、boot 顺序与哈希
- 06_final/：本报告、FINAL_STATUS、SHA256SUMS

## 修改清单与耗时（墙钟，单人）
- 新增 11_perf_paired_20261024 全部文件；未改历史目录/制品/统计；无平台构建、
  无 APK 重建（复用 esp-timing-signed 8ca8cd21… 与配对制品）。
- 日志审计与诊断 ~1.2h；协议冻结 ~0.2h；9 次启动（安装/授权/稳定/采样）
  ~3.2h（含 p4 一次失败重试）；统计与报告 ~0.6h；磁盘清理与记录 ~0.3h。
  合计约 5.5h。
- 注意：root 文件系统曾 100% 满，清理了本轮及前几轮运行目录的 images/userdata
  （保留日志到 logs_archive）；r16 的 logs_archive 因当时磁盘满未复制成功，
  其原始 guest 日志未保留（诊断内容已见于 09 轮记录），如实登记。
