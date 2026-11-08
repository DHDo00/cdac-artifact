# MISSING_AND_LIMITATIONS.md

## 缺失/未决
1. 内核精确源码树仍 SOURCE_MISSING（内核清理行为由运行观测支撑，源码不闭合）。
2. MediaProvider 进程 `sObserver=null` 与 `tracingEnabled=false` 是**静态配置链结论**，
   无该 boot 的逐字段运行时快照（任务禁止新 adb 采样）；单点采样也不能证明整 boot。
3. system_server 内 observer 默认开启，callStarted/callEnded/callThrewException 无 throws
   声明、无显式抛出点，但 unchecked 异常原则上不可排除 → E7/E8 的 system_server 窗口为
   UNKNOWN_BOUNDED；不属于被评估 6/501 路线进程，不作为 6/501 收尾依据。
4. 诊断 app_process 未启用 observer/trace（证据为日志无相关调用 + dex 顺序），
   未运行触发 E7/E8 的 system_server 类配置。
5. attempt4（未修正 Binder）的旧 dex 未在当前 /tmp 保留（重建时被覆盖）→ 无法提供
   失败过程的旧产物字节对照；仅保留上轮 dex_verify.txt 的 7 行摘要与源码 diff。
6. A16/A17 仅静态对照，无新增运行样本。
7. 人工工时 UNMEASURED；无手工移植对照 → 不写节省/高效结论。

## 已建立（对应限定）
- E5 缺口修正 + 运行验证（D3：展开中一次 exit/POP、内核 EXIT_CTL、深度恢复）。
- E6 常量折叠不可触发；checkParcel 在固定产物为 return-void。
- E7/E8 在被评估 MediaProvider 配置内不可达（observer null + trace 关闭 + 源码/binary 证据）。
- R1 回归 30/30（6 拒止+24 允许/恢复）在修正制品上通过。
