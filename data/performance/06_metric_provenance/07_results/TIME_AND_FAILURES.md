# TIME_AND_FAILURES.md — 第 35 轮 R1 补证：时间线与全部尝试/失败/环境故障记账

范围：R1(txn14/openFile) 主体反转最小矩阵，实例 cvd-35，1 个 boot。
冻结协议：03_protocol/PROTOCOL_FROZEN.md（冻结于 2026-10-29T00:07:41+08:00，
采样开始于 00:13:47，冻结先于采样）。

## 1. 时间线（host，Asia/Shanghai）
| 时刻 | 事件 |
|---|---|
| 2026-10-29 00:09:18 | 预启动状态记录（配置链接→27 轮 boot1；adb 空；无 cvd 进程） |
| 00:09:21 | launch_c35 分派（launch_pid=4071028） |
| 00:13:29 | BOOT_COMPLETED=1（attempts=49，ADB_OK，SELinux=Enforcing，Android 16，kernel 6.12.74-android16-6-maybe-dirty） |
| 00:13:47 | run_r35.sh 开始采样（B0） |
| 00:13:52 | uidA=10121、uidB=10122；X ino=2931、Y ino=2951（backing dev=65120=254:96） |
| 00:14:01–00:14:20 | B0 无规则原生前提 6/6（A→X 原字节、B→X redacted） |
| 00:14:21–00:14:53 | B1 R14A(caller=A)：A→X 3/3 拒止、B→X 3/3 放行、A→Y 3/3 放行；file_open_deny 0→3 |
| 00:14:55–00:15:24 | B2 R_rev(caller=B)：B→X 3/3 拒止、A→X 3/3 恢复、B→Y 3/3 放行；file_open_deny 3→6 |
| 00:15:26–00:15:38 | B3 撤规：A→X 3/3、B→X 3/3 恢复；runtime_policy_count=0 |
| 00:15:38 后 | 终止快照（counters/backing/proc attrs），run 结束 |
| 00:19:00–00:19:02 | stop_cvd rc=0，cvd-35 干净停止；无遗留进程/端口 |
| 00:20 | 恢复 $HOME/.cuttlefish_config.json → 预启动目标（27 轮 boot1 assembly） |

## 2. 请求记账（30/30，全部为正式，无预试行）
| 块 | 请求腿 | 尝试 | 结果 |
|---|---|---|---|
| B0 | A→X | 3 | 3 ALLOW_PASS（e22785…，marker present） |
| B0 | B→X | 3 | 3 ALLOW_PASS（96f60e…，redacted） |
| B1 | A→X | 3 | 3 DENY_PASS（real-enforce -13 deny-now） |
| B1 | B→X | 3 | 3 ALLOW_PASS |
| B1 | A→Y | 3 | 3 ALLOW_PASS（f3d29c…） |
| B2 | B→X | 3 | 3 DENY_PASS（real-enforce -13 deny-now） |
| B2 | A→X | 3 | 3 ALLOW_PASS（恢复） |
| B2 | B→Y | 3 | 3 ALLOW_PASS（redacted） |
| B3 | A→X | 3 | 3 ALLOW_PASS（撤规恢复） |
| B3 | B→X | 3 | 3 ALLOW_PASS（撤规恢复） |
合计 30 请求；6 真实拒止 + 24 允许/恢复。

## 3. 失败/异常/重试/环境故障（全部如实保留）
- 采样请求：**0 失败、0 重试**。30/30 一次通过，无需要重跑的腿。
- boot 等待：attempts=49（launch 脚本每 5s 轮询 sys.boot_completed，属正常
  冷启动；非故障）。
- 环境异常观察：
  1. launch.log 出现 "Failed to remove userdata.img / Could not open
     images/userdata.img"：与 `--data_policy=always_create --blank_data_image_mb=4096`
     下 launch_cvd 自建空白 userdata 的既有行为一致，boot 成功、无影响（保留原文）。
  2. dmesg 内核环形缓冲在 verbose_audit=1 下被 CDAC_FILE_LINEAGE/BINDER_NO_CONTEXT
     逐行淹没并旋转：per-request `dmesg|tail -80` 的 *_kernel.txt 因而**不含**每条
     拒止的 iguard decision 行；但同一批行已在 logcat main 缓冲的 *_framework.txt
     中完整捕获（iguard_ctx decision/decision-apply/real-enforce 全部在列）。
     判定以 framework.txt 为准；限制如实登记（不是逐条 dmesg 证据）。
- 无规则安装失败、无读回不一致、无环境崩溃、无宿主磁盘/内存问题。
- 未修改 SELinux/内核/框架/规则容量/发布接口；未触碰其它任务实例。

## 4. 环境清理与恢复
- cvd-35 stop_cvd rc=0；adb devices 空；无 crosvm/launch_cvd 残留。
- $HOME/.cuttlefish_config.json 恢复为预启动目标
  （27 轮 boot1/instance/assembly/cuttlefish_config.json）。
- /tmp/cf_avd_1000/cvd-35、/tmp/cf_env_1000/env-35 为正常实例元数据残留
  （历史各轮同样保留）；不属本轮目录，不做删除。
- 历史归档零写入；本轮全部产物仅在本轮目录。

## 5. 证据缺口（诚实保留）
- 无逐条 write 的 scontext 日志（proc/<pid>/attr/current 为采样时刻域证据，
  已采 setup/end 两份；与第 32/33 轮结论一致）。
- B 请求的 redacted 视图 sha=96f60e…（X）、3116065d…（Y），为合法非恒等视图；
  B→X 的“恢复可用”语义=redacted 视图能力，不是与 A 同条件。
- 1 boot（原第 27 轮协议即为 1 boot；本轮不新增跨启动重复，按原协议执行）。
