# CDAC 多规则规模匹配正确性与延迟实验 — 冻结协议（2026-10-26，先于正式采样）

本协议在正式采样前冻结；之后不按结果调整规模、顺序、样本量或统计方法。
独立工作区 `21_rule_count_scaling_20261026/`；不修改第 20 轮工作区、共享源码、
构建输出与论文。路线只测一条：ESP 5/401 直接写（R-ESP-P-ESP-004-004）。

## 0. 隔离与并行边界
- 实例：cvd-21（`--base_instance_num=21`，ADB serial `0.0.0.0:6540`），
  与本轮无关的进程不停止；round-20 若占用同端口则等待其结束后再启动。
- 运行目录全部在 `04_runtime/{boot1,boot2}/` 下；脚本只在
  `scripts/` 与各自输出目录写文件；来源制品只读。
- 采样避开平台构建/论文编译高峰：每块开始记录 host loadavg；冻结干扰阈值见 §8。

## 1. 规模（先于采样固定）
- 规模集合 N ∈ {0, 1, 8, 32, 128}（4 个非零规模 + N=0 空规则参考）。
- 不测 8192 容量上限（实现审计已确认常量 8192；实际支持规模结论只到 128）。
- 每个非零 N 的配置：**1 条 A+X 目标拒绝规则**（先安装）+ **N-1 条填充规则**。

## 2. 规则（生成器 03_rulegen/rules.py，先于采样冻结）
- 目标规则：`service_id=5 op_id=401 caller_uid=<A> operation=openAssetFile
  ino=<X.ino> s_dev=<DEVRAW> i_mode=00 f_flags_mask=0x3 f_flags_value=0x1
  decision=deny reason=rcs21_tgt_A_X`
- 填充规则 i=1..N-1（**合成工作负载，未经真实业务审查，全程标注 synthetic**）：
  `service_id=5 op_id=401 caller_uid=<T> operation=openAssetFile path_tail=X.bin
  ino=<2000000+i> s_dev=<DEVRAW> i_mode=00 decision=audit reason=rcs21_fill_<i>`
  - 合法（结构合法、字段互不覆盖）、互不覆盖（合成 ino 互异且远离真实 ino）。
  - 它们**进入执法查找结构**：实现为唯一 8192 槽扁平数组、无分桶（审计 §4）；
    对 T→X 请求每条填充规则会通过 service/op/caller 与 operation/path_tail 两次
    strcmp 后在第 6 字段 ino 处失败，属单条最贵失败路径。
  - 目标规则对 T→X 不命中（caller_uid=A≠T）。因此 N>0 时**全部 N 条规则均不命中
    T→X 计时请求**，符合“始终允许的同一种请求”。
  - 诚实边界：≥64 条不同 (ino,s_dev) 时，第 65 条起不再进入 64 项 fd 血统缓存，
    但全部进入执法全表扫描（该缓存只服务 fd 血统审计，不服务裁决）。
- 动态值（A/B/T UID、X/Y ino、DEVRAW）逐 boot 运行时采集并写入该 boot 的
  `boot_cfg.json`，规则命令由冻结生成器按该 cfg 生成；合成 ino 固定 2,000,001…。
- **核实**：每个规模安装后读回 `policy_dump`，以 `runtime_policy_count` 与
  逐槽行数双重核对 == N；add 返回值（成功/ENOSPC）一并记录。绝不把“发送 N 次
  add”当作 N 条活跃规则。读回不匹配 → §8 冻结处理。

## 3. 夹具与计时边界
- 对象：espafd_tree 下 X.bin（计时与拒绝目标）、Y.bin（对象控制），初始内容
  "0123456789ABCD"（16B），A 以 create 动作建立（Y 同）。backing s_dev 254:96。
- 允许请求计时：`com.demo.esptiming` 对 X.bin 以 "w" 打开；主指标=应用内
  `SystemClock.elapsedRealtimeNanos` 从 openFileDescriptor 调用前到 PFD 返回/异常
  （CSV 列 open_ns）。能力验证（写+fstat）、close、CSV、fixture 写入均在计时区间外。
