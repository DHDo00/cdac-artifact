# DISK_TIMELINE.md — 磁盘满事件与正式采样关系（2026-10-25，基于保留证据）

## 文件系统划分（关键）
- Root disk (`/home` and `/tmp`):guest 镜像副本、instance/userdata、
  主机侧 kernel.log/logcat/launcher.log 等。性能正式采样的 guest 数据分区
  也位于该盘上的 image 文件内。
- Data disk:04_samples 的 CSV（adb pull 落点）、项目文档。
  that disk stayed far from full，未受影响。
- The CSVs and host logs were therefore exposed differently to the disk event: the CSVs lived on the data disk, the host logs on the root disk.

## 时间线（本地 CST，证据等级标于行尾）
- 17:31:47 s0_p1_b1 采样开始（meta.txt，直接）。
- 17:45:08–17:45:29 e_p1_* 三块（直接）。
- 17:51:39 / 17:51:49 / 17:52:00 e_p2_* 三块开始；块内 CSV 各 200 行全部
  WRITE_OK（CSV 完整，直接）。主机 kernel.log 终态 uptime 256.82s、mtime
  17:52（logs_archive，直接）。
- 17:52:32 p2 enabled 停止（stop_cvd 输出，直接/转录）。
- ~17:53 首次 p2_s0 启动在复制 super.img 时
  `cp: error writing ...: No space left on device`（exec 转录；该次目录随后
  删除重建，其 launch.log 未保留 → 转录级证据）。
- 17:54–17:56 清理：df showed the root disk at 100% (0 avail)（转录快照）；删除 11 个
  运行目录的 images/instance（保留 logs_archive）；期间 r16 的 logs_archive
  mkdir 因 ENOSPC 失败（转录）。
- 17:56:41 p2_s0 第二次启动（保留 launch.log，直接）；17:58 BOOT_COMPLETED。
- 18:01:09 s0_p2_b2 采样（直接）。此后 p3/p4 各块正常（18:06–18:29，直接）。
- After cleanup the root disk had 194G free（转录快照）；124G free at re-check（本轮复核）。

## 判断
1) 磁盘满事件发生在 **17:52:32（p2 enabled 全部块结束/停止）之后、
   17:53 首次 p2_s0 启动之前**，即两次采样块之间，不与任何采样块重叠。
2) 采样期间无 ENOSPC 迹象：p2 enabled 三块 CSV 均 200 行完整 WRITE_OK
   （guest 写成功），主机 kernel.log 有完整终态；p1 及之后各块同样完整。
3) 没有连续磁盘监控，磁盘“达到 100%”的精确时刻只能以 17:52:32–17:53
   窗口间接界定；17:51:39–17:52:00 块与满盘时刻的最短距离约 30–80s。
4) 缺失记录：首次 p2_s0 的 launch.log（目录删除）；连续 df 序列；r16 原始
   guest 日志（logs_archive 因满盘未复制成功，其诊断内容已见于 09 轮）。

## 结论与补测建议
- The retained evidence supports that the disk event did not affect any saved performance block (CSVs on the data disk, successful guest writes, no overlap between blocks and the event).结论等级：高置信，但“满盘开始时刻”为间接推断。
- 无需按原协议重跑整批性能实验；不据此挑除任何批次。
- 若要消除最后的不确定性，仅需在下次性能轮次加入每块前后 df/ENOSPC 快照
  （新增观测，不重算历史）。
