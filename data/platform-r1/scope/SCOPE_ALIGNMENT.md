# SCOPE_ALIGNMENT.md — 四类证据的范围对齐

生成：2026-11-02。方法：只读核查 + 既有材料复算；不新增异常诊断或新路线请求。
每项声明按 SCOPE_ALIGNMENT.csv 的 13 列登记（声明/锚点、版本与制品、进程/域、路线与入口、
主体口径、规则/对象、配置前提、证据层次、正式分母、来源路径/行号、支持的结论、
不能外推的结论、缺证及建议措辞）。本文件为分组合成说明；逐项详见 CSV。

## 1. 三版本 R1 回归（普通 A/B 应用、MediaProvider txn14 openFile→6/501、真实 PFD 与拒止）
- 已核对的历史批次：A15 修正版 1 boot（30=6+24）、A16 R35 1 boot（30=6+24）、
  A17 2 boots（60=12+48），共 120 个历史正式请求，逐请求账本 sha256 复验一致。
- 本轮按差额补至每版 3 boot：计划新增 5 boot / 150 正式请求（A15×2、A16×2、A17×1）。
- 关键口径：
  1) 公开 API 签名只限被核实调用 `ContentProviderClient.openFile(uri,"r")`，不扩展为
     全部 API/CTS/OEM/原生内核兼容。
  2) 14=Binder transaction code；6/501=CDAC 内部端点映射；源码常量与运行证据分列。
  3) 每版三个 boot 使用该版同一冻结制品、动态绑定重测；A16 列注明“R35 冻结制品；
     原始批次及新增重复”，不得把合计 90 请求全写成历史 R35 原有数据。
  4) A15 旧制品（system.img 186ea808…）明确排除于修正版主表，单列历史。
  5) 三版均复用 CDAC Linux 6.12.74 A16 谱系制品 kernel_openkeychain_dist；
     A15 没有完成原生 6.6 的 CDAC 回移，A17 也没有完成任意内核兼容验证。
  6) 只支持该真实路线+指定组合的调用者选择性、规则主体反转、撤规恢复；不自动覆盖
     其余端点、性能、origin 跨跳传播或所有 B1–B4 运行条件。
  7) 发布 PUSH/POP 与管理 ADD/CLEAR 仍共享 /dev/iguard_ctl write，不写 publish-only。
     域授权与采样/逐次写入观测区分；A15/A17 最小移植与 A16 R33 六域结果不能相互套用。
  8) 平台适配按原件核实：SELinux/ueventd 及 A15 checkfc；cuttlefish 条目三版一致；
     goldfish 只比较 A16/A17（A15 对应目录不存在）。

## 2. 4/301 共同 Binder 清理诊断（UID0/su 域、两进程夹具、无真实文件交付）
- 复算既有客户端尝试与服务端 frame：DIAGNOSTIC_CLIENT_ATTEMPTS.csv（5 次尝试，
  TXN0–3 有服务端 ENTER，TXN4 无）、DIAGNOSTIC_SERVER_FRAMES.csv（4 个 frame，tid 22727）、
  DIAGNOSTIC_CLAIMS.csv（normal/Runtime/Error-unwind 成立；Error-after-recovery 不成立）。
- 约束：
  - 诊断为两个 app_process 进程、su 域夹具、caller UID0、通用映射 4/301；无真实文件
    打开与能力交付。不能称为新增 DownloadProvider 或 MediaProvider 执法路线。
  - 正常调用有对应 POP；已捕获 RuntimeException 后同一 TID 继续正常事务有证据；
    AssertionError 展开时完成对应 POP、内核清理，随后服务进程死亡；Error 后继续服务未建立。
  - raw transact 返回 ok 不等于 reply 无业务异常；原驱动未 readException 时保持该限制。
  - 诊断计数、正式 R1 请求、空策略预检、各 boot 全局发布计数分别报告，不相加凑 90。
  - 三类出口的诊断覆盖发生在共同 Binder 夹具，不写成在 MediaProvider 6/501 实际触发
    并通过了全部异常类型。

## 3. E6/E7/E8 的源码、产物与配置结论
- 依据 binder_cleanup_reachability_readonly_20261101_232443 的可达性核查包复算：
  - E6：CHECK_PARCEL_SIZE=false；固定修正制品 checkParcel 仅 return-void（dex）。
    删除“超大 reply 使该函数抛 RuntimeException”的触发解释，不与
    TransactionTooLargeException 混同。
  - E8：enter 后、try 前的 observer.callStarted 窗口；MediaProvider sObserver=null
    （Binder.setObserver 仅 system_server 的 BinderCallsStats 调用）→ 三元跳过。
  - E7：finally 中 exit 前的 traceEnd/observer.callEnded 回调窗口；冻结启动无 tracer、
    observer 块关闭 → exit 是 finally 首条执行语句。
  - 无全 boot sObserver/trace 快照就是现有观测限制；静态配置推断不升级为全 boot
    运行事实，也不推广到任意进程/未来配置。
  - A16/A17 仅源码对照，不写成三版都做过异常运行验证。
  - “writeFrame 捕获写失败”不扩大为 exit 对所有 Throwable、所有 JVM 故障永不抛出。
  - 对 system_server 的 observer/trace 窗口保留原 UNKNOWN_BOUNDED 及其前提；三版共用
    该窗口不等于已修复。
  - 若原证据不足以支持某个配置判断，标部分记录/待核，不新增机制修补或故障注入凑收口。

## 4. GraphicsStatsService 源码资格与 system_server 范围
- 原 23 路径源码审计 = DownloadProvider 4 + ExternalStorageProvider 16 +
  GraphicsStatsService 3；20 = 4 + 13 + 3；另 3 条 ESP→MediaProvider 转发为 ABSTAIN。
  三条 GraphicsStats 路径均为 B1–B4 ESTABLISHED（SOURCE_ONLY_FROZEN_AUDIT），宿主
  system_server。
- system_server 位于本轮 MediaProvider R1 运行范围之外，但不能据此称它位于整篇论文范围之外。
- 逐条对齐与关系结论见 GRAPHICSSTATS_SCOPE_RECONCILIATION.md：
  1) 原 20/23 为冻结协议与范围下的源码资格结果，不是本轮需要强行保持的验收数字。
  2) 原结构资格与共同 Binder 实现的异常生命周期保证不是同一类证据；三版本 R1 成功
     不能推出 system_server 异常窗口已通过。
  3) observer/trace unchecked 异常窗口影响的是共同插桩前提（Binder lifecycle 的
     exit/POP 次序），逐路径列出影响等级，不藏进“未来工作”。
  4) 不静默删除三条路径、不缩分母、不另定义范围维持 20/23、不无据改历史资格结果。
  5) 支持“结构资格成立，但更广异常配置下的共同实现前提未充分验证”的准确关系表述。
  6) 不虚构新运行守卫或自动 abstain；若需修补列独立后续任务，本轮不修改生产代码、
     不另开 system_server 实验。

## 5. 成本与共用边界（与本表有关信息）
- 4/5 自有 R1 完整源文件原样复用 ≠ 系统 80%；Binder 不在分母。人工主动时间仍未测
  （UNMEASURED）；墙钟、同步/构建等待、guest 运行时间不改成人时。
- 修正前后 A15 接入规模分列：892/763=含 checkfc 总数；修正 Binder 净少 1 空行
  →修正制品 891/763；A17=890/763。
- 只采用已审阅的端点/策略口径，不引入仍在勘误中的全局策略/模板总数；与本任务无关的
  新问题列待办，不自动扩展。