- 正确性请求用 A/B 应用 write 动作（16B payload，见 payloads.json），返回
  WRITE_OK / WRITE_FAIL+异常类；后置核对文件 size/sha 与 dev/ino。

## 4. 日志配置（冻结，同 round-11 LOG_OFF）
- 每 boot 稳定后、首次使用 provider 前：`setprop persist.debug.cdac.logging_mode quiet`
  + `am force-stop com.android.externalstorage`；读回 getprop 记录。
- kernel：`mount -t debugfs debugfs /sys/kernel/debug`；`echo 0 >
  /sys/kernel/debug/iguard/verbose_audit`；读回记录。消融开关全部 0。
- 保持开启：上下文发布、规则查找、对象检查、真实拒止、全部钩子、quiet_counters。
- 正式采样期间不切日志配置；诊断（LOG_ON decision_ns）单独一段，在 §9，不混入主采样。

## 5. 健康检查（每 boot 正式数据前，失败即定位首个阻塞点，不混入性能数据）
- boot 指纹、`uname -r`、SELinux Enforcing、/dev/iguard_ctl 存在、verbose_audit=0、
  logging_mode=quiet、boot_completed、uptime≥180s 稳定。
- 小规模功能块：H0 clear → A→X WRITE_OK（原生合法）；H1 clear → T→X 计时 WRITE_OK
  （无规则能力可用）；H2 装目标规则 → A→X 真实拒止（§6 拒止判据全过）；H3 保持目标
  规则 → A→Y WRITE_OK、B→X WRITE_OK，clear 后 A→X WRITE_OK（对象/调用者控制+撤规恢复）。
- A/B/T 均有 espafd_tree 持久 rw grant（grants.txt 核验）；UID/X/Y ino 动态采集。

## 6. 正确性（boot1，非零规模各 3 轮；每轮同配置）
每轮（N=1,8,32,128）：clear → 装 config_N → 读回核实 N → 依次
- T1 A→X：期望 WRITE_FAIL；判据=①policy_dump 含目标规则且字段核对
  （service_id=5 op_id=401 caller_uid=<A> operation=openAssetFile ino=<X>
  s_dev=254:96 decision=deny；主体/对象/操作+规则状态）②app 未获可用能力
  （WRITE_FAIL，无目标 FD 交付）③X size/sha 不变（无副作用）
  ④quiet_counters file_open_deny +1（只有真实执法分支会加该计数器，为
  LOG_OFF 下的执法依据；iguard_vinfo 的 real-enforce 文本行在 LOG_OFF 被门控
  关闭，见 §9 单独捕获）。**原生拒绝、report-only 或仅 matched 记录均不计成功**。
- T2 A→Y：WRITE_OK，字节写入=16，size/sha=期望（对象控制）。
- T3 B→X：WRITE_OK，字节写入=16（调用者控制，B 持合法 grant）。
- T4 clear（读回 0）→ A→X：WRITE_OK（撤规恢复）。
位置检查（仅 N=128，少量）：clear → 装 127 填充 → 最后装目标 → 读回 128 →
A→X 拒止 ×3（同一判据）。填充规则 specificity 与目标规则不影响：目标规则是唯一
命中 A→X 的规则（填充 caller=T），位置无关；结果只作稳定性证据。
正确性失败不进入性能数据；失败轮次保留原始日志并登记。

## 7. 性能采样（冻结）
- 2 个独立 boot，顺序启动；每个 boot 全新 userdata（always_create）+ 全套 setup
  + 健康检查，再开始正式块。boot1 在正确性之后开始正式块；boot2 健康检查后直接
  正式块。两 boot 使用同一 schedule。
- 每 boot 20 个完整区组（schedule.csv，seed=20261026，4 个 5 阶拉丁方；每块含全部
  5 个规模各 1 次，每规模每列位置 4 次）。
