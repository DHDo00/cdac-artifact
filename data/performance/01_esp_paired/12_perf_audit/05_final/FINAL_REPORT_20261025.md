# 性能核对 + 机制比较最终报告（2026-10-25）

目录：12_perf_audit_mech_compare_20261025/（独立；历史报告/数据/统计未覆盖）。

## 一、性能汇总修正后是什么？
由 11 轮原始 CSV 独立重算（01_stats_recompute/recompute.py，type-7 分位）：
- 每 pair S2−S0（中位数差 ns）：2225950 / 3961812 / 2161134 / 2550305；
  **均值 +2724800ns（+2.72ms）**；范围 2.16–3.96ms；配对比值 1.669/2.464/
  1.691/1.841，配对比值均值 1.916（比值之均值 1.894）。
- S3−S0：1886152 / 3024278 / 2424583 / 1714802；**均值 +2262454ns（+2.26ms）**；
  范围 1.71–3.02ms；配对比值均值 1.756（比值之均值 1.742）。
- 勘误：此前聊天将 +2.3ms、2.2–2.7ms 错配给 S2（实为 S3 量级），且 S2 范围
  应为 2.16–3.96ms；1.9× 是 S2 配对比值均值。逐 boot 中位数的均值与 pooled
  中位数分别列出（pooled：S0 3045218 / S1 6237511 / S2 5735940 / S3 5385918ns；
  pooled P95：10819647 / 13423468 / 14028540 / 14614968ns）。已写入 ERRATA
  文件，不覆盖 11 轮报告。
- 归因收紧：日志同启动对照只支持“日志显著增加耗时”；跨批次差值不相加拆解
  历史差距；S1 未更快≠排除上下文发布/规则查找成本；S2/S3 未分辨≠零成本。

## 二、磁盘事件是否影响性能结论，是否需要补证？
见 02_disk_timeline/DISK_TIMELINE.md。结论：ENOSPC 发生于 17:52:32（p2 enabled
全部块结束）之后、17:53 首次 p2_s0 启动之前——严格位于两个采样块之间，不与任何
采样块重叠；the sampled block CSVs and guest writes were all complete.满盘精确时刻只能
以 ~1 分钟窗口间接界定。**无需按原协议重跑整批**；若再测，只需每块加 df/ENOSPC
快照。缺失记录（首次 p2_s0 launch.log、连续 df、r16 原始 guest 日志）已列出。

## 三、合理局部检查能否解决当前 ESP 案例？
能。L（原生基础 + ExternalStorageProvider 1 文件约 45 行检查，applied_L.diff）
3/3 实现：A+X 拒绝（FNF + L_POLICY_DENY 日志）、A→Y/B→X 保留、撤规恢复、
主体 A→B 反转、原生拒绝保持；并在 "wt" 截断诊断中**在打开前拒绝、文件不变**
（C 同场景为拒绝但文件已截断）。检查位置=openDocument 入口（Binder 调用者 uid
未清除前），对象=provider documentId，无资源泄漏（拒止在打开前）。

## 四、CDAC 在该比较中实际增加了什么，哪些方面平局或不占优？
- 平局：当前单入口直接路径的行为结果与 L 等价；身份信息在该路径与 L 同源。
- C 增加（本比较可陈述）：backing dev/ino 跨层对象证据（B2）、统一路由化决策
  与运行时规则（不改代码）、跨入口复用、生命周期/关系计数。
- 不占优：截断副作用（C 在 backing 打开后拒止→已截断；L 入口前拒止→不截断）；
  单路径接入成本（L 1 文件 vs C 全栈 delta）。
- 无实测证据的收益：多入口/转交/B3-B4 优势、更大规模与可靠性——仅机制分析。
- 论文 VI 的 LSM/BPF 表述针对内核侧 hook，与 L 不冲突；未冒充复现 LSM/BPF。

## 五、下一轮 B3 测试最值得检验的具体缺口是什么？
B3=同文件直接构造（绕过 ESP 入口直接持有 backing/PFD）能否被 CDAC 的
backing 对象关联（dev/ino+关系）识别，而 L 的 provider 入口检查天然不可见该
路径。最值得检验：**一个非 ESP 入口（例如已授权 app 通过 /storage 路径或
MediaProvider 直接 open 同一 backing X）能否在 C 下被同一 A+X 规则识别/拒绝，
L 下则无此能力**；并记录能力交付与文件副作用。这是 C 相对 L 的核心可辩护差异
的唯一直接行为证据点，本轮未测。

## 交付
- 01_stats_recompute/（脚本、重算输出、ERRATA_20261025.md）
- 02_disk_timeline/DISK_TIMELINE.md
- 03_mech_compare/{protocol/MECH_COMPARE_PROTOCOL.md, L_patch/*, RESULTS_COMPARE.md,
  INTEGRATION_COST.md, results/{N_n1,L_l1,C_c1}}
- 04_builds/（l_build/nprime_build 日志、l_artifacts、nprime_artifacts、
  nprime_vs_l_tree.diff）
- 05_final/（本报告、FINAL_STATUS、SHA256SUMS）

## 修改清单与耗时（墙钟）
- 新增 12 轮全部文件；未改 CDAC 实现、论文、历史统计。
- L 补丁设计/实现 ~0.6h；源码解压 ~0.6h；L 全量构建 1:27:51 + N'/L 增量重构建
  3×~1.2min（机器时间，与文档工作并行）；协议与脚本 ~0.8h；N/L/C 三侧启动、
  授权（含 SAF 自动化失败手工补齐）、运行 ~1.6h（C 首次启动 Mode-A adb 不可达
  一次并重试，已记录）；统计重算/磁盘时间线/报告 ~1.2h。合计约 6.7h。
- 保留全部原始 CSV、逐次 ledger、规则/策略读回与文件状态；三侧实例已干净停止。
