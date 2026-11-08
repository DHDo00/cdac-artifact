# PROTOCOL.md — 第 26 轮多主体真实并发下的选择性执法验证（2026-10-27，预试后正式运行前冻结）

## 0. 隔离、并行与共享元数据协调
- 实例 cvd-26（`--base_instance_num=26`，ADB serial `0.0.0.0:6545`）；两个
  boot **顺序启动、不同时运行**（boot1 完整结束并 stop_cvd 干净停止后启动 boot2）。
- 运行目录 `04_runtime/{boot1,boot2}`；输出 `05_results/{boot1,boot2}`。
- 与第 27 轮（cvd-27/6546）并行共存：不修改其源码/制品/实例；不执行全局
  stop/kill；不恢复其仍使用的配置链接。共享 Cuttlefish 元数据协调：仅在其
  launch 完成（boot_status 就绪）后启动本实例；本实例 launch 若改写
  `~/.cuttlefish_config.json`，在停止后仅当该链接仍指向本运行时才恢复为启动前
  目标，否则不改动。
- 每波记录 host 1-min loadavg（记录用，不据此挑样本）。SELinux Enforcing；
  不改核心机制/规则容量/平台时序。

## 1. 路线、制品、主体、对象（冻结）
- 路线：ESP 5/401 openDocument 写分支；主模式 "w"（非截断；每 boot 以 VFS_JOIN
  实测 f_flags 复核=0x8041，无 O_TRUNC）。
- 制品：android_matchedimg_newsystem + kernel_esp_dist + iguardctl_test（哈希见
  FREEZE_MANIFEST）。
- 主体：A=com.demo.espafdtest、B=com.demo.espafdtestb（UID 每 boot 动态；
  两者均经 SAF 对 primary:espafd_tree 持持久 rw grant，read/write=true 读回核验）。
- 对象（本轮自建）：`espafd_tree/ccx.bin`（X）、`ccy.bin`（Y），初始为空
  （content "-"）；权威对象=backing `/data/media/0/espafd_tree/*` stat
  dev(254:96)/ino；join 的 s_dev+ino 核验；proxy 0:45 仅投影记录。
- 能力验证：允许请求经返回 PFD 在**预先划定偏移**写 16B 标记：
  A 偏移 0、B 偏移 4096（同一文件 A/Y 与 B/Y 因此互不覆盖，避免夹具数据竞争）；
  波后以 root dd 读该偏移 16B 与期望 sha256 比对。

## 2. 主规则与预期（冻结）
- `add service_id=5 op_id=401 caller_uid=<A> operation=openAssetFile
  ino=<X.ino> s_dev=<DEVRAW> i_mode=00 f_flags_mask=0x3 f_flags_value=0x1
  decision=deny reason=rcs26_tgt_A_X`
- 预期：A→X 真实拒止（无 PFD）；A→Y、B→X、B→Y 原生合法、成功、能力可用。
- 装/撤均 policy_dump 读回逐槽核对；撤规后串行恢复检查 A→X。

## 3. 串行健康检查（正式波前，每 boot；各请求 ×3）
- H0 无规则：A→X/A→Y/B→X/B→Y 串行成功、偏移标记读回一致。
- H1 装规则：A→X 串行真实拒止（决策 matched=1 reason=rcs26_tgt_A_X +
  real-enforce errno=-13 + App 失败 + file_open_deny 增量），其余 3 允许。
- H2 撤规：A→X 串行恢复。
- 失败时修复夹具/部署并保留尝试；不能恢复则 BLOCKED，不进入正式波。

## 4. 客户端同步（冻结；预试单独列）
- 每波 4 请求：AX=A→X(offset0)、AY=A→Y(offset0)、BX=B→X(offset4096)、
  BY=B→Y(offset4096)，启动顺序固定 AX,AY,BX,BY。
- 每 App 用独立工作线程执行本波请求；主线程仅接收 `am start` 并下发任务。
- ready/release：各 App 波动作先写 `<label>.ready` 并阻塞在 CountDownLatch；
  主机轮询 4 个 ready 后发送一条 `am broadcast -a com.demo.cdac26.RELEASE`
  （两 App 动态接收器同时放行）。协调仅客户端；Provider/内核无额外等待。
- 波超时（ready 15s / 完成 15s）记失败并**有界重试一次**（仅夹具/基础设施
  原因），失败记录保留，不据此追加波次；正式 20 波不因重叠不足追加。

