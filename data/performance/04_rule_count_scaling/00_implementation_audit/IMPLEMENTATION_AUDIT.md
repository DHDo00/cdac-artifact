# CDAC 运行时规则实现与容量核查（第 21 轮专用，2026-10-26）

本文件只描述**实际部署制品对应的源码**，不修改任何源码。部署制品的规则机制来自
`kernel_esp_dist`（round-6 制品，bzImage 5e89e605… / initramfs 95af695a…），其
`common/security/iguard_ctx.c` 按 round-6 证据重构：
`00_impl/kernel/iguard_ctx.c.before`（sha256 a109559b…）+ `00_impl/kernel/whitelist.diff`
（+1 行 `(service_id == 5 && op_id == 401)`）= `iguard_ctx.c.deployed`
（sha256 225242ce…），与 round-6 记录 `00_impl/kernel/after.sha256` 完全一致。
`common/drivers/misc/iguard_ctl.c`（sha256 见 sources.sha256）自 2026-06-24 未改动，
先于 round-6 构建，视为部署源码。行号以下均指 `iguard_ctx.c.deployed`。

## 1. 容量上限及约束层

- 编译期常量 `IGUARD_RUNTIME_POLICY_MAX = 8192`（:887）。
- 存储：内核全局扁平数组 `iguard_runtime_policy_table[8192]`（:903），类型
  `struct iguard_runtime_policy_rule`（`used` 标志 + 规则字段 + 4 个 96B 字符串缓冲）。
- 计数：`iguard_runtime_policy_count`（:904），由 `iguard_runtime_policy_lock` 互斥锁保护。
- 约束层在**内核安全模块**（`security/iguard_ctx.c`），不是 /dev/iguard_ctl 驱动层，
  也不在 framework/userspace。容量提升必须改内核源码并重建内核；本轮不改。
- 历史事实（仅作背景）：`source_enabled_kernel` 中保留备份
  `iguard_ctx.c.bak.runtime_policy_max_32.20260503_235750`，其中常量为 32，
  说明历史上容量曾为 32，后被改为 8192。部署制品的运行时常量以 :887 的 8192 为准。

## 2. 安装（add）语义

- 入口：userspace 工具 `iguardctl_test add key=value…` → 构造
  `iguard_policy_add_msg_v2`（iguard_ctl.c :166-179，含 service_id/op_id/caller_uid/
  decision_kind/f_flags_*/service/operation/path_tail/reason/f_mode_*/ino/s_dev/i_mode）
  → `write()` 到 `/dev/iguard_ctl`（iguard_ctl.c :432-597）→
  `iguard_handle_policy_add_v2`（:375）→ `iguard_ctx_runtime_policy_add_rule_fields`
  → `iguard_ctx_runtime_policy_add_rule_internal`（iguard_ctx.c.deployed :1556）。
- **追加语义（非替换）**：`add_rule_internal` 从槽位 0 起扫描第一个 `!used` 槽，
  写入新规则（:1589-1601），`runtime_policy_count++`。**没有按键/去重/替换逻辑**：
  重复 add 相同键会产生多条独立条目（不覆盖、不去重）。
- 每次 add 都调用 `iguard_fd_target_cache_rebuild_locked()`（:1596），全表重扫
  （:916-930）重建 fd 目标缓存（见 §5）。
- 表满（8192 条全 used）时返回 `-ENOSPC`，打印 `add-nospace`（:1632-1637）。
- add 的 pr_info 诊断行（:1606-1625）与 `iguard_emit_runtime_policy_perf("add",…)`
  为无条件 `pr_info`，不受 verbose_audit 门控；本轮安装放在计时区间之外。

## 3. 清除（clear）语义

- `iguardctl_test clear` → `/dev/iguard_ctl` POLICY_CLEAR → `iguard_ctx_runtime_policy_clear_all`
  （iguard_ctx.c.deployed :1530）：重置全部 8192 槽、`count=0`、重建 fd 目标缓存。
- 全量清除，无按条删除接口。

## 4. 查找顺序、索引与提前返回

- **无索引、无分桶**：唯一查找结构是全局扁平数组
  `iguard_runtime_policy_table[8192]`。所有运行时规则共享这 1 个结构。
