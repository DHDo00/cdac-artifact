# LOG_GATING_AUDIT.md — CDAC 观测日志门控审计（2026-10-24）

## 内核侧（source_enabled_kernel）
- 全部每请求 CDAC 内核日志均由 `iguard_verbose_audit`（debugfs bool
  /sys/kernel/debug/iguard/verbose_audit）门控：
  - iguard_ctx.c：decision/decision-apply/enforce-plan/real-enforce/perf(seq)/
    VFS_JOIN/BINDER_ENTER_CTL/PUSH/POP/EXIT_CTL/BINDER_NO_CONTEXT/
    FILE_LINEAGE/CDAC_RUST_BINDER_FD_TRANSFER 均为 `iguard_vinfo` 宏；
    宏在 verbose=false 时短路，不执行参数求值与格式化（pr_info 不调用）。
  - binder.c CDAC_BINDER_FD_AUDIT 系列：`if (iguard_ctx_verbose_audit_enabled())`
    显式门控（binder.c:2539/2562/2572/2597/3810/3846/4975/5008）。
  - iguard_ctx.c:444 CDAC_RECEIVE_FD_TRANSFER：`if (!enabled) return;` 显式门控。
- 非每请求的无条件输出仅：policy add/clear 的 perf policy_op（管理操作，在计时
  区间外）、push/pop 失败告警（异常路径）、模块初始化行。因此
  **verbose_audit=0 同时关闭生成、格式化与控制台输出**，不是仅关采集。
- 开关读写均为 root debugfs 0600；写入 1/0，读回 Y/N。

## 框架侧（frameworks/base）
- CdacRuntimeConfig（package-private）：`persist.debug.cdac.logging_mode`
  取值 quiet/audit/trace；`isPerAttemptTextLoggingEnabled()=!quiet`。
- quiet 时跳过每次尝试的 Log.i 文本（Binder.java:1548 CDAC_BINDER_ENTRY、
  CdacEndpointRegistry.java:326 CDAC_ENDPOINT_RESOLVE、ExternalStorageProvider
  发布日志等），但仍执行计数器（noteContextEnter/noteContextPublish/…）与
  **向 /dev/iguard_ctl 的上下文发布（安全路径，不受日志模式影响）**。
- 属性经 SystemProperties.addChangeCallback 即时生效于 provider 进程。

## 性能评估日志配置（LOG_OFF，用于正式采样）
- kernel：`echo 0 > /sys/kernel/debug/iguard/verbose_audit`（读回 N）。
- framework：`setprop persist.debug.cdac.logging_mode quiet`（provider 进程回调）。
- 保持：上下文发布、规则查找、对象检查、真实拒止、全部钩子与计数。
- LOG_ON（诊断对照）：verbose_audit=1 + logging_mode=audit。
- 结论：现有开关即可分别关闭内核与框架的每请求观测输出，无需新增内核补丁。
