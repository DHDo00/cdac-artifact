# CONCURRENT_ATTRIBUTION_REPORT.md — 多主体真实并发下的选择性执法验证（第 26 轮，2026-10-27）

路线：ESP 5/401 openDocument 写分支（"w" 非截断，join f_flags=0x8041 实测无
O_TRUNC）。制品=android_matchedimg_newsystem + kernel_esp_dist + iguardctl_test
（哈希见 02_protocol/FREEZE_MANIFEST.sha256）。实例 cvd-26（ADB 0.0.0.0:6545），
两个 boot 顺序启动，与第 27 轮并行共存、未触碰其文件/实例，共享 Cuttlefish
配置链接已按协议恢复。

## 一、设计（冻结协议见 02_protocol/PROTOCOL.md）
- 主体 A/B（UID 每 boot 动态：boot1/boot2 均为 A=10121、B=10122），经真实 SAF
  持久 rw grant 合法访问自建对象 X=ccx.bin、Y=ccy.bin。
- 主规则：`service_id=5 op_id=401 caller_uid=A operation=openAssetFile
  ino=<X.ino> s_dev=<DEVRAW> i_mode=00 f_flags_mask=0x3 f_flags_value=0x1
  decision=deny reason=rcs26_tgt_A_X`（装/撤均 policy_dump 读回）。
- 每 boot 20 波；每波 AX=A→X、AY=A→Y、BX=B→X、BY=B→Y。App 内独立工作线程 +
  ready/release 广播门闩（协调仅在客户端）。允许写使用预设偏移（A=0、B=4096）
  与逐请求 16B 标记，避免夹具自身数据竞争；返回 PFD 实写标记即能力使用证据。
- 串行健康检查（每 boot 27 项：H0/H1/H2 各请求 ×3）先于正式波完成。

## 二、服务端重叠（回答 1：实际确认多少波）
重叠判据（冻结）：请求 i 的 join/decision/real-enforce 时间点落在请求 j 的
[kernel PUSH, kernel POP] 活动区间内，且 server_tid_i ≠ server_tid_j；全部日志
用 `logcat -v epoch` 的同一 epoch 基准（预试校准：main 与 kernel 缓冲同基准）。
- **boot1：20/20 波确认服务端重叠**；每波 4 个不同 server_tid、6/6 请求对
  满足判据（合计 120 个请求对证据）。
- **boot2：20/20 波确认服务端重叠**；每波 4 个不同 server_tid、6/6 请求对。
- 示例（boot1 w01）：AX(tid4650)/AY(tid4652)/BX(tid10878)/BY(tid4827)；
  AX 的 real-enforce/decision 时刻 1793102404.834-836 落在 AY/BX/BY 各自的
  [PUSH,POP] 区间内，同时 AY/BX/BY 的 decision 亦落在对方区间。
- 未重叠波次=0；关联证据不足请求=0（每波 4 context_id 全部唯一映射到 4 个请求）。

## 三、逐请求主体/对象/结果关联（回答 2）
每请求按 seq/context_id 关联并核对：ENTER.caller_uid、decision.obj_ino 或
JOIN.ino（backing 254:96）、operation=openAssetFile、f_flags=0x8041、App 结果。
- AX：20/20（boot1）+ 20/20（boot2）真实拒止——decision matched=1
  reason=rcs26_tgt_A_X obj_ino=X + real-enforce errno=-13 + App WAVE_FAIL
  （无 PFD/无 n/无 fstat ino）+ 波级 file_open_deny 增量。
- AY/BX/BY：各 20/20 × 2 boot 允许成功——App WAVE_OK n=16、JOIN 对象/主体正确、
  无该 seq deny、偏移标记 sha 与期望一致（能力可用）。
- server_tid 与 kernel reporter_tid 逐请求一致；App uid/pid/tid 与业务主体一致。
- 结论：40 个重叠波中的 160 个请求全部完成主体-对象-结果正确关联。

## 四、正确性与清理（回答 3）
- **无错误拒止**：60/60 允许请求（AY/BX/BY）在两 boot 全部成功可用，无任何
  决策 matched=1/real-enforce 串入。
- **无错误放行**：40/40 A→X 全部真实拒止，无放行。
- **无上下文串用**：0 次 CDAC_CONTEXT_STACK_MISMATCH（框架与内核面均 0）；
  每请求 EXIT/POP remaining_depth=0；无嵌套/借用/stale 计数。
- 计数平衡（仅作辅助，不作归属判据）：boot1 push=pop=178、enter=exit=178、
  push/pop fail=0；boot2 110/110 同；file_open_deny 增量与拒止次数一致。
- 资源清理：两 boot 服务端 espafd_tree FD 连续三次稳定快照 NONE；
  撤规后串行 A→X 恢复 3/3（两 boot）；文件状态按允许/拒止分别核验（允许=标记
  可读，拒止=无写入）。
- 辅助 open/后台 FUSE/扫描事件：未以时间邻近并入任何业务请求；波内只有 4 个
  service_id=5 context 被关联。

## 五、未重叠与未决（回答 4）
- 未重叠波次：**0/40**（全部 40 波确认重叠）。
- 未决/关联证据不足请求：**0/160**。
- 平台限制如实记录：本轮仅证明 4 并发请求规模的归属正确性，不宣称任意并发度；
  协调为客户端级，服务端重叠由内核区间证据确认。

## 六、与第 24 轮相比新增证据（回答 5）
第 24 轮证明**同一服务线程在异常后顺序复用**时上下文正确清理与归属正确；
本轮新增**多服务线程真实重叠**下：4 个并发请求在 4 个 server_tid 上活动区间
重叠时，主体-对象-操作-结果逐 seq 关联全部正确，拒止/放行选择性在并发下保持
（A→X 拒、其余放），无跨请求身份/对象/判定串入、无 STACK_MISMATCH、无残留。
即"选择性执法"从串行/同线程扩展到多线程并发区间重叠的正交证据。

## 七、判定（按项目）
| 项目 | 结果 |
|---|---|
| 服务端重叠确认 | **通过** 40/40 波（每波 6/6 请求对） |
| 重叠请求关联 | **通过** 160/160 请求 |
| 并发选择性执法正确性 | **通过**（40 拒止 + 120 允许，零串扰） |
| 上下文清理/无串用 | **通过**（0 mismatch、深度 0、FD 无遗留） |
| 未重叠样本 | 0 |
| 未决样本 | 0 |
