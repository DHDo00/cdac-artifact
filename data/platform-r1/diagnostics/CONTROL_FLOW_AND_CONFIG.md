# CONTROL_FLOW_AND_CONFIG.md — E7/E8 配置与可达性（只读核查）

## 1. 结论（限定范围）
- 修正 A15 的**被评估进程/路线** = MediaProvider 进程、IContentProvider txn14 openFile→6/501：
  - E8（enter 后 try 前 observer.callStarted）**不可达**：MediaProvider 进程 `sObserver=null`，
    `observer != null ? observer.callStarted(...) : null` 短路跳过。
  - E7（finally 内 exit 前的 traceEnd / workSource 解析 / observer.callEnded）**不可达**：
    `tracingEnabled=false`（冻结启动未启用 AIDL trace tag）且 `observer==null` → 两段均被
    guard 跳过 → **exit 是 finally 中实际执行的第一个调用**（其后 checkParcel 为常量折叠后的空方法）。
  - E6（checkParcel 抛 RuntimeException）**不可触发**：`CHECK_PARCEL_SIZE=false` 为 static final，
    修正产物 dex 中 `Binder.checkParcel` 已编译为仅 `return-void`。
- 因此**在被声称的固定配置与路线范围内，不存在“成功 PUSH 后绕过对应 exit/POP”的可达路径**；
  可按限定范围收尾，无需新增运行样本。这是配置关闭+源码/产物证据，不是“已验证永不抛异常”。

## 2. 关键配置链（逐条来源）
### 2.1 observer（E8/E7 的 observer 部分）
- `Binder.sObserver` 是每进程 static；唯一赋值点 `Binder.setObserver`。全树（out 排除）
  bounded grep：仅 `BinderCallsStatsService.java`、`BinderCallsStats.java`（A15；A16/A17 同）。
- `BinderCallsStatsService` 只由 `SystemServer.java` 启动（A15:1434-1435；A16:1493-1494；
  A17:1501-1502）→ 只有 **system_server** 进程会设置 observer。
- 默认开启值：`BinderCallsStats.ENABLED_DEFAULT=true`，settings key `binder_calls_stats`
  缺失时 parser 取默认 true → system_server 内 observer 默认启用；但 system_server 不承载
  IContentProvider 6/501 路线，不在被评估进程范围。
- MediaProvider 进程/诊断 app_process：从不调用 setObserver → sObserver 恒为 null
  （该进程生命周期内，静态字段由类加载器隔离）。

### 2.2 trace（E7 的 traceEnd 部分）
- `tracingEnabled = Trace.isTagEnabled(TRACE_TAG_AIDL) && transactionTraceName!=null`；
  `TRACE_TAG_AIDL = 1L<<24`（三版一致）。
- `Trace.traceEnd` 自身再检查 `isTagEnabled`，关闭时不做 native 调用。
- 修正轮冻结启动脚本无 atrace/perfetto 配置 → 冻结配置下 tag 关闭；属配置链静态结论，
  不是整 boot 运行采样。启用 only 在显式 atrace 时，属未来配置范围。

### 2.3 修正 A15 finally 内实际顺序（dex 原文）
`traceEnd → resolveWorkSourceUid → observer.callEnded → CdacBinderContext.exit →
checkParcel`（三段 finally 副本同序；raw_execTransactInternal.txt 偏移 008c/00ab、
00f6/0110、0120/013a）。前三个调用全部在 guard 内；guard 关闭时第一个实际调用即 exit。

## 3. E8 的 try 前其它语句（非 callback）
`cdacAuditBinderEntry`（Log）、`CdacBinderContext.enter`（writeFrame 内 catch(Throwable)，
enter 返回 null 或 Frame；失败路径 exit(null) 早退）、`observer= sObserver`（无调用）、
`callSession=…:null`（短路）、`Trace.isTagEnabled`（native 查询）、
`getTransactionTraceName`（AtomicReferenceArray 查询/首次分配）。在普通 JVM 模型下无已知
抛出路径；虚拟机级故障不在本轮模型内。

## 4. E7/E8 的“system_server 窗口”处置
system_server 内 observer 默认开启，callStarted/callEnded/callThrewException 无 throws
声明、其函数体（BinderCallsStats.java:220-253/253-269/384+）无已知显式抛出点；unchecked
异常原则上无法完全排除。该窗口在三版共同存在（exit 均在这些调用之后），但：
1) 不属于被评估的 MediaProvider 6/501 路线进程；
2) 无运行触发证据；
→ 记为 `UNKNOWN_BOUNDED`，禁止从 6/501 收尾扩展到 system_server。

## 5. 证据层次
- 配置关闭（observer null / trace off）= SOURCE_DIRECT（源码+启动链+bounded grep），
  非单次运行采样。
- 产物结构（exit 顺序、checkParcel 常量折叠）= BINARY_DIRECT（dexdump，见 04_dex/）。
- E5 已运行验证（上轮 D3）+ R1 回归（上轮）= RUNTIME_GUEST。
