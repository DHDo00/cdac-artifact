# CDAC 三版本 R1：3 boot／90 请求、范围对齐与材料归档

目录：three_version_r1_3boot_scope_alignment_20261102_100240/
运行盘：three_version_r1_3boot_scope_alignment_20261102_100240/
轮次时间：2026-11-02T10:02 起（Asia/Shanghai）。本轮不修改论文、不编译 TeX、不生成 PDF；
只交付数据反馈、表格数据、证据索引与归档。

## 结果一览（最终以 THREE_VERSION_SUMMARY.csv / TABLE_XV_DATA.md 为准）
- 目标：每版 3 个独立 boot、每 boot 30 个正式请求、每版 90 个正式请求。
- 复用 4 个历史合格 boot：A15 修正版 1、A16 R35 1、A17 2。
- 新增 5 个正式 boot：A15×2、A16×2、A17×1，共 150 个正式请求。
- 每个新增 boot 实测 30/30 = 6 真实拒止 + 24 允许/恢复（见 runs/<boot>/matrix）。

## 文件索引
- 计划与协议：ALIGNMENT_PLAN.md、ALIGNMENT_PLAN_AMENDMENT_1.md、PROTOCOL_FROZEN.md、
  EXISTING_BATCH_ELIGIBILITY.csv
- 输入与来源：INPUT_AND_PROVENANCE.md、INPUT_HASHES.csv、PRE_LAUNCH_STATE.txt
- 身份与账本：ARTIFACT_AND_RUNTIME_IDENTITY.csv、PER_BOOT_SUMMARY.csv、
  THREE_VERSION_SUMMARY.csv；新增逐请求账本 runs/<boot>/matrix/PER_REQUEST_LEDGER.csv；
  历史账本副本 history_ledgers/
- 范围对齐：SCOPE_ALIGNMENT.csv/.md、GRAPHICSSTATS_SCOPE_RECONCILIATION.md/.csv、
  diagnostics/（4/301 三账本与 E6/E7/E8 证据副本）
- 表格与反馈：TABLE_XV_DATA.md、DATA_FEEDBACK.md
- 声明/失败/缺证：CLAIM_EVIDENCE_MAP.csv、FAILURES_AND_EXCLUSIONS.md、
  MISSING_AND_LIMITATIONS.md
- 收尾：FINAL_STATUS.txt、SHA256SUMS.txt、audit_package/、audit_package.tar.gz

## 新增运行目录（/data2 运行盘，短目录防 AF_UNIX 108 字节限制）
- b2=A15B2(cvd-2/6521)、b3=A15B3(cvd-3/6522)、b97=A16B2(cvd-97/6616)、
  b98=A16B3(cvd-98/6617)、b99=A17B3(cvd-99/6618)。
- 每 boot：images 副本（launch 前与源 hash 一致）、新 userdata、i/instances/cvd-N、
  日志与装配文件；结束仅 stop 本轮实例。

## 关键边界（执行中遵守）
- 不构建/不 repo sync/不下载；不改 Binder/SELinux/发布接口/选择器/端点/原生授权；
  不删除文件、不改冻结镜像、不写历史目录；不操作 Overleaf、不编译论文/PDF。
- 90 是计划正式尝试数，不是预填成功数；失败/重试/无效全部保留。
