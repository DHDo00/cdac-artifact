# GRAPHICSSTATS_SCOPE_RECONCILIATION.md — GraphicsStatsService 源码资格与 system_server 范围对齐

生成：2026-11-02。依据：route_observation_control_lookup_20260917（23 路径源码审计）与
binder_cleanup_reachability_readonly_20261101_232443（E6/E7/E8 配置链与 UNKNOWN_BOUNDED 结论）。

## 1. 原 20/23 口径（先核对当时定义与逐路径记录）
- 23 条 held-out 结构路径 = DownloadProvider 4 + ExternalStorageProvider 16 + GraphicsStatsService 3。
- 20 = 4 + 13 + 3（GraphicsStats 三条全部 ESTABLISHED）；另 3 条 ESP→MediaProvider 转发 B1=UNCLASSIFIABLE、
  路径结论 ABSTAIN（B2–B4 仍 ESTABLISHED）。23 条中没有 UNESTABLISHED。
- 路径单位是外部入口序列、进程转换序列、能力构造形式和首次暴露形式组成的结构元组；
  不是 23 个 Provider/漏洞/运行环境。B1–B4 判定是冻结协议与范围下的源码资格结果。
- 精确源码 revision：frameworks/base=45034f0663f960d9ee5fb0a101a4732b71f6e2f4。
- 结论：20/23 是源码资格计数，不是本轮需要强行保持的验收数字，也不能改写成 20 条已运行成功。

## 2. 三条 GraphicsStats 路径逐条列示
### R-E1-GRAPHICSSTATS-P-GFX-001-001（原路径编号，宿主 system_server）
- 入口/能力构造：requestBufferForProcess / existing_current_buffer
- 调用链：IGraphicsStats.requestBufferForProcess -> GraphicsStatsService.requestBufferForProcess -> GraphicsStatsService.requestBufferForProcessLocked -> GraphicsStatsService.fetchActiveBuffersLocked(existing current) -> ActiveBuffer.getPfd
- 进程转换：application process -> system_server Binder thread -> application process
- 能力形式/暴露：DIRECT_PFD_DUP / DIRECT_BINDER_RETURN
- 原判定：B1=ESTABLISHED B2=ESTABLISHED B3=ESTABLISHED B4=ESTABLISHED；
  路径结论=ESTABLISHED；evidence_kind=SOURCE_ONLY_FROZEN_AUDIT；
  runtime_observation=NOT_ESTABLISHED_BY_THIS_SOURCE_DATASET
- B1 机制：requestBufferForProcess captures Binder uid/pid before clearCallingIdentity, validates package ownership, and passes those captured values into the locked selection before restoring identity and returning.
- B2 机制：fetchActiveBuffersLocked selects the current uid/pid buffer or creates its replacement; the exact selected ActiveBuffer is the object whose descriptor is obtained.
- B3 机制：requestBufferForProcessLocked returns buffer.getPfd, which duplicates that ActiveBuffer SharedMemory descriptor.
- B4 机制：The selected buffer PFD is duplicated and returned synchronously before the Binder response.
- 源码引用（节选）：platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:core/java/android/view/IGraphicsStats.aidl:25-26;platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:graphics/java/android/graphics/GraphicsStatsService.java:173-195;278-283;376-401;496-547;platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:core/java/android/os/SharedMemory.java:297-309;platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:core/java/android/os/ParcelFileDescriptor.java:364-

### R-E1-GRAPHICSSTATS-P-GFX-001-002（原路径编号，宿主 system_server）
- 入口/能力构造：requestBufferForProcess / new_buffer_created
- 调用链：IGraphicsStats.requestBufferForProcess -> GraphicsStatsService.requestBufferForProcess -> GraphicsStatsService.requestBufferForProcessLocked -> GraphicsStatsService.fetchActiveBuffersLocked(no existing buffer) -> ActiveBuffer.<init> -> SharedMemory.create -> ActiveBuffer.getPfd
- 进程转换：application process -> system_server Binder thread -> application process
- 能力形式/暴露：SHARED_MEMORY_CREATE_AND_PFD_DUP / DIRECT_BINDER_RETURN
- 原判定：B1=ESTABLISHED B2=ESTABLISHED B3=ESTABLISHED B4=ESTABLISHED；
  路径结论=ESTABLISHED；evidence_kind=SOURCE_ONLY_FROZEN_AUDIT；
  runtime_observation=NOT_ESTABLISHED_BY_THIS_SOURCE_DATASET
- B1 机制：requestBufferForProcess captures Binder uid/pid before clearCallingIdentity, validates package ownership, and passes those captured values into the locked selection before restoring identity and returning.
- B2 机制：fetchActiveBuffersLocked selects the current uid/pid buffer or creates its replacement; the exact selected ActiveBuffer is the object whose descriptor is obtained.
- B3 机制：requestBufferForProcessLocked returns buffer.getPfd, which duplicates that ActiveBuffer SharedMemory descriptor.
- B4 机制：The selected buffer PFD is duplicated and returned synchronously before the Binder response.
- 源码引用（节选）：platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:core/java/android/view/IGraphicsStats.aidl:25-26;platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:graphics/java/android/graphics/GraphicsStatsService.java:173-195;278-283;376-401;496-547;platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:core/java/android/os/SharedMemory.java:297-309;platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:core/java/android/os/ParcelFileDescriptor.java:364-

