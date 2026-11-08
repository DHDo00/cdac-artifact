# PROTOCOL_FROZEN.md — R1 主体反转最小补证冻结协议（第 35 轮）

冻结时间：2026-10-29（采样前冻结；任何采样开始前本文件不再改动）。
依据：原协议=第 27 轮 03_protocol/PROTOCOL.md + 第 29b 勘误更正 4（R1 缺项表）。
本协议只补充 R1 缺失项，不重复/不重定义第 27 轮已完成项作为新结论。

## 1. 运行资格（已在 R1_PROTOCOL_RECONCILIATION.md §10 核对通过）
- 路线=原 R1：C2=ContentProviderClient.openFile(uri,"r") → txn14 openFile →
  MediaProvider.openFile → openFileCommon → 6/501（preview-enforce）。
- A/B=可区分真实非 root 调用者；对象 X/Y 可合法建立；原始主体经既有可信发布
  路径到达现有检查点；现有制品支持该路线实际拒止；对象/操作/能力返回位置可确认。

## 2. 环境与隔离（冻结）
- 实例：**cvd-35**（--base_instance_num=35；ADB serial=0.0.0.0:6554）。
  仅此一个隔离运行实例；不启动/连接任何其它任务实例；不对全局/其它实例 stop。
- 运行目录：06_runtime/boot1（全新）；userdata 8GiB truncate + always_create。
- 制品只读复用：C19_media + kernel_openkeychain_dist（哈希见
  00_inputs/INPUT_AND_VERSION_CHECK.md §4，sha256sum -c 已 OK）。
- SELinux=Enforcing；不修改 SELinux/内核/受信服务/CDAC 核心机制/端点范围/
  原生授权；不做 publish-only 接口切分、κ 复验、report-only 计拒止。
- 客户端：复用第 27 轮冻结 APK（app_a/app_b，本轮复制到 04_fixtures/ 并实测
  哈希与 27 轮 FIXTURE_SHA256 一致）；夹具普通错误可修复并全量记账。
- 策略工具：iguardctl_test（493e8e80…）→ /data/local/tmp/iguardctl_test。

## 3. 对象与真值（冻结）
- A=com.demo.espafdtest（owner）；B=com.demo.espafdtestb（READ_MEDIA_IMAGES，
  无 ACCESS_MEDIA_LOCATION）。UID 每 boot 动态读（package list packages -U）。
