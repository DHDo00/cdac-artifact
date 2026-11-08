# VERIFY_REPORT — 第 39 轮归档离线校验（2026-10-30，Asia/Shanghai）

归档：cdac_r39_mediaprovider_matrix_replication_20261029_230000.tar.zst
字节数：42796322（约 40.8 MiB）
SHA-256：45eb51fbab86fed2a283d0a5a1d85fb38a03bb74891eb56e96a93a090fe4b782

## 1. 解压与哈希校验
- 解压目录：/tmp/r39_verify2_20261030/39_mediaprovider_matrix_replication_20261029_230000（全新临时目录）。
- `sha256sum -c SHA256SUMS.txt`：**10919/10919 OK，0 FAILED，rc=0**。
- SHA256SUMS.txt 覆盖除自身外的全部归档文件（自外排除记录于 SHA256SUMS_EXCLUSIONS.txt）。

## 2. 离线复算（解压副本内执行 bash recompute/run_all.sh）
- 排程复现：gen_schedule.py 重生成 SCHEDULE.csv 与冻结 SCHEDULE.csv 哈希一致（rc 通过）。
- analyze.py（仅从 raw 逐请求证据重新判定）：
  duplicate_reqids=[]、boot_ledger_mismatches=[]、structure=[]、no_req_line=[] → **STRUCT_OK**。
  pooled M：600 计划/600 尝试/480 usable/120 CDAC-denied/0 other/0 unresolved。
  pooled L：480 计划/480 尝试/360 usable/120 CDAC-denied/0 other/0 unresolved。
- pool_ledger.py：REQUEST_LEDGER 1284 行（1080 正式 + 204 预检/恢复），duplicate_reqids=[]。

## 3. 重算汇总与冻结汇总逐字节比较（diff -r / cmp）
- summary/{table7,table8}_{per_boot,pooled}.csv：**IDENTICAL**。
- analysis/requests_verified.csv、analysis/checks.json：**IDENTICAL**。
- REQUEST_LEDGER.csv、EVIDENCE_MAP.csv、BOOT_LEDGER.csv、tables_replacement.tex：**IDENTICAL**。

## 结论：解压后哈希校验通过；离线复算通过；重算汇总与冻结汇总一致。
