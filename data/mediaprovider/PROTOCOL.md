# PROTOCOL_FROZEN.md — MediaProvider 两项功能复现冻结协议（第 39 轮）
# 冻结：采样前。SCHEDULE.csv 种子=2026102939。本文件与排程冻结后不再改动。

## 1. 目标
- 实验 M（tab:media-selectivity，表 VII）：调用者—对象选择性。
  3 boots × 20 循环 × 10 条件 = 600 次正式请求；预期 120 拒止 + 480 允许/恢复。
- 实验 L（tab:media-method-selectivity，表 VIII）：已发布方法标签选择性。
  3 boots × 20 循环 × 8 条件 = 480 次正式请求；预期 120 拒止 + 360 允许/恢复。
- 合计计划 1,080 次正式请求（预期 240 拒止 + 840 允许/恢复）。实际结果按原始记录统计。

## 2. 构建与隔离（冻结）
- 构建：C19_media（system.img 009b68dc…/super.img 55f51a09…/boot.img cd536baa…）+
  kernel_openkeychain_dist（bzImage 0c0f7e4c…/initramfs.img 0fa2d559…/vmlinux c9d0e9ab…）。
  与历史 R35/R36 同一批冻结制品（sha256sum -c 本轮复验 OK）。
- 实例：**cvd-39**（base_instance_num=39；ADB serial=0.0.0.0:6558）。3 次独立 guest
  启动（boot1/2/3，userdata always_create）。不触碰 A15/A17/R38/cvd-74 与任何其它实例；
  不全局停止 CVD 或 adb server；不覆盖共享 out。
- 三项实验（M、L）在同一冻结构建、同一组三个 boot 内完成：每 boot 先 M 后 L。
- SELinux=Enforcing；不改 SELinux/内核/机制/信任模型/端点范围/原生授权。

## 3. 路线与调用者/对象（冻结）
- A=com.demo.espafdtest（owner，无 READ_MEDIA_IMAGES）；B=com.demo.espafdtestb
  （READ_MEDIA_IMAGES，redacted 视图）。UID 每 boot 动态读，要求 A≠B。
- X=image1.jpg（AAAA，911B，owner sha=e22785cd…）；Y=image2.jpg（BBBB，911B，
  owner sha=f3d29ccd…）。A 经 MediaStore 创建；每 boot 重新解析 dev/ino 与 URI，
  不机械沿用旧 inode。
- M 读：ContentProviderClient.openFile(uri,"r")→txn14 openFile→6/501（operation=openFile）。
- L 读：同上。L 写：ContentResolver.openFileDescriptor(uri,"w")→txn15 openAssetFile→
  6/501（operation=openAssetFile）。PFD/descriptor 与 backing 对象对应关系每请求记录。

## 4. 规则（冻结；安装前后 policy_dump 逐字段读回）
M（沿用 R35 形状，两规则仅 caller 不同，同一 X 对象限制）：
- MA：`service_id=6 op_id=501 caller_uid=<uidA> operation=openFile ino=<INO_X> s_dev=45 i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason=cdac39_ma`
- MB：`service_id=6 op_id=501 caller_uid=<uidB> operation=openFile ino=<INO_X> s_dev=45 i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason=cdac39_mb`
L（沿用 R36 形状，两规则仅 operation 不同；有效访问标志掩码关闭）：
- LW：`service_id=6 op_id=501 caller_uid=<uidA> operation=openAssetFile ino=<INO_X> s_dev=0 i_mode=00 f_flags_mask=0x0 f_flags_value=0x0 decision=deny reason=cdac39_lw`
- LR：`service_id=6 op_id=501 caller_uid=<uidA> operation=openFile ino=<INO_X> s_dev=0 i_mode=00 f_flags_mask=0x0 f_flags_value=0x0 decision=deny reason=cdac39_lr`
撤规=iguardctl_test clear + runtime_policy_count=0 读回。每次状态切换保存 add/dump
（及 clear/dump）结果，等待更新完成后再发送该状态正式请求。

