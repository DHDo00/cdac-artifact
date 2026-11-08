# PROTOCOL_FROZEN.md — 新增 boot 冻结协议（每版一致，沿用原协议）

冻结：2026-11-02T10:02+08:00。每个新增 boot 在正式采样前再写一份
runs/<boot>/protocol_frozen_<boot>.md（含本 boot 实测绑定值与冻结时刻）；本节不随后改。

## 0. 制品与运行态前提（每 boot 核验）
- 平台镜像/内核/host/APK 哈希与本版冻结值一致（见 ALIGNMENT_PLAN.md §4）；镜像副本
  sha256 与源一致后才启动。
- 运行态：release/sdk/REL/fingerprint、uname（6.12.74-android16-6-maybe-dirty）、
  Enforcing、/dev/iguard_ctl crw-rw-rw- iguard_ctl_device、boot_id 实测记录。
- A/B 为非 root 普通应用（untrusted_app），owner/redacted 原生授权不变；
  su 仅用于既有管理路径（iguardctl_test add/clear）。A15 保持 MediaProvider
  observer/tracing 冻结前提（不启用 tracer、不改回调）。

## 1. 预检（单列，不计正式 30）
1. 安装 app_a/app_b；pm grant READ_MEDIA_IMAGES 仅给 B。
2. app A 创建 image1(X)/image2(Y)；解析 URI_X/Y、BACK_X/Y、INO_X/Y、stat、sha；
   实测 uidA/uidB、Provider 进程域样本、App fstat dev（SDEV_X）。
3. 控制面回环：iguardctl_test add → policy_dump 逐字段读回 → clear → 读回 count=0。
4. 空策略探针：E_AX×3、E_BX×3——PFD 确实可用、读 911B、A=orig e22785cd…、
   B=redacted 96f60e…（B 按自己真值，不要求等于 A）；发布 msg5/msg6 ok 到达内核。
5. 预检结束写 uris.env + PROTOCOL_FROZEN_<boot>.md（冻结时刻早于首次正式请求）。

## 2. 正式矩阵（30 次，10 格×3）
| 块 | 规则状态 | 请求 | 次数 | 预期 |
|---|---|---|---|---|
| B0 | 无规则 | A→X | 3 | 允许 |
| B0 | 无规则 | B→X | 3 | 允许 |
| B1 | caller=A 拒、对象 X | A→X | 3 | 拒止 |
| B1 | 同规则 | B→X | 3 | 允许 |
| B1 | 同规则 | A→Y | 3 | 允许 |
| B2 | 反转 caller=B 拒、对象 X | B→X | 3 | 拒止 |
| B2 | 同反转规则 | A→X | 3 | 允许/恢复 |
| B2 | 同反转规则 | B→Y | 3 | 允许 |
| B3 | 撤规 | A→X | 3 | 恢复 |
| B3 | 撤规 | B→X | 3 | 恢复 |
B0=6、B1=9、B2=9、B3=6；期望 6 拒止+24 允许/恢复。B0–B3 是实验块，不是论文资格条件 B1–B4。

规则（每 boot 用本 boot 实测 uid/ino/sdev，reason 文本随版本）：
- A15：`add service_id=6 op_id=501 caller_uid=<uidA> operation=openFile ino=<INO_X> s_dev=<SDEV_X> i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason=a15cdac_r14a`
- A16：reason=cdac35_r14a；A17：reason=cdac35_r14a（保持各自冻结 reason 文本）。
- B2 反转：caller_uid=<uidB>，reason=a15cdac_rev / cdac35_rev。
- 装规/撤规均 policy_dump 读回；撤规=clear + runtime_policy_count=0 读回。

## 3. 逐请求核验
- 每条拒止六判据：规则读回；txn14/6/501 与 caller/对象正确；ENTER/PUBLISH 与
  PUSH/VFS_JOIN 可关联；matched=1、reason 对应；real-enforce errno=-13 deny-now；
  App EACCES 无可用 PFD；backing 前后状态/内容与 file_open_deny 计数对应。
- 每条允许/恢复：PFD 实际可用、读取成功、sha 符合 owner/redacted 真值；不以"未见拒止"代替。
- 连续捕获 logcat -v threadtime 与 dmesg -w（START/END 标记）；保留日志与定位索引。
  无逐写 scontext 继续标缺证，采样域不升级为逐次 write 证据。
- 记录各块/最终规则、计数器、push/pop、失配及文件状态；全 boot 总量与正式窗口增量分开。

## 4. 失败处理
- 前提不成立停止正式执行并记录；开始后有失败/无效/证据异常，保留实际尝试与原因，
  不删除、不自动补成功行、不事后宣称零重试、不无上限重跑求全绿。
- 任何重试保留原尝试。

## 5. 收尾
- 撤规读回 count=0；停止仅本轮实例；核验进程/端口；输入镜像 hash 前后一致。
