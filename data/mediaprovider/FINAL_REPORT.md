# FINAL_REPORT — 第 39 轮 MediaProvider 两项功能复现
目录：39_mediaprovider_matrix_replication_20261029_230000
日期：2026-10-29/30（Asia/Shanghai）。状态：COMPLETE。

## 结论
- 实验 M（tab:media-selectivity，调用者—对象矩阵）：**3 个真实 guest 启动 × 20 循环 × 10 条件 = 600/600 计划并实际执行**。120 次目标拒绝全部逐请求对应 CDAC 匹配与执法；480 次允许/恢复全部实际使用返回的描述符。0 异常、0 unresolved、0 排除。
- 实验 L（tab:media-method-selectivity，方法标签矩阵）：**3 个真实 guest 启动 × 20 循环 × 8 条件 = 480/480 计划并实际执行**。120 次目标拒绝全部逐请求对应 CDAC 匹配与执法；360 次允许/恢复全部实际使用描述符。0 异常、0 unresolved、0 排除。
- 合计 1,080 次正式请求：240 次 CDAC 拒止 + 840 次允许/恢复。每 boot 内核计数 file_open_deny=80（三 boot 合计 240），与逐请求拒止数一致。
- 离线复算：从 raw 逐请求证据重新判定 1,080 条，与 runner 记账 0 不一致；无重复 reqid；每条件恰 60 条；排程可按冻结种子逐字节复现。

## 实际分母（正式，scientific=1）
| 实验 | 计划 | 实际尝试 | 可用 | CDAC 拒止 | 其他失败 | unresolved |
|---|---|---|---|---|---|---|
| M（表 VII） | 600 | 600 | 480 | 120 | 0 | 0 |
| L（表 VIII） | 480 | 480 | 360 | 120 | 0 | 0 |
| 合计 | 1080 | 1080 | 840 | 240 | 0 | 0 |
非正式调用：每 boot 预检 8 条（4 读 + 1 写 + 1 恢复 + 2 建对象）×3 boots + 60 次允许写后恢复×3 boots = 204 条，全部 scientific=0、单列，不进入正式分母。

## 逐 boot 结果
| boot | boot_id | inoX | inoY | M 计划/执行 | M 拒止/允许 | L 计划/执行 | L 拒止/允许 | file_open_deny | 残留规则 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | b33ca4b8-5a9b-47f7-9c9f-7b32d7b4168e | 2991 | 3024 | 200/200 | 40/160 | 160/160 | 40/120 | 80 | 0 |
| 2 | 1e5d3389-73c1-45a2-a212-19bf689a26a7 | 2979 | 3008 | 200/200 | 40/160 | 160/160 | 40/120 | 80 | 0 |
| 3 | 4f3ee9db-418d-4e3a-94c4-336b14bd54ec | 3012 | 3042 | 200/200 | 40/160 | 160/160 | 40/120 | 80 | 0 |
UID：每 boot A=10121、B=10122（不同 UID）。三次 boot_id 互不相同、ino 逐 boot 重新解析（不机械沿用旧 inode）。每 boot 60 次允许写后恢复全部 RESTORE_PASS（backing 回到 e22785cd…）。

## 表 VII（tab:media-selectivity）十行真实计数（每条件 pooled，60 计划/60 执行）
| 条件 | usable | denied | 异常 | unresolved |
|---|---|---|---|---|
| 无规则 A→X | 60 | 0 | 0 | 0 |
| 无规则 B→X | 60 | 0 | 0 | 0 |
| 规则 caller=A，A→X | 0 | 60 | 0 | 0 |
| 规则 caller=A，B→X | 60 | 0 | 0 | 0 |
| 规则 caller=A，A→Y | 60 | 0 | 0 | 0 |
| 规则 caller=B，B→X | 0 | 60 | 0 | 0 |
| 规则 caller=B，A→X | 60 | 0 | 0 | 0 |
| 规则 caller=B，B→Y | 60 | 0 | 0 | 0 |
| 撤规 A→X | 60 | 0 | 0 | 0 |
| 撤规 B→X | 60 | 0 | 0 | 0 |

## 表 VIII（tab:media-method-selectivity）八单元真实计数（每单元 pooled，60 计划/60 执行）
| 单元 | usable | denied | 异常 | unresolved |
|---|---|---|---|---|
| 无规则 openFile/r | 60 | 0 | 0 | 0 |
| 无规则 openAssetFile/w | 60 | 0 | 0 | 0 |
| 选择 openAssetFile，openFile/r | 60 | 0 | 0 | 0 |
| 选择 openAssetFile，openAssetFile/w | 0 | 60 | 0 | 0 |
| 选择 openFile，openFile/r | 0 | 60 | 0 | 0 |
| 选择 openFile，openAssetFile/w | 60 | 0 | 0 | 0 |
| 撤规 openFile/r | 60 | 0 | 0 | 0 |
| 撤规 openAssetFile/w | 60 | 0 | 0 | 0 |

