# CDAC 多规则规模匹配正确性与延迟实验 — 最终报告（2026-10-26）

目录：21_rule_count_scaling_20261026/（独立；未修改第 20 轮工作区、共享源码、
构建输出与论文）。实例 cvd-21（ADB 0.0.0.0:6540），实验后已干净停止并恢复
全局 cuttlefish 配置链接。

## 一句话结论
在已验证的 ESP 5/401 直接写路线上：**N=1/8/32/128 条活跃规则下选择性拒止全部
保持正确（61/61 正确性步全部 PASS，含 128 目标规则靠后安装）**；**端到端延迟
增长在本会话精度下未被分辨**（配对区组差值中位数 ±3.4ms 内、bootstrap 均值
CI 全跨 0），即不能据此宣称“更多规则更慢或更快”，也不能写“零成本”。

## 1. 实测了多少条活跃规则、如何核实
- 规模 N ∈ {0,1,8,32,128}（4 个非零规模 + 空规则参考），先于采样冻结。
- 每个非零规模配置 = 1 条 A+X 目标拒绝规则 + N−1 条合成填充规则。
- 核实方式：每次安装后读回 `/sys/kernel/debug/iguard/policy_dump`，
  `runtime_policy_count` 与逐槽行数双重核对 == N；所有安装记录 verified=True
  （正确性 13 次、性能 200 次配置）。绝不把“发送 N 次 add”当作 N 条活跃规则。
- 填充规则进入执法查找结构（唯一 8192 槽扁平数组、无分桶；每条对 T→X 请求
  经 service/op/caller 与 operation/path_tail 两次 strcmp 后在第 6 字段 ino
  失败，属最贵单条失败路径）。诚实边界：第 65 条起不进入 64 项 fd 血统缓存
  （该缓存只服务 fd 审计，不参与裁决）。填充规则全程标注 synthetic。

## 2. 各规模的选择性拒止是否正确
- 是。boot1 每个非零规模 3 轮 × {A→X 真实拒止, A→Y 允许, B→X 允许, 撤规后
  A→X 恢复} = 48/48 PASS；N=128 目标规则靠后安装 3/3 拒止；健康块 boot1、
  boot2 各 5/5 PASS。合计正确性步 61/61 PASS（含 16 次拒止，quiet_counters
  file_open_deny 与 16 精确对应；boot2 deny=3 与 H2+diag 对应）。
- 拒止判据（全部满足）：规则状态与主体/对象/操作字段（policy_dump）、
  App 无可用能力（WRITE_FAIL）、对象无副作用（size/sha 不变）、
  file_open_deny 计数 +1（真实执法分支）。LOG_ON 诊断单独捕获
  `real-enforce … caller_uid=10122 … service_id=5 op_id=401 op=openAssetFile
  path_tail=X.bin errno=-13 verdict=deny-now`（N=1 与 N=128 各一次）。
- 未出现对象误杀、调用者误杀；上下文发布全程平衡（boot1 push=pop=1187，
  boot2 push=pop=1140，fail=0）。

## 3. 延迟增长是否可分辨、跨 boot 是否一致
- 不可分辨。每 boot 20 区组配对差值 T(N)−T(0)：
  boot1 N∈{1,8,32,128} 中位数 −0.49..+0.23ms；boot2 −3.34..+2.25ms；
  区组极差 ±10–27ms；bootstrap 均值 95%CI 全部跨 0。
- 跨 boot：各规模中位数 boot1/boot2 分别 15.6–16.9 / 15.5–17.3ms，水平一致；
  差值符号在两 boot 间不重现（除 N=32 两 boot 均略负、N=128 均略正，幅度
  ≪ 噪声）。仅 2 个独立 boot，一致性描述以此为限。
- 与本实现预期一致：执法恒遍历 8192 槽，128 条仅占 1.6% 槽位，边际成本
  亚微秒级，被端到端几毫秒噪声淹没。与 round-11 “S2 vs S3 未分辨”一致并
  扩展到 128 条。

## 4. 当前容量/查找结构限制（实现审计，未改动任何源码）
- 容量上限：编译期 `IGUARD_RUNTIME_POLICY_MAX=8192`（内核 security/iguard_ctx.c，
  部署源码重构哈希 225242ce… 与 round-6 after.sha256 一致）；表满返回 -ENOSPC。
- 安装=追加（首空槽），无按键替换、不去重（重复 add 产生多条）；clear=全清
  （无按条删除）。每次 add 重建 fd 目标缓存。
- 查找=唯一 8192 槽扁平数组恒全扫、无索引/无提前返回；同特异性取槽序靠前者；
  运行时规则优先于 4 条静态基线。规则条数可用 policy_dump 的 count+逐槽行
  运行时核实。
- fd 血统缓存上限 64 项（ino&&s_dev 非零规则），不参与裁决。
- 本轮不测 8192 上限本身；实测规模结论限于 ≤128 条。

## 5. 支持/不能外推的规模结论
- 支持：ESP 5/401 写路线上，1→128 条活跃规则时选择性拒止正确性不变；在本会话
  条件（LOG_OFF、两 boot、同区组配对、5 条/规模/区组）下，端到端延迟差异
  “当前测量未分辨”。
- 不能外推：不宣称规则条数对延迟“零影响”；不把端到端差值当纯内核查询耗时；
  不与 round-12 旧制品差值拼接；不覆盖其他端点/路线（转发的读路径、MediaProvider
  等）；不覆盖 8192 上限或超过 64 条后 fd 血统缓存截断对审计行为的影响；合成
  填充规则不代表真实业务规则分布；2 boot/每区组 5 条样本不足以给正式置信区间。

## 交付物
- 00_implementation_audit/：实现与容量核查 + 部署源码重构（iguard_ctx.c.deployed、
  iguard_ctl.c、iguardctl_test.c）。
- 01_evidence_reuse/：制品来源与哈希。02_protocol/：冻结协议与冻结清单。
- 03_rulegen/：规则生成器 rules.py、schedule.csv（seed=20261026）、payloads.json。
- 04_runtime/：启动/安装/健康/日志归档、boot_cfg.json、TIME_AND_FAILURES.md。
- 05_correctness/：逐次正确性 jsonl/csv、规则读回、diag（decision_ns、拒止文本）、
  结果表。06_perf_raw/：1000 行逐次 CSV + 每配置 meta.json。
- 07_analysis/：analyze.py、plot.py、analysis.json/txt、两张图、REPORT.md。
- 08_final/：本报告、FINAL_STATUS.txt、SHA256SUMS.txt。

## 边界声明
- 未修改第三方发布机制、SELinux、核心算法；未搜索新入口；未改论文。
- 未为凑规模修改容量或查找算法；未新增内核计时探针（decision_ns 复用既有日志）。
- 普通脚本问题修复均记录在 TIME_AND_FAILURES.md；核心机制/容量/探针零改动。
