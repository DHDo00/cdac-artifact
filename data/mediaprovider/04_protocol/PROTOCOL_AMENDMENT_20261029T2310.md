# PROTOCOL_AMENDMENT_20261029T2310.md — 执行顺序记录（非策略/机制改动）

冻结协议 §2 写“每 boot 先 M 后 L”。冻结 runner（06_runtime/run_boot.py，其哈希已入
FREEZE_MANIFEST.txt）对每个 boot 的排程行按 `(study, cycle, state, exec_order)` 排序，
字符串序 `"L" < "M"`，因此实际执行顺序为 **每 boot 先 L 后 M**。

处理（保持单一 campaign，不重跑、不改 runner）：
1. 三个 boot 统一使用同一冻结 runner，实际顺序均为 L→M，boot 间一致；
2. 每循环语义不变：以无规则开始、以撤规和恢复检查结束；每次状态切换均 add/dump/
   clear/dump 读回；两项实验之间 L 结束的 S3 已 clear 且 M 首个 S0 再次确认 count=0；
3. 所有请求仍唯一 reqid、按冻结 SCHEDULE.csv 的每状态内随机顺序执行；
4. 本文件只记录执行顺序与协议措辞的差异，不改变任何判定 oracle、样本量或分母。

影响评估：M 与 L 规则、对象、调用者相互独立；L 每次允许写后恢复 X 原字节，M 开始时
X 内容为原始 e22785cd…。因此顺序差异不影响任何条件的结果判定。
