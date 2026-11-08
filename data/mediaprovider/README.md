# README — 第 39 轮 MediaProvider 两项功能复现（mediaprovider_matrix_replication）

目录：39_mediaprovider_matrix_replication_20261029_230000
日期：2026-10-29（Asia/Shanghai）

## 内容概览
- 实验 M（tab:media-selectivity）：调用者—对象选择性；计划 3 boots × 20 循环 × 10 条件 = 600。
- 实验 L（tab:media-method-selectivity）：已发布方法标签选择性；计划 3 boots × 20 循环 × 8 条件 = 480。
- 构建：复用已验证 CDAC-enabled 冻结制品 C19_media + kernel_openkeychain_dist（哈希复验 OK）。
- 实例：cvd-39（ADB 0.0.0.0:6558），三次独立 guest 启动。

## 主要文件
| 文件 | 内容 |
|---|---|
| FINAL_REPORT.md | 结论、实际分母、逐 boot 结果、十项问答、偏离与缺口 |
| PROTOCOL.md / 04_protocol/ | 冻结协议与执行顺序勘误 |
| SCHEDULE.csv | 冻结排程（种子 2026102939，1,080 行） |
| BUILD_PROVENANCE.md | 构建来源、运行时属性、与历史构建关系 |
| BOOT_LEDGER.csv | 每 boot 身份（boot_id/fingerprint/ino/UID/日志哈希） |
| REQUEST_LEDGER.csv | 全部实际调用（正式/预检/恢复，scientific 标记） |
| EVIDENCE_MAP.csv | request id → 原始证据路径/行号与完整性 |
| EXCLUSIONS.csv / FAILURES.md / MISSING_ITEMS.md | 排除/失败/缺失（无事件时为零项） |
| summary/table7_*.csv, table8_*.csv | 逐 boot 与 pooled 汇总（计数，不用百分比） |
| tables_replacement.tex | 两张候选替换表（沿用原 label）+ 中英文结果段 |
| raw/（07_results/boot<N>/raw/） | 逐请求 app/framework/kernel/am/规则/对象/计数原始证据 |
| recompute/ | 排程生成、逐请求复算、ledger 汇总、run_all.sh |

## 离线复算
解压后执行：
```bash
bash recompute/run_all.sh
```
- 从原始请求记录与实际证据重新判定每条请求（不从预期矩阵反推）；
- 校验排程可复现、重复 reqid、逐 boot 与 pooled 加总、runner 与复算一致性。

## 哈希与打包
- FREEZE_MANIFEST.txt：采样前冻结输入的 SHA-256。
- SHA256SUMS.txt：完整归档哈希清单（自外排除）。