- 每块内按 schedule 顺序：装 config_N（安装/读回/诊断采集全部在计时区间外）→
  T→X restore（区间外）→ logcat -c → `am start` timed 动作 warmup=5 record=5 →
  pull CSV → file_state → qc 计数 → policy_dump 快照。块末 clear（读回 0）。
- 每 boot 正式记录行：20 块 × 5 规模 × 5 = 500；两 boot 共 1000。**样本量冻结，
  不按结果增减、不无界补跑。**

## 8. 干扰/失败/排除规则（冻结）
- 有效行：result=WRITE_OK 且 open_ns=t1−t0≥0 且 ino=X 当前值（app 可见
  st_dev 为 FUSE 视图 0:45，轮 6 已记录为已知事实，不参与有效性判定；backing
  dev 254:96 用于规则）。
- 配置读回≠N：允许一次普通修复重装；仍失败 → 该配置标记 config-invalid，
  该配置行保留并排除出主分析，登记失败账本；继续下一配置（不无界重试）。
- 干扰阈值：块开始 host 1-min loadavg≥8.0（空闲基线约 1.6）→ 该块全部行标记
  disturbed，保留原始数据、排除出主配对分析、单独报告；**不重跑该块**。
- 失败/异常行（非 WRITE_OK）保留、登记，**绝不因延迟值删除样本**。
- 出现需改核心机制/容量/新增探针的问题：停止扩展并报告，不自行改。

## 9. 诊断（单独，不混入主采样）
- 主采样完成后一段 LOG_ON：verbose_audit=1，每个规模装 config_N 后 T→X 计时
  warmup=1 record=3，采集 kernel `perf … decision_ns` 与 policy add/clear cost_ns
  行（复用既有日志，**不为本轮新增内核计时探针**）。
- 同一段内对 N=1 与 N=128 各做一次 A→X 拒止，捕获
  `real-enforce … errno=-13 verdict=deny-now` 文本行（LOG_ON 下才会打印），
  作为 §6 拒止的文本执法依据证据（主体/对象/操作字段齐全）。
- 结束恢复 verbose_audit=0 并 clear。

## 10. 统计（冻结）
- 分位数：线性插值 R type-7（rank=(n−1)p）。报告每 boot 每规模 n、有效行、失败行、
  中位数、P95、min/max。
- 主对比：**同一区组内 T(N) − T(0)**。区组汇总口径=区内 5 行的中位数之差
  （N 规模中位数 − 本块 N=0 中位数）；每 boot 20 个配对差值 → 中位数/P95/min/max。
- 跨 boot：分别报告 boot1、boot2；跨 boot 一致性如实描述（仅 2 个 boot 样本）。
- bootstrap 置信区间（若给出）：按**区组**重采样（20 块有放回 10000 次，percentile），
  只适用于当前采样条件；不把每请求当独立启动样本。
- 拒绝请求（T1/位置检查）单独报告绝对/分布，**不与允许请求直接相减解释为拒止开销**。
- 解释固定口径：N=0 是同一 CDAC 制品的空规则参考，不是无 CDAC 基线；端到端差值
  ≠纯内核查询耗时；不与第 12 轮旧制品差值拼接；噪声淹没差异时写“当前测量未分辨”，
  不写零成本。
- 图表：每 boot 每规模中位数+P95 条形；配对差值 T(N)−T(0) 分布（箱线/散点）。

## 11. 停止与交付
- 完成冻结设计即停止；不追加路线/更大规模找趋势。
- 交付：00 实现与容量核查；02 PROTOCOL；03 规则生成器+schedule；01 制品哈希；
  04 原始日志/规则读回；06 逐次 CSV；05 正确性结果表；07 分析脚本/图/报告；
  耗时与失败记录；08 FINAL_STATUS.txt、SHA256SUMS.txt。
- 完成后干净停止并归档 cvd-21，结果交第 20 轮之后统一整合。
