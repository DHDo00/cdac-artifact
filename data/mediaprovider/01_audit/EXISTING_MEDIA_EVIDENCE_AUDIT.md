# EXISTING_MEDIA_EVIDENCE_AUDIT.md — 第 39 轮历史证据定位与核对（采样前，2026-10-29）

## 1. 适用范围与结论
本轮要补强的两张表：
- `tab:media-selectivity`（表 VII）：调用者—对象选择性矩阵。历史批次=1 boot、
  每条件 3 次、共 30 次。
- `tab:media-method-selectivity`（表 VIII）：已发布方法标签选择性。历史批次=
  2 boots、每 boot 每条件 3 次、共 48 次。

历史定位结论（按内容核对，不按编号/文件名猜测）：
- 表 VII 的 30 次 = **第 35 轮** `35_r1_reversal_and_data_provenance_20261028`
  （B0/B1/B2/B3 十条件 × 3 次；30/30 全通过；6 次拒止=3×A→X + 3×B→X）。
- 表 VIII 的 48 次 = **第 36 轮** `36_operation_selectivity_and_proxy_feasibility_20261029`
  （S0/SW/SR/S3 每 boot 24 次 × 2 boots；48/48 有效；12 次拒止）。
- 第 37 轮 `37_r36_evidence_closure_20261029` 是对第 36 轮的只读证据闭合核对。

## 2. tab:media-selectivity（调用者—对象）历史 30 次
- 协议：`35_…/03_protocol/PROTOCOL_FROZEN.md`（冻结矩阵 B0..B3，C2=txn14 openFile→6/501）。
- 结果：`35_…/07_results/PER_REQUEST_LEDGER.csv`（30 行）。
  - B0 无规则：A→X 3/3 usable(owner sha e22785..)、B→X 3/3 usable(redacted 96f60e..)。
  - B1 规则 caller=A：A→X 3/3 denied、B→X 3/3 usable、A→Y 3/3 usable。
  - B2 规则 caller=B：B→X 3/3 denied、A→X 3/3 usable、B→Y 3/3 usable(redacted 311606..)。
  - B3 撤规：A→X 3/3、B→X 3/3 usable。
- 规则形状（R35）：service_id=6 op_id=501 caller_uid=<A|B> operation=openFile
  ino=<INO_X> s_dev=45 i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny
  reason=cdac35_r14a/cdac35_rev。
- 调用者：A=com.demo.espafdtest（owner，无 READ_MEDIA_IMAGES）；
  B=com.demo.espafdtestb（READ_MEDIA_IMAGES，redacted 视图）。二者不同 UID
  （boot1 实测 10121/10122）。
- 对象：X=image1.jpg（AAAA 标记）、Y=image2.jpg（BBBB 标记），A 经 MediaStore 创建，
  原生授权成立；B 的 redacted 视图不要求读回原文件未脱敏哈希（协议明文记录）。

## 3. tab:media-method-selectivity（方法标签）历史 48 次
- 协议：`36_…/04_protocol/PROTOCOL_FROZEN.md` + `PROTOCOL_AMENDMENT_20261029T1627.md`
  （S0 6 + SW 6 + SR 6 + S3 6 = 24/boot × 2 boots）。
- 结果：`36_…/07_results/PER_REQUEST_LEDGER.csv`（48 行有效；另有 24 条 INVALID
  批次保留不混入分母）。
  - S0 无规则：读/写各 3×2 boots 可用；SW（operation=openAssetFile deny）：
    读 3 可用、写 3 拒止；SR（operation=openFile deny）：读 3 拒止、写 3 可用；
    S3 撤规：读/写各 3 可用。
- 规则形状（R36）：service_id=6 op_id=501 caller_uid=<A> operation=<openFile|openAssetFile>
  ino=<INO_X> s_dev=0 i_mode=00 f_flags_mask=0x0 f_flags_value=0x0 decision=deny
  reason=cdac36_op。两条规则唯一差异=operation 字段；f_flags_mask=0（关闭有效访问标志掩码）。
- 入口：read_cpc=ContentProviderClient.openFile(uri,"r")→txn14 openFile→6/501；
  write_mp=ContentResolver.openFileDescriptor(uri,"w")→txn15 openAssetFile→6/501。
  两个标签在 Provider 侧汇聚到 MediaProvider.openFileCommon，仅 mode 参数不同
  （第 37 轮核对）。
- 第 37 轮收紧结论：拒止行无 CDAC_BINDER_VFS_JOIN 行；对象/标签证据来自
  decision(obj_ino/obj_s_dev/obj_f_flags) + real-enforce(op)；48/48 RAW_VERIFIED。

## 4. 本轮与历史的差异（预声明，见 04_protocol/PROTOCOL_FROZEN.md）
1. 样本量：M 由 1 boot×10×3=30 提升为 3 boots×20 循环×10 条件=600；
   L 由 2 boots×24=48 提升为 3 boots×20 循环×8 条件=480；合计计划 1,080。
2. 每 boot 内 M 与 L 在同一启动中完成（同一冻结构建 C19_media + kernel_openkeychain_dist）。
3. 客户端仅为观测字段增加 `reqid`（唯一请求标识）日志；API/权限/mode/路径不变
   （05_fixtures/CLIENT_CHANGE_RECORD.md + diff）。
4. 规则 reason 改为 cdac39_ma/mb/lw/lr（诊断标签）；其余规则语义与历史一致。
5. 每循环内同一规则状态请求顺序按冻结种子随机化；两目标规则顺序每 boot 各 10 次。
6. 历史 30/48 与第 27/25/16 等轮次的数字不并入本轮分母；本轮准备/恢复/健康检查
   单列（scientific=0）。

## 5. 可复现命令（历史）
- R35：`bash 35_…/06_runtime/run_r35.sh <out>`（cvd-35/0.0.0.0:6554，C19 制品）。
- R36：`bash 36_…/06_runtime/run_matrix.sh …`（cvd-36/0.0.0.0:6555，C19 制品）。
- 制品：`19_…/artifacts/{C19_media,kernel_openkeychain_dist}`；哈希
  `19_…/artifacts/ARTIFACT_HASHES.txt`（本轮 sha256sum -c 全部 OK，见 00_inputs）。
