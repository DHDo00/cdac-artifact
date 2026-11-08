# REVIEW_RESPONSE_DRAFT.md — 逐条回复草稿（第 28 轮统一版，2026-10-27）

未定位 Review #735A/#735B 原文：对应关系不编造，编号留空；原文到位后按
REVIEW_GAP_MATRIX 逐行对齐。以下按任务书列出的已知审稿主题组织，每行标注
“已限定范围回答 / 仅部分回应 / 运行前提阻塞 / 未验证 / 来源缺失”。

| 审稿关注点 | 已采取措施 | 新证据/修订位置 | 状态与剩余 |
|---|---|---|---|
| 服务与能力覆盖不足 | 新增 ESP 5/401、MediaProvider 6/501 直接写专用端点执法；DP/Settings 40/40 保留 | unified table + §Supplementary | 已限定范围回答（两条存储 Provider 写入口）；其他服务类别未验证 |
| 第三方 Provider 能否接入 | OpenKeychain 源码资格+原生授权链成立、端点/调用者解析正确；发布被 SEAndroid 拒写设备阻断；下游未验证 | Implementation Scope + §Supplementary 六步证据段（20 轮）；计数器口径修正（23 轮） | 运行前提阻塞（BLOCKED_RUNTIME_PRECONDITION）；需要受审发布通道或第三方域（机制扩展，未做） |
| wrapper/proxy/能力变化/abstain | 转发读 origin 丢失如实写；19/20 轮把“must abstain”改为“该 hop 不支持 origin-scoped 执法”；22 轮证明端点级执法≠分支级资格；**25 轮 redacted：辅助 lower open、FUSE upper 能力与读时 GPS 清零；构造链+cookie/身份+字节真值共同建立合法非恒等变换对应；upper open 交付前拒止 3/3；daemon no_context 与判定点分列；关系决策未触发、走普通 file-open 规则** | RQ3 + §4.5 + §4.6 + §Supplementary redacted 段 | 已限定范围回答（一条 redacted 读路线）；通用 B3 失配检测/运行时 κ 复验未实现；其它复杂返回分支未测 |
| OEM/旧 API 兼容 | 引用 01_compatibility 历史 CTS/canary；**27 轮仅在当前 Android 制品验证两条公开读入口兼容**；未与旧系统/OEM 复验 | 历史引用 + §Supplementary 跨入口段 | 仅部分回应；原文与旧系统/OEM 制品复核待做 |
| 与合理局部检查比较 | L/C 功能平局、成本分列 | §Supplementary + ADAPTATION_COST_LEDGER | 已限定范围回答 |
| 真正无 CDAC 性能 | matched stripped 4 对 boot；+2.72/+2.26ms 校正口径 | RQ4 段落 | 已限定范围回答（ESP 制品/负载）；MediaProvider 性能未做 |
| 策略编写/规则规模 | **21 轮规则规模**：N=0/1/8/32/128、正确性 61/61、延迟增量未分辨；**27 轮跨入口：单入口精确规则只覆盖相应 operation；两条精确规则实现两入口一致限制；逻辑限制目标需展开为路线集合+精确规则集并检查入口覆盖** | §Supplementary 规则规模/跨入口段 + Implementation Scope 策略准备段 | 已限定范围回答（≤128 条、单路线、两公开读入口）；真人资格审核与策略编写成本不足保留；真实业务规则分布未验证；不推荐未验证 operation 通配 |
| 异常输入/绕过 | 历史 02_bypass_surface；**24 轮：E1 非法模式、E2 已删除对象均发布后/pre-join；24 触发+60 恢复全 PASS；EXIT/POP depth=0、0 mismatch；同线程复用归属正确；删除重建后旧规则不命中新对象、更新规则恢复拒止** | §4.7 清理段 + §Supplementary 异常/生命周期段 | 已限定范围回答（两类异常+特定对象绑定）；取消/超时/inode 复用/路径键未覆盖；原文 SOURCE_MISSING |
| B3 失配检测 | 未实现；直接路线=资格期构造不变量；**redacted 路线=构造链+cookie+字节真值（构造层面正向对应），仍无运行时 κ 复验；文件身份不独自证明内容视图；规则无脱敏状态字段** | §4.6 + 限制 | 未实现能力（论文未承诺，故列未实现而非必须补齐）；不写成已实现 |
| 跨进程身份传播 / 并发归属 | 转发读 origin 丢失如实写；**26 轮：40/40 重叠波、160/160 请求唯一归属、40 拒止+120 允许零串扰（服务端活动区间重叠，非同时执行）** | RQ3 + §Supplementary 并发段 | 转发身份未验证；并发归属已限定范围回答（4 请求规模）；不重复该分支 |
| 资格与执法粒度（22/25 轮观察） | pending 与 redacted 分支均经 6/501 join/评估/拒止；执法按端点键控；形式前提/离线审查/运行时检查/已测范围四者区分；措辞修订≠自动分支隔离实现 | §4.5 分层表述 + §Supplementary pending/redacted 段 | 已限定范围回答（两条分支观察）；所有未审查分支的自动隔离=未验证 |