## 5. 正式波次（冻结）
- 每 boot 固定 20 波；每波 4 请求；label=`r26_{b1|b2}_w{01..20}_{AX|AY|BX|BY}`；
  标记=p16(label)（16B）。规则在第 1 波前安装并读回，全程保持，结束后撤规。
- 每波采集：主 logcat `-v epoch`（framework ENTER/EXIT/PUBLISH/STACK_MISMATCH）、
  `logcat -b kernel -d -v epoch`（PUSH/POP/JOIN/decision/real-enforce/
  STACK_MISMATCH/CTL_REJECT，service_id=5 过滤）、逐 label App CSV、偏移标记、
  quiet_counters 前后差、host loadavg、设备时钟锚
  （`date +%s.%N` + 本地时间串，用于跨格式时间换算）。
- 时序基准与重叠判据（冻结）：
  - 主判据（同一日志面内核缓冲）：请求 i 的 join/decision/real-enforce 时间点
    落在请求 j 的 [PUSH, POP] 活动区间内，且 server_tid_i ≠ server_tid_j；
  - 次判据（跨面）：内核 decision/join 时间点落在 framework
    [CONTEXT_ENTER, CONTEXT_EXIT] 区间内（两者换算到同一 epoch 基准）；
  - 未满足主判据的波=未重叠；时间/seq 无法唯一关联的请求=关联证据不足。
  - 预试时校准 logcat `-v epoch` 对 kernel 缓冲的行为，记录换算参数。
- 不允许把全部发起请求计为并发样本；不凭时间接近拼接日志；辅助 open、后台
  FUSE/扫描事件与观测动作单独标记，不归入业务请求。

## 6. 逐请求关联与正确性（冻结）
每请求记录：wave/request ID、App uid/pid/tid、server_pid/server_tid、
CONTEXT_ENTER/EXIT(remaining_depth)/PUBLISH(5/6)、kernel PUSH/POP(remaining_depth)、
JOIN（caller_uid/ino/s_dev/f_flags/join_result/stack_result）、decision/reason/
real-enforce、App 结果/ex/n、偏移标记。
- 主体正确=ENTER.caller_uid 与业务主体一致；对象正确=decision.obj_ino 或
  JOIN.ino 与 X/Y 权威 ino 一致；操作正确=operation=openAssetFile、
  f_flags=0x8041。
- A→X 真实拒止判据（综合）：policy_dump 规则读回 + seq 关联的
  decision matched=1 reason=rcs26_tgt_A_X + real-enforce errno=-13 +
  App WAVE_FAIL（无 PFD/无 n/无 ino）+ file_open_deny 增量。
- 允许请求判据：App WAVE_OK n=16 + 该 seq 无 deny + JOIN 对象/主体正确 +
  偏移标记 sha 一致。
- 清理：无 STACK_MISMATCH；逐请求 EXIT/POP remaining_depth=0；
  context_push/pop_fail=0；波末服务端 espafd_tree FD 稳定快照 NONE；
  计数器按第 23 轮口径（rule_match_total 不作 file-open 命中；push/pop 平衡
  不单独证明归属）。

## 7. 预试（正式冻结前，单独记录）
- boot1 上最多 3 个预试波验证 ready/release、App 波动作、logcat epoch 校准与
  server_tid 分布；预试数据写入 `05_results/boot1/pretrial/`，不计正式 20 波。

## 8. 停止与交付
- 完成 2 boot × 20 波即停止；重叠不足如实报告覆盖不足，不无限重试/追加。
- 交付：PROTOCOL、制品与夹具来源、同步脚本/规则/schedule、原始日志、逐请求
  ledger、重叠波次与事件关联表、正确性/清理/未决结果、
  CONCURRENT_ATTRIBUTION_REPORT.md、TIME_AND_FAILURES.md、FINAL_STATUS.txt、
  SHA256SUMS.txt。完成后干净停止并归档 cvd-26，不触碰第 27 轮。

## 预试结果（冻结记录，正式数据不计入）
2026-10-27 boot1 预试 3 波（pretrial/）：ready/release 广播同步有效（每波 ~0.6s
完成）；每波 4 个请求映射到 4 个不同 server_tid；主判据 6/6 请求对
decision/join 时间点落在对方 [PUSH,POP] 区间内；`logcat -b kernel -d -v epoch`
与主 logcat 同为 epoch 基准（同一时钟面），无需换算。夹具修复（接收器导出标志、
按波键控 latch、offset 用 --el）已记录 TIME_AND_FAILURES。冻结后不再修改同步
机制、波数、顺序或判据。
