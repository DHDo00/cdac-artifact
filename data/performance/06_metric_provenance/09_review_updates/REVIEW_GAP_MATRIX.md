# REVIEW_GAP_MATRIX.md — 审稿实验缺口核销矩阵（第 28 轮统一版，2026-10-27）
> 第 35 轮副本更新（2026-10-29）：R1 主体反转补齐；R21 对应缺项收紧。

状态：CLOSED_SCOPED=限定范围内已有证据；PARTIAL=部分回应；BLOCKED_RUNTIME_
PRECONDITION=运行前提阻断且根因已定位；UNVERIFIED=未验证；SOURCE_MISSING=
原文/证据缺失。评审原文 #735A/#735B 仍 SOURCE_MISSING，不编造引文/编号，
不重复全盘搜索。第 24–27 轮证据按各自有限样本推进到限定状态。

| # | 意见来源 | 问题 | 现有证据 | 状态 | 已入稿 | 尚缺 |
|---|---|---|---|---|---|---|
| R1 | 审稿主题（原文待核对） | 系统 Provider 入口扩展 | ESP 5/401、MediaProvider 6/501 真实 origin-scope 拒止（各自小样本）；**35 轮补证：txn14/openFile 主体反转 B→X 3/3 真实拒止 + A→X 恢复（RUN/ENF）** | CLOSED_SCOPED（这两条存储 Provider 写入口 + txn14 读入口主体反转，各为小样本） | 是 | 无（R1 主体反转由 35 轮补齐） |
| R2 | 审稿主题（原文待核对） | 第三方 Provider 接入（平台外项目） | 19 轮 OpenKeychain：源码资格+原生授权链成立；端点/调用者解析正确；发布被 SELinux 拒写设备阻断（write_failed、无帧）；下游匹配/执法未验证。32 轮静态审计：同一 write 承载 PUSH/POP+POLICY_ADD/CLEAR、无消息/凭据核验、主体自报，publish-only 边界无法由现有接口表达 | BLOCKED_RUNTIME_PRECONDITION + DESIGN_BLOCKED_PUBLISH_INTERFACE（两状态分列；0 构建/0 部署/0 运行，无注入/清除/伪造攻击执行） | 是（两者均入稿，区分运行事实与设计提案） | publish-only 接口切分（更深系统设计变更，未立项）；下游选择性执法 UNVERIFIED |
| R3 | 审稿主题（原文待核对） | 服务覆盖 | 均属存储 Provider 一类 | PARTIAL（单一服务类别） | 是（明确限定） | 不同系统服务类别（UNVERIFIED） |
| R4 | 审稿主题（原文待核对） | OEM/旧 API 兼容 | 历史 CTS/canary；近期未复验 | PARTIAL（历史证据） | 引用历史 | 原文+制品复核 |
| R5 | 审稿主题（原文待核对） | wrapper/proxy、能力变化、abstain | 13 轮转发读 origin 丢失；16 轮正向对应；19/20 轮修正为“该 hop 不支持 origin-scoped 执法”；22 轮 pending 观察=端点级执法≠分支级资格；**25 轮 redacted：构造链+cookie/身份+字节真值建立合法非恒等变换对应，upper open 交付前拒止 3/3；daemon no_context 与判定点分列；关系决策未触发、走普通 file-open 规则** | CLOSED_SCOPED（redacted 一条所测路线）；转发 hop 与通用失配检测=UNVERIFIED | 是（§4.6 新段 + §Supplementary redacted 段） | 通用失配检测（UNVERIFIED）；其它复杂返回分支未测 |
| R6 | 师兄建议 | 与合理局部检查比较 | 12/13/16 轮两条入口 L/C 功能平局、成本分列 | CLOSED_SCOPED | 是 | 无 |
| R7 | 审稿主题（原文待核对） | 真正无 CDAC 性能 | 11/12 轮 matched stripped、4 对 boot（+2.72/+2.26ms 校正口径） | CLOSED_SCOPED（ESP 负载与当时制品） | 是 | MediaProvider 性能（低优先） |
| R8 | 审稿主题（原文待核对） | 策略编写/适配/规则规模 | 16 轮账本（单入口边际改动）；**21 轮规则规模：N=0/1/8/32/128，正确性 61/61，延迟增量未分辨**；**27 轮跨入口：单入口精确规则只覆盖相应 operation，两条精确规则实现两入口一致限制；逻辑目标需展开为路线集合+精确规则集并检查入口覆盖** | CLOSED_SCOPED（≤128 条、单路线、两公开读入口）；真人资格审核与策略编写成本不足=保留 | 是（Implementation Scope 策略准备段 + §Supplementary 跨入口段） | 其他路线/真实业务规则分布/真人编写成本（UNVERIFIED） |
| R9 | 审稿主题（原文待核对） | 异常输入/绕过/兼容 | 历史 02_bypass_surface；**24 轮：E1 非法模式、E2 已删除对象均发布后/pre-join，24 触发+60 恢复全 PASS、清理平衡、同线程复用归属正确；取消/超时/inode 复用/路径键未覆盖** | PARTIAL→CLOSED_SCOPED（两类已测异常）；其余异常类 UNVERIFIED | 是（§4.7 清理段 + §Supplementary 异常段） | 原文 SOURCE_MISSING；取消/超时等（UNVERIFIED） |
| R10 | 历史人类审稿（phase1r1） | Section 3 形式边界 | 已修订 | CLOSED_SCOPED（历史） | 是 | 无 |
| R11 | 师兄建议 | 副作用顺序 | 09/12/16：ESP 截断后拒止；MediaProvider 拒止后不变——仅所测路径/模式；22 轮 pending "rw" 文件不变（不外推） | CLOSED_SCOPED（所测路径/模式） | 是 | 无 |
| R12 | 师兄建议 | 非属主写正规用户授权 | 15/16 轮 createWriteRequest 系统确认 | CLOSED_SCOPED | 是 | 无 |
| R13 | 审稿主题（原文待核对） | B3 通用失配检测 | 未实现；运行时不复验能力指纹；直接路线由构造不变量承担；**25 轮 redacted 由构造链+cookie+字节真值建立正向对应（构造层面），仍无运行时 κ 复验；文件身份不独自证明内容视图；规则无脱敏状态字段** | UNVERIFIED（非“已排除”）——论文未承诺该检测器，故列未实现能力而非必须补齐项 | 是（§4.6 明示 + 限制） | 最小诊断设计（20 轮 REMAINING_WORK；不重复启动） |
| R14 | 审稿主题（原文待核对） | 跨进程转发后身份 / 并发归属 | 转发读 origin 丢失；无受审传播机制；**26 轮：40/40 重叠波（2 boot×20 波×4 请求），160/160 请求唯一归属，40 拒止+120 允许零串扰；仅 4 请求并发规模** | 转发身份 UNVERIFIED；并发归属 CLOSED_SCOPED（4 请求规模） | 是（RQ3 保留 + §Supplementary 并发段） | 任意并发度/受审传播机制（UNVERIFIED，不重复） |
| R15 | 22/25 轮发现（非审稿原文） | 资格范围 vs 执法范围 | pending 与 redacted 分支均经 6/501 端点 join/评估/拒止；端点级执法≠分支级资格；新增路线证据不自动证明 Provider 全分支资格；形式前提/离线审查/运行时检查/已测范围四者区分 | CLOSED_SCOPED（两条分支观察）；对所有未审查分支的自动隔离=UNVERIFIED | 是（§4.5 分层表述 + §Supplementary） | 全分支运行时门控（机制扩展，未立项） |

