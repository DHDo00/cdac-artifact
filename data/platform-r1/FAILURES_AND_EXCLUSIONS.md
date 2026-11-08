# FAILURES_AND_EXCLUSIONS.md — 失败尝试与排除项（如实记录）

## 1. 启动失败（全部保留原始日志，未删除）
| # | boot | 时刻 | 现象 | 原因 | 处理 |
|---|---|---|---|---|---|
| 1 | A15B2 | 10:11:33 | launch_cvd 拒绝 --enable_tap_devices | A15 bp1a 冻结 host 工具无该参数 | 移除该参数后重试（已记 attempts.log） |
| 2 | A15B2 | 10:16:53 | run_cvd Check failed: namelen=118 > 108 | 运行盘路径过长超 AF_UNIX 108 字节 | 运行盘短目录 b95/b2/b3 + instance 子目录 i/instances（ALIGNMENT_PLAN_AMENDMENT_1） |
| 3 | A15B2 | 10:24:58 | userdata.img 路径错位（launch_cvd 在 instance_dir/instances/cvd-N 下找） | 脚本把 userdata 放到了 instance_dir/cvd-N | 改为 instance_dir/instances/cvd-N 后重试 |
| 4 | A15B2 | 10:32:55 | crosvm 新建 tap 失败 Operation not permitted | 新实例号 95 无预建 tap、sudo 需密码（任务禁索取密码） | A15 改用预建 tap 的 cvd-2/cvd-3（修正案 1） |
| 5 | A16B2 | 11:17:xx | crosvm 新建 tap 失败 Operation not permitted | 生成脚本误删 --enable_tap_devices=false | 恢复该参数后重试（已记 attempts.log） |
| 6 | A16B2 | 11:22:49 | 预检 make_image1 无 URI | A16 夹具 APK 在 app_a/build/ 子目录 | 修正 APK 路径，同 boot 重跑预检（正式请求未开始） |
| 7 | A16B3 | 11:30:57 | 预检 make_image1 无 URI | 同上（A16 夹具 APK 子目录路径） | 修正后同 boot 重跑预检（正式请求未开始） |

正式请求阶段失败：0（截至 A16B2；A15×2、A16×1 已各自 30/30）。

## 2. 批次排除（EXISTING_BATCH_ELIGIBILITY.csv 详列）
- A15 旧制品 cvd-7（system.img=186ea808…）：旧清理实现，不能与修正制品合并为 60/90；
  单列历史。
- A16 R36（cvd-36 两 boot、operation selectivity 48 请求、s_dev=0 通配、reason=cdac36_op）：
  不同冻结协议/规则语义，不能替代 R35 B0–B3。
- A16 R39 M（cvd-39 三 boot、600 请求大矩阵、reqid 客户端 APK 13e4d592/21339bce、
  reason=cdac39_ma/mb）：不是独立冻结的完整 30 请求 R35 批次；不得事后挑 30 行。
- R25 txn23、R16 txn15：其他研究/路线，不并入 R1 90 分母。
- 未发现 A17 第三完整合格 boot → 本轮补 1 boot（A17B3）。

## 3. 反例与前提不成立
- 诊断 4/301：Error 后同进程继续服务 NOT_ESTABLISHED（进程终止、TXN4 无服务端 ENTER）；
  不把 D1–D4 一概改成 PASS（REPORT_ERRATA ER2）。
- A15 旧制品 E5 缺口（exit 在 try/finally 后）：历史 gap，已被修正制品取代；修正前后分列。
- 历史缺证（保留，不回填）：A15/A16/A17 首轮 boot_id 未记录；逐写 scontext 无；
  A17 清单记账缺陷 + 3 条未归因发布；A17 boot2 debugfs-after-root 顺序 bug。