## 偏离与缺口
1. 执行顺序：冻结协议写“先 M 后 L”，冻结 runner 的字典序使每 boot 实际“先 L 后 M”
   （三个 boot 一致）。已记录于 04_protocol/PROTOCOL_AMENDMENT_20261029T2310.md；
   每循环仍以无规则开始、以撤规+恢复结束，所有状态切换 add/dump/clear/dump 读回；
   不影响任何判定。无重跑、无换 boot。
2. 客户端观测字段：为逐请求唯一标识增加 `reqid` 日志（保留 diff），API/权限/mode/路径
   不变，见 05_fixtures/CLIENT_CHANGE_RECORD.md；APK 在采样前冻结。
3. 打包后分析脚本 pool_ledger.py 增加“建对象 prep 行”汇总（仅记账层，不影响 raw/判定/
   分母）；分析脚本 gen_tables_tex.py 为打包阶段新增；机制/APK/runner/规则模板/排程/
   oracle 冻结后零改动。
4. 缺失登记（MISSING_ITEMS.md）：MediaProvider APEX 精确构建来源
   哈希未重建（版本字符串如实记录）；内核→vmlinux 源码编译哈希沿用 R37 已登记缺口；
   无逐请求 scontext（采样时刻域证据）。
5. 大镜像不打包：06_runtime/boot*/{images,instance,assembly,early_tmp} 留在服务器，
   路径与源制品哈希见 BUILD_PROVENANCE.md 与 00_inputs。

## 十项问答
1. 两项实验都完成。各执行 3 个真实新 boot（boot1/2/3，boot_id 见上表），全部使用同一
   冻结构建 C19_media + kernel_openkeychain_dist（与历史 R35/R36 同批，哈希复验 OK）。
2. 每 boot：M 计划 200/实际 200；L 计划 160/实际 160。合计 M 600、L 480。
3. 表 VII 十行真实计数：见上文“表 VII”表。
4. 表 VIII 八单元真实计数：见上文“表 VIII”表。
5. 240 次目标拒绝 100% 逐请求对应 CDAC 执法（policy_dump 目标规则 + ENTER caller 正确 +
   PUBLISH msg5 ok + decision matched=1 reason 对应 + real-enforce errno=-13 deny-now +
   App FileNotFoundException:EACCES + 无 PFD）；840 次允许/恢复 100% 实际使用描述符
   （读=911B+sha+marker；写=写入 911B+backing sha 等于该请求 token 冻结期望，随后恢复）。
   缺失 0。
6. 保持原语义：A owner 视图（无 READ_MEDIA_IMAGES）、B redacted 视图（READ_MEDIA_IMAGES）；
   M 读=ContentProviderClient.openFile(uri,"r")→txn14 openFile→6/501；L 读同上、L 写=
   ContentResolver.openFileDescriptor(uri,"w")→txn15 openAssetFile→6/501；两条 L 规则仅
   operation 标签不同且 f_flags_mask=0，两条 M 规则仅 caller 不同且对象限制同为 X。
   与旧批次差异：样本量（30→600、48→480）、reason 标签 cdac39_*、reqid 观测字段、
   每状态内随机顺序、执行顺序 L 先于 M（见偏离 1）。
7. 失败/超时/排除/重试/额外 boot：全部为 0。3 次启动尝试全部一次成功（ADB_OK，
   46–48 次轮询内完成）。协议偏离 1 项（执行顺序，见偏离 1），另有客户端 reqid
   观测字段改动（采样前冻结）。
8. 冻结后未修改系统机制、APK、runner、规则模板、排程、oracle。仅：打包阶段新增
   gen_tables_tex.py、pool_ledger.py 增加 prep_make 记账行（纯记账），以及文档
   （AMENDMENT/README/FAILURES/MISSING_ITEMS/FINAL_REPORT）。无 campaign 分离。
9. 解压后哈希校验与离线复算：见 07_results/offline_verify/（校验 100% OK；run_all.sh
   复算 STRUCT_OK；复算汇总与冻结汇总一致，0 差异）。
10. 压缩包路径/字节数/SHA-256：见同目录外 sidecar 文件
    `39_mediaprovider_matrix_replication_20261029_230000.ARCHIVE_INFO.txt`（包内文件不
    自引用包含自身的归档哈希，避免循环），并在最终回复中给出。