| R16 | 24 轮新证据 | 异常后上下文清理与同线程复用 | 24 触发 + 60 恢复；EXIT/POP depth=0、0 mismatch、计数平衡；复用后归属正确 | CLOSED_SCOPED（两类异常、两条观测面） | 是（§4.7 + §Supplementary） | 取消/超时、E3 原生拒绝、任意异常类 |
| R17 | 24 轮新证据 | 对象删除重建后的规则绑定 | 两 boot：X0.ino≠X1.ino（无复用）；旧 X0 规则不命中 X1，更新 X1 规则拒止恢复，撤规恢复 | CLOSED_SCOPED（特定对象绑定语义） | 是（§Supplementary） | inode 复用歧义、路径键生命周期 |
| R18 | 25 轮新证据 | 复杂返回路线（proxy/变换视图）能力对应 | redacted：辅助 lower open + FUSE upper 能力 + 读时 GPS 清零；三件套对应；S1 3/3 交付前拒止；daemon no_context 与判定点分列；关系决策未触发 | CLOSED_SCOPED（一条 redacted 读路线） | 是（§4.6 + §Supplementary） | 通用视图识别、运行时 κ、关系规则覆盖非 passthrough 视图 |
| R19 | 27 轮新证据 | 不同公开入口覆盖与兼容 | C1/C2 两条链；单规则单入口；双规则两入口 3/3 一致限制；原生 18/18 | CLOSED_SCOPED（当前 Android 制品、两公开读入口） | 是（Implementation Scope + §Supplementary） | 旧 Android/OEM/其它 Provider/其它 API 族 |

