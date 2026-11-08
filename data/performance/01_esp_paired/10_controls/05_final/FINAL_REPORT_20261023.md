# 补实验最终报告 — 三项控制 + 配对构建 + 应用计时试跑（2026-10-23）

目录：10_controls_matched_builds_timing_20261023/（独立，历史目录与统计未动）。
实例：enabled r20（C1–C3、S1/S3/S2）、stripped r21（S0），均经 session-holder
稳定运行，session-holder 修复沿用 09 轮结论。

## 状态字
- CONTROLS=PASS
- MATCHED_BUILDS=READY（复用 v1 已验证的配对 fresh 构建 + 本轮补齐两侧启动/运行时审计）
- APP_TIMING=PASS（主指标与辅助记录已实现；20 次试跑完成，非正式性能结论）

## 1. 撤规恢复和调用者策略反转是否成立？
- 成立。
- C1：A+X 规则 → `real-enforce deny-now errno=-13`、App FNF、X 状态不变；
  `policy clear` 后 runtime_policy_count=0，A→X 恢复 WRITE_OK（dev:ino=45:3401，
  内容变化），文件恢复夹具已记录。
- C2：规则 caller 从 A(10121) 改为 B(10122)、对象/操作不变 → B→X
  `real-enforce caller_uid=10122 deny-now`、App FNF；A→X 在规则存在时
  `decision matched=0`（caller≠10122）→ WRITE_OK。与 C1 撤规、与 deny→allow
  均不同，单列。
- 全部 UID/ino/dev 动态查询，无硬编码。

## 2. 原生拒绝是否保持？
- 是。A 打开其未持有 grant 的 espafd_tree_b/XN.bin：
  (a) CDAC 机制开、无规则 → SecurityException（原生授权拒绝，Provider 层，未到
  VFS join/decision）；
  (b) 判定路径消融（ablate_disable_runtime=1 + ablate_disable_ctx=1）→ 同样
  SecurityException；内核仅多出 `CDAC_BINDER_ASYNC_ABSTAIN push_skipped`。
  两种状态均未把原生拒绝改为放行。
- 如实声明：S1 消融开关只关运行时规则查找与调用者上下文发布；静态规则、全部
  钩子与日志仍在，不是完整"关闭 CDAC"，完整无 CDAC 只有 S0（stripped 构建）。

## 3. 有、无 CDAC 制品是否真正可比，尚有哪些差异？
- 共同基础可重建：AOSP Baklava BP4A.251205.006，产品 aosp_cf_x86_64_only_phone
  eng，BUILD_NUMBER=cdacmsb20260818，boot.img 双侧字节相同（1d1a25f8…）。
- 无 CDAC 侧（S0）= v1 stripped fresh 构建：源码等价 PASS（共享文件字节一致、
  0 未授权差异、CDAC marker 0 命中），覆盖 framework/JNI/FUSE/内核/模块/sepolicy
  各层；运行时缺位本轮核验（/dev/iguard_ctl、iguard 模块、debugfs iguard 均缺失）。
- 两侧差异全部可归属 CDAC delta（89 行清单）+ ESP 两条（registry 5/401 分支、
  kernel 白名单一行）；差异清单见 02_matched_builds/。
- 遗留说明：enabled 侧 vbmeta/vendor_boot 与 stripped 侧哈希不同（签名链差异，
  未逐一解析但两侧均可正常启动）；kernel dist dot_config 中 CONFIG_IGUARD_CTL
  为前阶段快照视图（模块经 fragment 构建并实际加载）。这些均已列出，不默认无影响。

## 4. 应用计时是否覆盖完整请求区间？
- 是。主指标=应用内单调钟（SystemClock.elapsedRealtimeNanos）从
  openFileDescriptor 调用前到 PFD 返回/异常；覆盖 txn15 真实服务路径。
- 辅助记录：结果类型/异常类、PFD fstat dev/ino/size_pre/post、写入字节、
  关闭时刻与 close_ns；夹具恢复、规则安装、快照、CSV 序列化均在主计时区间外；
  计时后验证能力（写入+fstat）。
- 同一 APK（esp-timing-signed，sha 见 SHA256SUMS）、同入口 openFileDescriptor、
  同 "w" 模式、同 14 字节规格与 SAF rw grant 用于 S0–S3。

## 5. 哪些数据只是连通性试跑，正式性能实验还缺什么？
- 试跑：每状态预热 5 + 记录 20 次合法请求，全部 WRITE_OK（0 失败/重试）。
  同构建可切换状态固定种子 20261023 打乱顺序= S1→S3→S2；跨构建 S0 单独
  boot（r21，先于 enabled 批次记录顺序）。采样期间无并发大型编译。
- 主指标中位数（ns，仅连通性，不作部署开销结论）：
  S0 6,330,685；S1 25,134,611；S2 28,603,177；S3 28,630,308。
- 已知混淆（报告而不修）：enabled 侧 verbose_audit=Y 使每次请求向控制台输出
  约 10 行功能审计日志，且 S0/S1–S3 跨 boot；因此本数据不能支持正式性能结论。
  同 boot 内 S2 vs S3（未命中规则）中位数几乎相同——规则查找边际成本本批约 0。
- 正式实验仍缺：匹配的无 CDAC 与 enabled 同批/多 boot 设计、采样时功能审计
  日志配置的显式冻结（功能日志与性能采样分离）、样本量与排除规则、P95 稳定性
  判定。decision_ns/cost_ns 作为内部成本分别保存（perf 行），不当作应用开销。

## 修改清单与耗时（墙钟，单人）
- 新增：10_*/ 全部文件（协议、脚本、计时 APK 源码+构建、控制结果、采样、
  匹配构建清单、报告）；未改历史目录/制品/统计。
- 分析/设计 ~0.6h；C1–C3 实施与核查 ~0.5h；计时 APK 开发与调试 ~0.7h；
  enabled 启动/授权/夹具/采样 ~0.7h；stripped 启动/授权/采样 ~0.6h；
  报告与哈希 ~0.6h。构建：本轮 0 次平台构建（复用 v1 配对 fresh 构建 +
  2026-10-22 enabled 构建），仅 1 次 APK 构建（分钟级）。
