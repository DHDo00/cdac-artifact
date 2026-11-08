# NEXT_ACTION_DECISION.md — 下一步判定

## 总判定：A（在限定范围内可按证据收尾，不新增实验）
- 被评估范围=修正 A15 固定制品、MediaProvider 进程、txn14 openFile→6/501 单路线、
  复用 CDAC 6.12 内核。该范围内：
  - E7/E8 的回调（traceEnd/observer.callEnded/callStarted）配置关闭（observer null 于
    非 system_server 进程；冻结启动未启用 AIDL trace tag）→ 不可达；
  - E6 常量折叠不可触发；
  - E5 已修正并运行验证。
  → 无“成功 PUSH 后绕过 exit/POP”的可达路径；移植收尾可结束，无需新 boot/版本样本。
- 论文表述限定词：frozen config、该路线/进程、复用内核组合。

## 属 B 但超出当前范围（不触发本轮，不当作已验证）
- system_server 进程（observer 默认开启）存在三版共同的结构性 E7/E8 窗口
  （exit 位于 callEnded 之后）。system_server 不承载 6/501 ContentProvider 路线，
  不属于当前移植声明范围。若未来论文把范围扩到 system_server 或宣称“任意进程”覆盖，
  需另行评估；不要现在写“已关闭”。

## 无需新实验的结论
- E6 不可触发（常量折叠，产物核验）；
- E7/E8 在 MediaProvider 配置内不可达（配置链+产物顺序）；
- R1 回归已通过且与本问题正交（其 30 请求不涉及 E7/E8/E6）。

## 若未来选择扩展 system_server 范围（仅草案，未应用/未构建/未测试）
- 候选最小防御（非本轮修正）：将 `CdacBinderContext.exit` 移为 finally 首条语句或
  用嵌套 try/finally 包裹 traceEnd/observer 块，保证 exit 在回调之前执行；
  这会改变与 A16/A17 参照版的次序，需要独立控制流审计与 R1 回归。
- 定向验收（冻结草案）：在启用 observer 的进程中触发 callStarted/callEnded 抛出，
  确认一次 exit/POP、原异常传播、内核清理与后续归属；不做则不得宣称。
本轮未执行、未应用、未构建、未测试。
