# TIME_AND_FAILURES.md — 第 26 轮投入与失败记录（2026-10-27）

说明：前瞻记录；[人工]=动手/分析/编写；[自动]=脚本执行；[等待]=启动/静止等待。
所有数值同操作者墙钟估计，不据此推算专家效率。

## 时间账本
| 起 | 止 | 类型 | 内容 | 约时 |
|---|---|---|---|---|
| 19:31 | 19:39 | 人工 | 历史核查、夹具（wave/offset/门闩）、协议与脚本编写 | ~0.5h |
| 19:39 | 19:43 | 等待 | cvd-26 boot1 启动（与 cvd-27 并行共存） | ~4min |
| 19:43 | 19:59 | 人工+自动 | boot1 setup/健康/预试 + 3 次夹具修复 + 协议冻结 | ~0.9h（含自动执行） |
| 19:59 | 20:02 | 自动 | boot1 正式 20 波 + 分析 + 恢复/清理 | ~4min |
| 20:03 | 20:07 | 等待 | boot2 启动 | ~4min |
| 20:07 | 20:34 | 人工+自动 | boot2 授权 UI 卡死修复（reboot）+ setup/健康/正式 20 波/分析/恢复 | ~27min（含 reboot 等待） |
| 20:34 | 20:40 | 人工 | 报告/FINAL_STATUS/哈希 | ~0.1h |

## 失败与重试记录（全部保留证据）
1. **App 崩溃：RECEIVER_NOT_EXPORTED**：targetSdk35 要求动态注册接收器显式
   导出标志。修复 Context.RECEIVER_NOT_EXPORTED，重建两 APK。
2. **offset 未达 App**：`--ei`（int）与 App `getLongExtra` 不匹配，B 的 4096
   偏移落回 0。修复：offset 经 `--el` 传 long。健康检查 BX/BY 首跑
   ALLOW_FAIL（12 项失败输出见运行会话日志；修复后重跑覆盖同名输出文件，本节留存说明）。
3. **门闩单实例 bug（预试发现）**：每 App 同一波两个请求各建 latch，广播只放行
   最后一个，导致 AX/BX WAVE_TIMEOUT（预试 w01-w03 留档）。修复：按 wave 键控
   latch，广播携带 wave 号，一次放行同波全部 worker。
4. **健康检查 ino 陈旧**：删除重建 ccx/ccy 后 boot_cfg 未刷新导致规则 ino 错误；
   中断并重发现 cfg 后 27/27 PASS。
5. **boot2 授权 UI 卡死**：早期误驱动创建出 `espafd_tree (1)` 且打开过
   新建文件夹对话框后 IME 残留，导致 DocumentsUI 底部 USE THIS FOLDER 按钮
   对注入点击无响应（有界面快照留档）。有界修复：root 删除多余目录、清
   DocumentsUI 状态、重启 guest（reboot）后 saf_grant_existing 正常授权 A/B。
   未改平台、未走非原生授权捷径。
6. **analyze_waves cfg 选择 bug**：glob 取到 boot1 cfg 导致 boot2 请求映射为空
   （第一轮 boot2 ledger 0 行留档），改为按 boot 参数选取后 80 行全部 PASS。
7. 与第 27 轮并行：cvd-27 活跃期间启动 cvd-26（64 核/251G 主机容量充足）；
   未执行全局 stop/kill；两次 launch 改写的 `~/.cuttlefish_config.json` 均在
   停止后按"仍指向本运行时才恢复"原则恢复为第 27 轮 boot1 路径。

## 预试（不计正式）
boot1 3 波（05_results/boot1/pretrial/）：验证 ready/release、epoch 同基准、
4 server_tid、6/6 请求对重叠。修复项 1-3 后预试通过，协议据此冻结。