## 5. 冻结矩阵（每循环，见 SCHEDULE.csv）
M（10 条件/循环；每 boot 20 循环；两规则顺序 RA→RB 与 RB→RA 各 10 次）：
| 状态 | 请求 | 预期 |
|---|---|---|
| S0 无规则 | A→X, B→X（顺序随机） | usable / usable |
| R1/R2=MA(caller=A) | A→X denied；B→X usable；A→Y usable（随机） | |
| R1/R2=MB(caller=B) | B→X denied；A→X usable；B→Y usable（随机） | |
| S3 撤规 | A→X, B→X（随机） | usable / usable |
L（8 条件/循环；每 boot 20 循环；LW→LR 与 LR→LW 各 10 次）：
| 状态 | 请求 | 预期 |
|---|---|---|
| S0 无规则 | openFile/r usable；openAssetFile/w usable（随机） | |
| R1/R2=LW(openAssetFile) | r usable；w denied（随机） | |
| R1/R2=LR(openFile) | r denied；w usable（随机） | |
| S3 撤规 | r usable；w usable（随机） | |
- 每次“允许”的写请求后执行 restore_mp 恢复 X 原字节并校验 backing sha=e22785cd…
  （恢复/维护单列，scientific=0）。拒止写无副作用，不恢复。

## 6. 逐请求判定（冻结；不得事后改 oracle 或删分母）
- usable：PFD 实际返回并通过对应 caller/view/mode 的原有成功使用 oracle：
  读=回读字节数+sha+marker_present 与真值一致；写=PFD 可写 911B+写后 backing sha=
  该请求 token 的冻结期望 sha（随后恢复）。仅不抛异常不算 usable。
- denied：调用失败且未交付 PFD，并存在该请求对应的 CDAC 匹配与执法证据：
  policy_dump 含目标规则 → ENTER(caller 正确) → PUBLISH msg5 ok → decision
  matched=1 reason=<对应 reason>（operation/obj_ino 匹配）→ real-enforce errno=-13
  deny-now；App 观测 FileNotFoundException:EACCES 或无 PFD。单独 SecurityException/
  权限缺失/普通打开失败不算 CDAC 拒绝。
- 应用结果明确但执法归属或证据缺失：保留应用结果，执法证据列 unresolved，不补造匹配。
- 预期不符=实验结果；全部实际调用、超时、异常、重试及原因进入总 ledger。
- 排程内每请求唯一 reqid，关联 study/boot/cycle/condition/exec_order/caller/入口/
  method/mode/URI/规则状态/应用结果与服务/内核记录（客户端 pid/tid、binder context_id/
  seq、server_tid、ts_ns 证据完成关联）。

## 7. 预检（单列，scientific=0，先于正式批次）
每 boot：创建 X/Y → A→X 读、B→X 读、A→Y 读、B→Y 读、A→X 写+restore →
4 条规则 add/dump/clear 往返 → 对象/域/计数器快照。校验：
- 读真值与 §3 冻结 sha/marker 一致（B 为 redacted）；
- 写 token 的 app 上报 sha == 主机离线计算的 write_sha（oracle 验证）；
- 4 条规则 dump 逐字段与 §4 一致；clear 后 count=0。

## 8. 每次真实启动证据（BOOT_LEDGER.csv + raw/<boot>）
/proc/sys/kernel/random/boot_id、启动日志（launch.log）、ADB serial、实例/镜像记录、
ro.build.fingerprint/SDK/内核/SELinux/MediaProvider 版本、启动/停止/清理时间。
服务重启不算新 boot；boot 内固定 X 的 ino 与 UID。

## 9. 修复口径
正式执行后不为凑全成功改机制、换 boot 或替换失败单元；必要修复用新 campaign，
旧批次完整保留并分别报告。本轮不把 60 请求写成 60 boot，也不做性能测量。
