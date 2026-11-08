# MISSING_AND_LIMITATIONS.md — 2026-11-02 范围绑定轮

## 1. 输入完整性（本轮实际结果）
全部到位：输入 ZIP（422427 字节 / `59daca84…`）、主稿
`paper_snapshot/102901.txt`（121715 字节 / `e18ef6a5…`，版次 8）、
服务器核算包 tar.gz（587979 字节 / `952d9b22…`）。`verify_input.py` 在全新
解压目录实际运行 PASS（17 项哈希，版次 8）。上一轮“主稿缺失、UNRESOLVED”
的阻塞点本轮已消解。

## 2. 字段解析与语义归一（已核验）
- 六份 R39 LR/LW dump 实际解析为 flags/mode=0、device 0:0，与账本
  `rule_dump_sha` 逐 boot 对应。
- exact vs wildcard、path/name、relation type/stage、主体角色全部保留
  （CHECK_LOG F01–F06）。
- `operation=UNKNOWN` 等缺字段**未**按默认值合并：R12×6、R16×8 共 14 条
  add-only 记录保持候选；S10 的 dump 中 operation 本就不存在（op 无关规则）
  作为“权威 dump 语义”确认，不属候选。

## 3. 范围绑定（已核验）
- `MAIN_LASTKNOWN` 31 行逐项判定：见 PAPER_BINDING.csv。
- R40-72 与 R40-720 当前正文未采用（无 72/720 数字；正文只有 B1“不可判定”
  的定性结论）→ COMPLETED_PENDING，两个分母分别保留。
- A15 历史与修正制品/批次分列（同配置、不同制品：历史 892/763、修正 891/763
  标 DERIVED；论文平台表用 1 boot/30 请求的修正版结果）。
- 不纳入进行中任务；R29（0 boot）与 A15 诊断 boot 单列。

## 4. 输出确定性（已核验）
`recompute/recompute_scope.py` 连跑两次，LOGICAL_CONFIGURATIONS /
COUNT_CONTRIBUTIONS / INSTANCE_LEDGER / DEPLOYMENT_LEDGER / stats.json
哈希完全一致（CHECK_LOG X01）。旧包与修正包两个既有重算也分别复现
（旧包 16 pass/0 fail、12 项 frozen MATCH；修正包 17 pass、12 selftest）。

## 5. 仍未决 / 明确未知
1. **历史可执行模板总数**：NOT_RECORDED（不事后补造；7 canonical 描述 +
   2 生成函数不是“9 个专家目标模板”）。
2. **专家主动工时**：NOT_MEASURED；不安排人时补测。
3. **无法确定的等价关系**（分列，不合并）：
   - R38 `X(proxy)` ↔ R40-RD `X`：同一 deputy/openTypedAssetFile/wildcard/
     flags=0 规则，仅 reason 派生的对象标签不同；
   - R12-C/R16-esp-regress add-only ↔ 有 dump 的 ESP A,X（op/rel 缺字段）；
   - R16 写对比四配置 add-only：op=openAssetFile 仅有 COMPARISON_REPORT 级证据；
   - A15 exact `0:46` ↔ A16/A17 exact `0:45`：跨平台设备号是否同角色未定。
4. **缺原件**：R30-name-O 的 add/dump；A17 boot2 的规则 add/dump（实例口径
   少 2 条，逻辑配置不受影响）；SettingsProvider decoy/caller 变体的独立规则
   原件（论文 Tab settings-protocol 的 C2/CB/CA0 行）。
5. **891/763 修正版 A15 行数**：仅有审稿分析说明（DERIVED），无本轮独立 diff
   重算；历史 892/763（含 checkfc）与机制口径 890/762 维持原复算。

## 6. 不成立的结论（继续不发布）
- 不宣称“全文共 5 个策略”；当前全文为 18 个 deny 逻辑配置
  （11 目标/MIXED + 7 控制）+ 1 filler 家族，其中 2+6 为候选。
- 不把 39/45 add 命令数写成 verified deployments；可核验成功部署 = 31。
- 不把“56/127”说成全量实例（它是解析子集；含端口为 62 deny 实例）。
- 不用 LOC/墙钟推断人力；不称人工扩展性已建立。