- A 经 MediaStore.Images insert 创建 X=image1.jpg(AAAA,911B)、Y=image2.jpg(BBBB,
  911B)。backing=/data/media/0/Pictures/*.jpg（dev 254:96，ino 动态）。
  解析后冻结 {BACK_X,BACK_Y,INO_X,INO_Y,URI_X,URI_Y}（记录 stat dev:ino）。
- 能力对象键（规则侧）＝**FUSE upper 0:45、同 ino**（App fstat 0:45；27 轮实测）。
- 真值字节：X 原字节 sha=e22785cd…（A 视图）；Y 原字节 sha=f3d29ccd…；
  B 的 redacted 视图 sha=96f60e…（非 A 同条件，仅主体不命中控制）。
- 对象身份若随启动变化：按原对象语义重新解析并记录 dev/ino；**不复用失效规则
  后把未命中计作主体选择性**。

## 4. 规则形状（冻结；安装前后均 policy_dump 逐字段读回）
- 块 1（A 拒止，基线控制）R14A：
  `service_id=6 op_id=501 caller_uid=<uidA> operation=openFile ino=<INO_X> s_dev=45
   i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason=cdac35_r14a`
- 块 2（主体反转，本轮核心）R_rev：
  `service_id=6 op_id=501 caller_uid=<uidB> operation=openFile ino=<INO_X> s_dev=45
   i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason=cdac35_rev`
- 读回判据：policy_dump 含且仅含预期规则；runtime_policy_count==1；
  caller_uid/operation/ino/s_dev=0:45/f_flags/decision 与冻结值一致。
- 撤规=`iguardctl_test clear` + 读回 runtime_policy_count=0。

## 5. 冻结实验矩阵（C2 链；每腿 3 次；顺序 B0→B1→B2→B3，同 boot）
| 块 | 规则状态 | 请求 | 预期 |
|---|---|---|---|
| B0 | 无附加规则 | A→X ×3 | 原生可用（原字节） |
| B0 | 无附加规则 | B→X ×3 | 原生可用（redacted 视图） |
| B1 | R14A(caller=A) | A→X ×3 | CDAC 真实拒止 |
| B1 | 同一 R14A | B→X ×3 | 保持可用（主体不命中） |
| B1 | 同一 R14A | A→Y ×3 | 保持可用（对象不命中） |
| B2 | R_rev(caller=B) | B→X ×3 | CDAC 真实拒止 |
| B2 | 同一 R_rev | A→X ×3 | 恢复可用（主体不命中） |
| B2 | 同一 R_rev | B→Y ×3 | 保持可用（对象不命中） |
| B3 | 撤规 | A→X ×3 | 恢复可用 |
| B3 | 撤规 | B→X ×3 | 恢复可用 |

合计 10 组 × 3 = 30 次请求；额外控制=装规/撤规读回、quiet_counters 前后快照、
对象前后 stat、进程域采样。不因中途看到成功/失败临时改变样本量。
第 27 轮已完成的 A 规则下 A→X 拒止与 B→X/A→Y 控制在本 boot 内重跑仅为
“同一 boot 内对照与恢复语义连续”，不重复计为第 27 轮新结论。

## 6. 判定标准（冻结；逐条严格）
**真实拒止通过（B1-A→X、B2-B→X 每腿）**，全部满足：
1. policy_dump 含目标规则且字段核对（caller/operation/ino/s_dev/f_flags）；
2. 该请求 ENTER（caller_uid 正确）→ PUBLISH(msg_type=5, result=ok) →
   VFS join（对象=0:45/INO_X，f_flags=0x28000）→ decision matched=1
   reason=对应 reason → decision-apply → `real-enforce … errno=-13 verdict=deny-now`；
3. App 观测 FileNotFoundException/EACCES（无 READ_CPC ok 行）；
4. **无 PFD 交付**（App 无 fstat/bytes 输出；FD 未交付）；
5. backing X 前后 stat（dev/ino/size/mtime/sha256）不变；
6. quiet_counters file_open_deny 计数 +1。
**允许通过**：App READ_CPC ok 且 bytes/dev/ino/sha/marker 与真值一致
（B 为 redacted sha），该 seq 无 matched=1/real-enforce，计数 deny 不增。
**不通过的情况**：原生权限拒绝、发布失败/内核无帧、规则存在但未命中、
report-only、客户端异常但拒止来源不明、FD 未交付但文件状态未采集即声称文件不变。

## 7. 逐请求 ledger 字段（冻结）
run_id、boot/session、block、seq、rule_version(policy_dump 文本哈希)、
client_pkg/client_uid/client_pid、entry(txn14 openFile)、service_id/op_id、
operation、context_id、PUBLISH(msg5) 结果、server_pid/server_tid、
join 次数与命中 join 的 ino/s_dev/f_flags、matched、decision action、
real-enforce errno/verdict、app_result、fd_delivered、bytes/sha/marker、
backing X/Y stat 前后、file_open_deny 增量、verdict、证据文件路径。

## 8. 进程域证据（冻结）
- 采样时刻采集 /proc/<pid>/attr/current：app A、app B、MediaProvider 进程
  （进程 pid 以 ps 实测）。这是**采样时刻的域证据**，不自动成为每条 write 的
  逐条 scontext；无既有逐条观测能力时保留限制，不为补日志改核心机制。

## 9. 尝试/失败/环境故障/重试记账（冻结）
- 所有尝试、失败、环境故障与重试分别记账（TIME_AND_FAILURES.md + ledger），
  不删除不利结果；预试行与正式行分列；规则安装/清除均读回；
  结束时 runtime_policy_count=0 并读回。

## 10. 停止条件
- 若 boot 无法到达、ADB 不可达经 120 次轮询仍失败、或必须超出本轮范围的平台
  构建/机制变更才能继续 → 记录阻塞并停止运行分支（写运行阻塞报告，不伪装完成）。
- 完成后 stop_cvd 干净停止 cvd-35；不触碰其它实例。

## 11. 结论口径预冻结
- 主体反转通过只支持 C2(txn14/openFile) 该路线的调用者选择性；
- 不证明设备边界独立认证自报字段；不解决 publish-only 权限耦合；
- 不扩展为任意并发、其它 Provider、旧版本兼容。