- 目标请求（ESP 5/401 写）的执法路径：`iguard_ctx_audit_file_open`
  （:2631）→ `iguard_apply_file_open_decision`（:2024）→
  `iguard_build_file_open_decision`（:1734）→ `iguard_find_best_matching_runtime_rule`
  （:1457），在 `iguard_runtime_policy_lock` 下执行。
- `iguard_find_best_matching_runtime_rule`（:1467-1487）：`for i in 0..8191`，
  **恒遍历全部 8192 槽**。used 槽调用 `iguard_policy_rule_matches`；未命中槽仅
  `if (!used) continue`。
- **无提前返回**：即使已命中某规则，仍继续扫完整个数组，以
  `iguard_policy_rule_specificity_score`（:1244-1279，统计非零字段个数）取
  **最高 specificity 的规则**；同分取**槽序靠前**者（`score > best_score` 严格大于，
  相等不替换）。因此命中与否只影响最终裁决，不影响“是否扫满 8192 槽”。
- 运行时规则优先于静态基线表 `iguard_policy_table[4]`（:954-1038）：先查运行时表，
  命中则直接返回（:1744-1762），否则才查静态表（:1770）。
- 单条规则逐字段求值顺序（`iguard_policy_rule_matches` :1283-1343）：
  service_id → op_id → caller_uid（3 个廉价 u32 判等）→ operation（strcmp）→
  path_tail（strcmp）→ ino → s_dev → i_mode → f_flags(mask) → f_mode(mask)。
  字段为 0 表示通配（`iguard_match_*` :1181-1232）。因此**填充规则的失败位置决定其
  单条求值成本**；后段失败（字符串比对之后才在 ino 上失败）是最贵的单条路径。
- 补充：裁决仍需 `iguard_select_file_open_enforce_mode`（:1087）确认端点白名单
  （:1076-1085 含 5/401）才进入 `PREVIEW_ENFORCE`（真实拒止），否则 report-only。

## 5. fd 目标缓存（辅助结构，非执法查找结构）

- `iguard_fd_target_objects[IGUARD_FD_TARGET_OBJECT_MAX=64]`（:56, :173）：
  由 add/clear 重建，只收录 `rule->ino != 0 && rule->s_dev != 0` 的规则，
  **最多 64 条**（:916-930），按槽序、不去重。
- 用途：`iguard_file_is_tracked_target`（:369）/ `iguard_audit_fd_install`（:388）
  等 **fd 血统跟踪/审计**路径的快速判定；**不参与**上面 §4 的裁决查找。
- 含义（本轮必须如实声明）：≥64 条不同 (ino,s_dev) 的规则时，第 65 条起不再进入
  该 64 项缓存，但**全部仍进入执法查找结构**（8192 槽全表扫描，无 64 上限）。
  本轮填充规则（合成 ino、真实 s_dev）会进入执法全表扫描；128 规模时只有前 63
  条填充规则 + 目标规则进入 fd 血统缓存，报告如实区分两种结构。

## 6. 读回与运行时核实

- `cat /sys/kernel/debug/iguard/policy_dump` → `iguard_policy_dump_show`（:2449）：
  首行 `runtime_policy_count=N`，随后逐槽打印
  `[i] service_id=… op_id=… caller_uid=… … ino=… s_dev=M:m … decision=… reason=… specificity=…`。
  行数可交叉核对 `runtime_policy_count`，是**权威的实际活跃条数证据**。
- 因此规则数量可在运行时可靠核实：本轮每个规模安装后都读回 dump，
  以 `runtime_policy_count` 与逐槽行数双重核对等于目标 N，绝不把“发送 N 次 add”
  当作 N 条活跃规则。add 返回值（成功/ENOSPC）与 dump 计数联合判定。
- `quiet_counters`（:2499）提供 file_open_join / file_open_deny / rule 相关计数，
  用于执法前后增量核对。
- `policy_dump` 的 ino 与 s_dev 输出可核实填充规则进入执法结构的具体字段值。

## 7. 与历史“额外一次查询”证据的边界

旧 RQ4（S10 Settings 路线）只有空策略、单条不命中规则、单条目标拒绝三条对照
（RQ4_PROTOCOL_V1.md 的 A/B/C/D 臂），不是规则条数规模实验；本轮是首次
多规则规模实验，不直接复用旧 RQ4 数据做规模结论。
