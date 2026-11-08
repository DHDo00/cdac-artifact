# ALIGNMENT_PLAN_AMENDMENT_1 — 实例号/端口调整（2026-11-02T10:33+08:00）

原计划 A15 新增 boot 使用 cvd-95/ADB6614、cvd-96/ADB6615；执行中发现两个环境事实：
1. A15 的 launch_cvd（bp1a 冻结 host 工具）不支持 --enable_tap_devices 参数
   （attempt1 被拒），且默认启用 tap 设备；
2. 主机仅预建了 cvd-{e,m,w}tap-01..10 持久 tap（group cvdnetwork）；新实例号 95 需
   新建 tap，需 CAP_NET_ADMIN，而 sudo 需要密码（任务禁止索取/保存 sudo 密码），
   新建 tap 失败（crosvm "failed to create tap interface: Operation not permitted"）。

修正（只改基础设施绑定，不改科学协议）：A15 新增 boot 改用预建 tap 对应的实例号：
- A15B2 = cvd-2 / ADB 0.0.0.0:6521（运行盘 b2）
- A15B3 = cvd-3 / ADB 0.0.0.0:6522（运行盘 b3）
A16/A17 的 launch_cvd 支持 --enable_tap_devices=false，维持原计划 cvd-97/98/99、
ADB 6616/6617/6618 不变（其运行盘短目录 b97/b98/b99，内部 instance 子目录 i/instances）。
比较索引、制品、规则、矩阵、判定、失败处理均不变。全部已记录的失败尝试保留于
runs/a15_boot2/attempts.log，未删除、未重写计划正文。