| 异常后清理与同线程复用（24 轮） | 两类发布后/pre-join 异常的框架+kernel 双面清理与平衡计数、60/60 恢复、同线程复用归属正确 | §4.7 + §Supplementary 异常段 | 已限定范围回答；取消/超时等未覆盖；“无遗留”仅限观测对象与采样范围 |
| 对象删除重建绑定（24 轮） | 两 boot 无 inode 复用；旧对象规则不命中新对象；更新规则后拒止恢复 | §Supplementary 生命周期段 | 已限定范围回答（特定对象绑定语义）；inode 复用/路径键未覆盖 |
| 复杂返回路线能力对应（25 轮） | redacted 三件套对应 + 字节真值 + 交付前拒止 3/3 | §4.6 + §Supplementary redacted 段 | 已限定范围回答（一条 redacted 读路线）；通用视图识别/运行时 κ 未实现 |
| 跨公开入口覆盖与兼容（27 轮） | C1/C2 两条链；单规则单入口；双规则两入口一致限制 | Implementation Scope + §Supplementary 跨入口段 | 已限定范围回答（当前 Android 制品）；旧 Android/OEM/其它 Provider/API 未验证 |
| 与合理局部检查比较（延续） | 24–27 轮未新增 L 对照 → 不据此宣称对复杂路线防御更强或适配更省 | §Supplementary L/C 段保留 + 明示 | 已限定范围回答（既有 L/C 平局与成本结论不变） |

口径：每条回复区分“已限定范围回答 / 仅部分回应 / 运行前提阻塞 / 未验证 /
来源缺失”，不把论文修订当作完成实验；735A/735B 原文仍 SOURCE_MISSING。


| 对象别名/改名/名称字段（30 轮+31 轮审计） | R_obj（ino+s_dev）改名/名称复用/硬链接下选择性拒止保持；R_obj_name 改名后实测拒止=观测键（decision 打印 obj->path_tail）携带旧 basename，新别名 H2 放行证明按名区分；成因=查找期缓存 backing_path dentry 不随 rename 刷新（主链闭合，底层 dentry 细节 UNRESOLVED_DETAIL） | §4.6 Identity-versus-access-names + §5.4 alias 段 + Table 5 | 已限定范围回答（对象绑定正项）；名称联合谓词的“当前名”语义不在本部署成立，按对象+名称联合范围评价；不判绕过 |
| 真人策略编写成本（29b） | 试验包、M/A 两条件、参考答案/评分/分配/计时工具已冻结；0 真人执行 | 29b 目录（不并入论文正文） | MATERIALS_READY_ONLY：成本与正确性未测量，不写“成本为零”，不组间比较 |
| 旧版本兼容（29） | 无可核验旧版本制品 | 29b 更正已入稿 | ARTIFACT_INSUFFICIENT_OLD_VERSION：不作兼容/不兼容结论 |
| R1 主体反转（29b 更正） | **35 轮补齐（2026-10-29）**：txn14/openFile 规则 caller=B 下 B→X 3/3 真实拒止（real-enforce errno=-13）、A→X 3/3 恢复、B→Y 3/3 放行、撤规 3/3 恢复；同 boot 固定规则选择性与主体反转分别成立。25 轮 txn23 redacted 证据仍单列为相关机制证据 | 证据映射+RUN/ENF | CLOSED_SCOPED（该路线小样本）；见 35 轮 R1_RESULT_AND_LIMITATIONS.md |


| 发布接口边界 / TCB（32 轮+34 轮） | 19 轮=运行前提阻塞（发布被 SELinux 拒写）；32 轮=静态设计阻塞（write 单一承载发布+规则增清、主体字段自报无核验，专用域写权不可限定为 publish-only，patch 仅 design-only，0 构建/部署/运行，未执行注入/清除/伪造）；信任=整个被授写域而非单个入口函数 | Threat model + §4 capture Deployed channel boundary + Implementation Scope + §5.4 + Table 边界表 | 已如实区分“运行事实/设计提案/未验证”：第三方下游执法仍 UNVERIFIED；不把已明确扩展门槛写成已完成第三方兼容 |
| 实际写入者与 TCB 域集合（33 轮审计） | 编译策略穷举：直授 write 的 6 域+permissive su 调试主体；发布写入与规则管理写入均已观测；radio/system_server 有 allow 无写入证据；论文原“platform provider domains only”已改为精确域集合并披露 su | EFFECTIVE_WRITER_MATRIX.csv / MESSAGE_CAPABILITY_MATRIX / TCB_CLAIM_ALIGNMENT | 编译策略层已核销；运行态写入者 scontext 未逐条记录 → 域由进程/包映射推断，不写成逐帧证据 |