### R-E1-GRAPHICSSTATS-P-GFX-001-003（原路径编号，宿主 system_server）
- 入口/能力构造：requestBufferForProcess / stale_buffer_replaced
- 调用链：IGraphicsStats.requestBufferForProcess -> GraphicsStatsService.requestBufferForProcess -> GraphicsStatsService.requestBufferForProcessLocked -> GraphicsStatsService.fetchActiveBuffersLocked(stale existing) -> ActiveBuffer.binderDied -> GraphicsStatsService.processDied -> GraphicsStatsService.addToSaveQueue -> ActiveBuffer.<init> -> SharedMemory.create -> ActiveBuffer.getPfd
- 进程转换：application process -> system_server Binder thread -> application process; stale-buffer persistence -> GraphicsStats-disk Handler
- 能力形式/暴露：STALE_REPLACEMENT_SHARED_MEMORY_CREATE_AND_PFD_DUP / DIRECT_BINDER_RETURN
- 原判定：B1=ESTABLISHED B2=ESTABLISHED B3=ESTABLISHED B4=ESTABLISHED；
  路径结论=ESTABLISHED；evidence_kind=SOURCE_ONLY_FROZEN_AUDIT；
  runtime_observation=NOT_ESTABLISHED_BY_THIS_SOURCE_DATASET
- B1 机制：requestBufferForProcess captures Binder uid/pid before clearCallingIdentity, validates package ownership, and passes those captured values into the locked selection before restoring identity and returning.
- B2 机制：fetchActiveBuffersLocked selects the current uid/pid buffer or creates its replacement; the exact selected ActiveBuffer is the object whose descriptor is obtained.
- B3 机制：requestBufferForProcessLocked returns buffer.getPfd, which duplicates that ActiveBuffer SharedMemory descriptor.
- B4 机制：The selected buffer PFD is duplicated and returned synchronously before the Binder response.
- 源码引用（节选）：platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:core/java/android/view/IGraphicsStats.aidl:25-26;platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:graphics/java/android/graphics/GraphicsStatsService.java:173-195;278-283;376-401;496-547;platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:core/java/android/os/SharedMemory.java:297-309;platform/frameworks/base@45034f0663f960d9ee5fb0a101a4732b71f6e2f4:core/java/android/os/ParcelFileDescriptor.java:364-

## 3. 宿主进程与共同插桩前提
- 三条路径宿主均为 system_server（应用进程 → system_server Binder 线程 → 应用进程）。
- 共同插桩前提：Binder.execTransactInternal 的 enter/exit/POP 生命周期（CDAC 钩子），
  exit 位于 finally 中 observer/trace 回调块之后（A16/A17 及修正 A15 位置一致）。
- 该共同前提不在原 B1–B4 四条件的判定范围内：B1–B4 是能力来源绑定/对象构造/返回暴露等
  源码义务；exit/POP 是否在任何异常下完成是另一层生命周期保证。

## 4. observer/trace unchecked 异常窗口对原资格前提的影响
- E7/E8 在 system_server 内 observer 默认启用（BinderCallsStatsService 于 SystemServer
  启动并 Binder.setObserver）；traceEnd 由 TRACE_TAG_AIDL 控制。
- 若 observer/trace 回调抛出 unchecked 异常，三版的 exit/POP 会被跳过（exit 在其后）。
- 影响等级：影响的是共同 Binder 生命周期前提（异常下的栈清理保证），不影响三条路径各自的
  B1（uid/pid 捕获与包所有权校验）、B2（锁定选择对应 ActiveBuffer）、B3（getPfd 复制描述符）、
  B4（返回前同步完成）的源码结构结论——即“结构资格成立”。
- 但“异常配置下的运行时清理”对 system_server 路径为 UNKNOWN_BOUNDED（无运行时触发证据）；
  不能宣称已保障，也不能把三版本 MediaProvider R1 的成功推广到 system_server 窗口。
- 逐路径影响表：三条路径共用同一 execTransactInternal 生命周期，逐条影响相同：
  B1–B4 源码资格不受影响；运行时异常清理前提 UNKNOWN_BOUNDED。

## 5. 两类证据的关系（准确表述）
- 可支持：结构资格成立（20/23 的源码资格），但更广异常配置下的共同实现前提未充分验证。
- 不能写：未验证异常情形已保障；20/23 已运行验证；三版本 R1 成功覆盖 system_server。
- 不静默删除三条路径、不缩分母、不另定义范围维持 20/23、不无据改历史资格结果。

## 6. 后续（仅登记，本轮不执行）
- 若确需补 system_server 异常窗口证据：独立任务 = 在 system_server 宿主触发 observer/trace
  回调异常并核验 exit/POP；或做默认关闭 observer 的静态/配置论证。本轮不修改生产代码、
  不另开 system_server 实验、不虚构运行守卫或自动 abstain 行为。