| R20 | 30 轮新证据 | 改名/名称复用/硬链接下的对象绑定 | R_obj 改名后 3/3 拒止、名称复用新对象不命中、硬链接 A 拒 B 放、撤规恢复（两 boot）；名称联合规则改名后实测拒止与 H2 放行的语义差异按观测报告 | CLOSED_SCOPED（对象绑定正项）+ 名称联合语义差异按 A/B/C 分状态（B 成立；C 主链闭合+UNRESOLVED_DETAIL）；不计入正式分母，置于 Supplementary | 是（§4.6 Identity-versus-access-names + §5.4 alias 段 + Table 5） | inode 复用、旧 FD 撤销、rename/open 竞态、TOCTOU、其它 Provider（UNVERIFIED） |
| R21 | 29b 续任务状态 | 真人策略编写成本 / 跨版本 / R1 主体反转 | 真人=MATERIALS_READY_ONLY（0 参与者，成本与正确性未测量，不得写零成本）；跨版本=ARTIFACT_INSUFFICIENT_OLD_VERSION（不判兼容）；**R1 主体反转=RUN/ENF（35 轮补齐，30/30 请求、B→X 3/3 真实拒止+A→X 恢复）** | MATERIALS_READY_ONLY / ARTIFACT_INSUFFICIENT / RUN_ENF_35（三者分列，不合并） | 是（OPEN_ISSUES 同步） | ≥2 真人执行；旧版本制品；R1 跨启动重复（按原协议为 1 boot，保留） |
| R22 | 32 轮新证据（design-only） | 发布接口边界与 TCB 粒度 | 控制设备 write 单一承载上下文发布与全局规则管理；无消息/凭据级核验；主体字段自报；专用域 patch 未编译/未部署/未运行；未实施注入/清除/伪造 | DESIGN_BLOCKED_PUBLISH_INTERFACE（静态设计阻塞；不写成已执行危害） | 是（Threat model/§4 capture/Implementation Scope/§5.4+Table） | 发布面与规则管理面的强制切分（未立项） |
| R23 | 33 轮审计新证据（本目录） | 实际写入者与 TCB 域集合 | 编译策略直授 write 的 6 域（mediaprovider、mediaprovider_app、platform_app、priv_app、radio、system_server）+ permissive su 调试主体；观察写入=发布（19 轮 push/pop 计数与 framework 日志）+ 规则管理（rule_add.txt/policy-clear）；radio/system_server 有 allow 无写入证据；论文原“platform provider domains only”过度声明已改为精确域集合 | CLOSED_SCOPED（编译策略层）；运行态写入者 scontext 未逐条记录=UNVERIFIED_DETAIL | 是（Threat model/§4.3/Implementation Scope 三处修订，33_main.diff） | 逐写路径 scontext 日志；radio/system_server 用途确认（未立项） |

“已限定范围回答”“仅部分回应”“运行前提阻塞”“未验证”四类在状态列明确区分；
不把论文修订当作完成实验。
