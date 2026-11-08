# R1_RESULT_AND_LIMITATIONS.md — R1 补证结论与限制（第 35 轮，2026-10-29）

路线：R1=MediaProvider 读入口 **txn14 openFile**（ContentProviderClient.openFile("r")
→ MediaProvider.openFile → openFileCommon → 6/501，能力=全文件 O_RDONLY PFD，
判定点=upper 0:45 open）。
制品：C19_media + kernel_openkeychain_dist（第 19 轮冻结，与 25/27 轮同哈希）。
实例：cvd-35，1 boot，SELinux Enforcing。协议冻结于采样前
（03_protocol/PROTOCOL_FROZEN.md）。**30/30 请求按冻结矩阵执行，6 次真实拒止
全部判据满足（详见 07_results/RESULTS_SUMMARY.md 与 PER_REQUEST_LEDGER.csv）。**

## 1. R1 的原始缺项究竟是什么？
- 审稿原文 #735A/#735B 文本仍 SOURCE_MISSING；R1 主题从任务书与 29b 勘误继承。
- 经 29b 勘误（ERRATA_AND_PROVENANCE.md 更正 4）确认的**唯一缺项**：
  在 C2(txn14/openFile) 路线上把拒止主体从 A 改为 B —— 规则
  `caller_uid=B, operation=openFile, ino=X, s_dev=0:45, f_flags 0x3/0x0, deny`：
  B→X 真实拒止 + A→X 恢复可用 + B→Y 保持可用 + 撤规后 A→X/B→X 均恢复。
- 第 27 轮已完成的 C2 原生前提(18/18)、R14 A→X 拒止(1/1+3/3)、S2/S3/S4(各 3/3)
  均属 R1 已通过项；25 轮 txn23 redacted、16 轮 txn15 写入口的主体反转是
  其它路线的证据，均**不能**替代 R1。

## 2. 本轮是否在同一路线、等价对象和操作下补齐？
**是（补齐）。**
- 同一路线：txn14 openFile → 6/501（运行 ENDPOINT_RESOLVE transaction_code=14、
  transaction_name=openFile、service_id=6、op_id=501）。
- 等价对象/操作：X=image1.jpg（backing dev 65120/ino 2931，规则对象=0:45/ino 2931，
  O_RDONLY f_flags=0x28000），与第 27 轮 R14 完全同形状；Y=image2.jpg 为对象控制。
- 授权前提与 27 轮一致：A=属主直读（原字节 e22785…/f3d29c…）、B=READ_MEDIA_IMAGES
  非属主（redacted 96f60e…/3116065d…），A/B 为非 root 普通应用（untrusted_app）。
- 未换路线、未改核心机制、未换对象、未用 root 代替受测 App、未 report-only 计拒止。

## 3. 固定规则的调用者选择性与规则主体反转是否分别成立？
**分别成立（本轮同 boot 内直接对照）：**
- 固定规则（R14A, caller=A）：A→X 3/3 DENY_PASS；同一规则 B→X 3/3 放行
  （matched=0，caller=10122）、A→Y 3/3 放行（matched=0，obj=2951）→ 规则按
  caller/对象选择性，非 provider 全灭。
- 主体反转（R_rev, caller=B，同一 service/op/object/operation）：B→X 3/3
  DENY_PASS（matched=1 reason=cdac35_rev、real-enforce errno=-13 deny-now）；
  同一反转规则 A→X 3/3 恢复放行（matched=0，caller=10121）、B→Y 3/3 放行
  （matched=0，obj=2951）。
- 撤规后 A→X/B→X 各 3/3 恢复；runtime_policy_count 终态=0。
- 两类的证据粒度均到逐请求 seq/context_id/server_tid，6 次拒止均满足冻结六判据
  （规则读回、ENTER/PUBLISH、0:45/ino 匹配、real-enforce、无 PFD、backing 不变、
  file_open_deny 0→3→6 精确对应）。

