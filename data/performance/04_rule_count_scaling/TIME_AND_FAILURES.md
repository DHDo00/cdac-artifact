# 实际耗时与失败记录（round-21，2026-10-26，单人墙钟）

## 时间线（本地 CST，日志时间戳为据）
- 16:50–16:57 历史证据检索 + 规则实现核查 + 制品哈希复核。
- 16:52–17:00 工作区建立、实现审计、制品来源、PROTOCOL 冻结、规则生成器、
  schedule、驱动与分析脚本（冻结清单见 02_protocol/FREEZE_MANIFEST.sha256）。
- 17:01:03 boot1 启动；17:05 boot_completed；17:07 boot_prep（uptime≥180s、
  LOG_OFF 核验）；17:07–17:09 setup（APK/工具/三项 SAF 授权/X/Y 夹具）。
- 17:10–17:14 boot1 健康块 + 正确性（4 规模×3 轮×4 步 + N=128 位置检查 3 次）。
- 17:20–17:58 boot1 正式性能采样 20 区组（100 配置、500 记录行）。
- 18:08:50 boot1 stop_cvd；全局 config 符号链接恢复。
- 18:09:28 boot2 启动；18:13 boot_completed；18:15 boot_prep；18:15–18:17 setup。
- 18:18 boot2 健康块（H0–H3）。
- 18:20–18:30 boot2 正式性能采样 20 区组（100 配置、500 记录行）。
- 18:30–18:31 LOG_ON 诊断（decision_ns 每规模 + N=1/N=128 拒止文本行）。
- 18:31:42 boot2 stop_cvd；ADB 断开；配置链接恢复。
- 18:32–18:36 统计/图表/报告/状态/哈希。
合计约 1.7h（含两次完整 boot 部署与采样；无平台构建）。

## 失败/异常记录（全部保留，无静默丢弃）
1. setup 首次读取 timing grants.txt 时为空——grant 实际已持久化，只是文件写入
   与读取竞态；随即 logcat TREE_PERSIST_OK + 重读确认三个应用授权齐全。
   属普通夹具核验问题，不重跑采样。
2. 驱动脚本健康块硬编码 payload 个别为 15/17 字节（协议正确性步用
   payloads.json 的 16 字节不受影响）；在正式正确性采样前修复为 16 字节，
   并给 one_request 增加长度断言。属普通脚本问题，修复保留记录。
3. 驱动 am_start 对所有 extra 均用 --es，导致 warmup/record 未按 int 传递，
   健康 H1 落到默认 20 行；修复为 int 用 --ei（在正式性能采样前修复并核验
   H1=1 行）。属普通脚本问题。
4. 冻结协议两处先于采样修订（合法，属协议冻结前/采样前修正并重哈希）：
   a) §6 拒止判据改为 LOG_OFF 下的“规则状态+file_open_deny 计数+无能力+无副作用”，
      real-enforce 文本行移至 §9 LOG_ON 诊断捕获；
   b) §8 有效行把 dev 判定细化为 ino==X（app 可见 dev 为 FUSE 0:45，轮 6 已知事实）。
5. 分析脚本文件名解析一处 bug（N0.csv 尾缀）已修复，不影响冻结统计口径。
6. 无需修改核心机制、容量或新增内核探针；未出现 config-invalid、disturbed、
   或无效性能行（两 boot 各 500 行全部有效）。

## 干扰监测
- 每区组开始记录 host 1-min loadavg：boot1 区间 1.37–3.34，boot2 1.67–3.65，
  均低于冻结干扰阈值 8.0；未观测到平台构建/论文编译高峰进入采样窗口。
- 宿主存在 round-19 遗留的 idle bazel 服务与 kworker 刷盘（未停止非本轮进程），
  loadavg 已记录于逐块 meta.json。

## 事后补充（18:38 观察）
- 本轮两次正式采样与诊断均结束于 18:31:42（boot2 stop_cvd）。18:34 起另一并行
  线程启动 22_media_special_branch_runtime_diagnostic_20261026 的 cvd-22 实例，
  位于本轮采样窗口之后，不与本轮正式延迟采样重叠；其进程/全局 cuttlefish
  配置链接均未由本轮触碰，本轮不停止非本轮进程。
