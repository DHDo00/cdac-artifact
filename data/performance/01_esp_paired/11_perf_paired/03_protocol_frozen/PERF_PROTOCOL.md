# PERF_PROTOCOL.md — 性能评估冻结协议（2026-10-24，先于正式采集固定）

## 制品与输入（复用已闭合的配对审计，逐项重新核验哈希）
- S0（完全无 CDAC）：v1 stripped system 24550e03… / super 820c1aa5… /
  boot 1d1a25f8… + kernel_stripped_dist bzImage 405f5c47… / initramfs
  ffb1b95f…；无 iguard_ctl.ko。
- S1/S2/S3（enabled）：android_matchedimg_newsystem system 54193b1f… /
  super a90df407… / boot 1d1a25f8… + kernel_esp_dist bzImage 5e89e605… /
  initramfs 95af695a…；iguard_ctl.ko 随 dist。
- APK：esp-timing-signed.apk sha 8ca8cd21…（S0–S3 同一 APK）。
- 启动参数：cpus=4、memory_mb=4096、SELinux Enforcing、4 条 launch 参数与
  10_controls 一致；enabled kernel 6.12.74-android16-6-maybe-dirty，stripped
  同版本串（同基础构建）。vbmeta/vendor_boot 差异沿用既有解释（签名链）。
- 实际模块：enabled 加载 iguard_ctl（运行时 /dev/iguard_ctl 在）；stripped
  无该模块、无设备、无 debugfs iguard。每次启动记录 lsmod/设备检查。

## 状态定义（正式采集）
- S0：完全无 CDAC（stripped），无规则接口。
- S1：enabled，ablate_disable_runtime=1 + ablate_disable_ctx=1，policy clear；
  保留静态机制与全部钩子（上下文发布被消融，真实拒绝路径被消融）——仅用于
  解释组成，不作主部署成本。
- S2：enabled 完整，policy clear（无规则）。
- S3：enabled 完整，安装 A+X deny 规则（caller=动态 A uid, ino=X, s_dev=
  254:96, f_flags_mask=0x3 f_flags_value=0x1, decision=deny, reason 固定）；
  计时应用 uid≠A，请求**不命中拒绝规则**（不得表述为“命中允许规则”）。

## 日志配置（冻结）
- 正式采样 LOG_OFF：kernel `echo 0 > /sys/kernel/debug/iguard/verbose_audit`
  （读回 N）；framework `persist.debug.cdac.logging_mode=quiet` 在首次 provider
  使用前设置并逐块核验（framework 文本日志≈0；已知 addChangeCallback 对已加载
  进程不即时生效，故在每 boot 首次使用 provider 前设置，且核验计数）。
- 保持开启：上下文发布（/dev/iguard_ctl 写）、规则查找、对象检查、真实拒止、
  全部钩子与 quiet_counters。
- 同 boot LOG_ON 对照已单独完成（01_diag_sameboot），不混入正式采样。

## 工作负载与夹具
- 计时 APK（com.demo.esptiming）对 primary:espafd_tree/X.bin（14 字节）执行
  ContentResolver.openFileDescriptor(uri,"w")；SAF 持久 rw grant；每状态前用
  同一 APK 的 restore 动作把 X 恢复为 0123456789ABCD（计时区间外）。
- 主指标：应用内单调钟（elapsedRealtimeNanos）从 openFileDescriptor 调用前到
  PFD 返回/异常。能力验证（写入+fstat）、关闭、快照、CSV 输出均在主计时区间外，
  逐次记录 open_ns/close_ns/结果/异常/dev/ino/size/字节/uid。
- 拒绝请求计时不参与成功返回比较；本轮不测拒绝计时。

## 采集设计（先于正式采集固定，不再按结果追加）
- 4 对启动：Pair1 S0 先→enabled 后；Pair2 enabled 先→S0 后；Pair3 S0 先；
  Pair4 enabled 先。
- enabled 内状态顺序（固定）：boot1 S1,S2,S3；boot2 S3,S1,S2；
  boot3 S2,S3,S1；boot4 S1,S3,S2（3 状态 4 行无法完全平衡位置，如实记录）。
- 每次启动：同健康检查（boot_completed、SELinux、/dev/iguard_ctl 按侧核验、
  uptime）；稳定等待后（boot_completed 后 ≥120s）开始采样；期间无大型编译。
- 每状态：预热 20 + 记录 200；全部原始行保存；任何失败/异常/重试保留，预定义
  规则：该状态有效行=WRITE_OK 且计时区间完整；无效行单独统计、不静默补足。

## 统计定义（固定）
- 分位数：线性插值（R type-7）——rank=(n-1)*p，floor/ceil 插值。中位数 p=0.5，
  P95 p=0.95。
- 每启动每状态报告 n、失败数、中位数、P95、min/max。
- 主指标：pair 内 enabled 状态中位数 − S0 中位数（绝对 ns）与比值（相对）。
- 合并样本（pooled）P95 与“各启动 P95 的汇总”分别给出，不混用。
- 不确定性：4 对为小样本，逐 pair 展示全部分布；不给正式置信区间，只报告
  pair 间 spread；同 boot 内 200 请求不作为独立系统重复（在解释中声明限制）。
- decision_ns / policy add-clear cost_ns 单独文件保存，不进入应用开销比较。

## 有效性闸门
- 若某侧可比性/功能检查失败或启动异常，保留诊断、标记 BLOCKED，不把该数据
  包装为正式性能结论。ESP 截断副作用与转发读路径边界保持不变。