## 4. 哪些条件通过、失败、未触发或缺证？
- **通过**：全部冻结矩阵 10 组 × 3 = 30/30；6 次真实拒止 + 24 次允许/恢复；
  policy 读回（count=1 字段核对、count=0）；对象前后状态不变；计数器与平衡计数
  （push=pop=35，0 嵌套失配）；进程域采样（A/B=untrusted_app、
  MediaProvider=mediaprovider_app）。
- **失败**：0。
- **未触发/不适用**：B 的能力视图为 redacted（合法非恒等视图），B→X 的“可用/恢复”
  语义=redacted 视图能力；无逐条 write 的 scontext 日志（仅有采样时刻域证据，
  与 32/33 轮观测能力一致）。
- **缺证（保留）**：跨启动重复未做（原 27 轮协议即 1 boot，本轮按原协议执行）；
  不覆盖其它 Provider/入口/并发度/旧版本。

## 5. 本轮结果能支持哪一句论文表述，不能扩大到什么范围？
**可支持（建议表述，PAPER_INSERTION_DRAFT.md 给出原文与插入位置）：**
- 在 C2(txn14 openFile) 读入口上，目标规则的主体反转成立：把同 service/op/object
  的拒止目标 caller 从 A 改为 B 后，B→X 3/3 在能力交付前被真实拒止、A→X 3/3
  恢复可用、B→Y 3/3 保持可用、撤规后 A→X/B→X 3/3 恢复。固定规则下的调用者选择性
  与规则主体反转在本轮同 boot 内分别成立。

**不能扩大：**
- 主体反转通过**只支持 C2 该路线的调用者选择性**；
- 不证明设备边界**独立认证**自报主体字段（32/33 轮：write 单面承载
  PUSH/POP+POLICY_ADD/CLEAR、无消息/凭据级核验、内核不独立认证）；
- 不解决 **publish-only 权限耦合**（DESIGN_BLOCKED_PUBLISH_INTERFACE 不变）；
- 不覆盖 txn23/txn15/其它 Provider 的主体反转（分别由 25/16 轮证据）；
- 不是第三方下游执法验证；不是并发/跨版本/跨启动可靠性证据。

## 保留的限制清单（来自 19/29b/32/33 轮，本轮不变）
1. 第 19 轮运行前提阻塞（第三方发布被 SELinux 拒写，无帧无裁决）。
2. 第 32 轮设计阻塞（publish-only 接口未切分，专用域 patch 仅 design-only）。
3. 第 33 轮六个直授写域（mediaprovider/mediaprovider_app/platform_app/priv_app/
   radio/system_server）与 su（typepermissive）的分层披露。
4. 第三方下游执法未验证。
5. path_tail 来源链已确认（查找期缓存 backing_path dentry 复用），旧名底层具体
   原因（dentry d_name 原地更新细节）仍 UNRESOLVED_DETAIL。
6. 真人成本=MATERIALS_READY_ONLY（0 参与者）；跨版本=ARTIFACT_INSUFFICIENT_OLD_VERSION。
7. B1–B4 定义与证明结构不变（本轮补充的是 R1 该路线的运行选择性与反转，
   不是新的 B1–B4 形式结果）。
8. 既有 L/C 功能平局及其比较范围不变（本轮无新 L 对照）。
9. 审稿原文 735A/735B 仍 SOURCE_MISSING。

## 成功数/尝试数（最终回答用）
- 冻结矩阵 30 请求：**30/30 一次通过**；其中**真实拒止 6/6**（B1 A→X ×3、
  B2 B→X ×3），允许/恢复 24/24；无失败、无重试、无无效样本。
- 本轮新增运行证据：R1 主体反转块（B2）+ 同 boot 内对照（B0/B1/B3）。
- 数据核验（40/40、120/120、3/3、10/10、61/61、160/160、24+60、128、0.252、
  +2.72/+2.26）：**全部为旧数据口径核验**，非新增实验；重算与汇报一致，未见
  数值反例；唯一历史口径差异（10/10 转发 vs DP 撤规健康、160/160 并发 vs MP
  重建、24 单/双 boot）已分列，未静默修改。
