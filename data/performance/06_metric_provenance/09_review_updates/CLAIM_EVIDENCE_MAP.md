# CLAIM_EVIDENCE_MAP.md — 论文核心声明与证据映射（第 28 轮统一版，2026-10-27）
> 第 35 轮副本更新（2026-10-29）：R1 状态由 MISSING 更新为 RUN/ENF（第 35 轮补证）；
> 其余历史结论/数字不变；原第 33 轮归档只读。

> 第 33 轮修订：按第 33 轮 EFFECTIVE_WRITER_MATRIX/SUBJECT_PROVENANCE_MAP 更新；
> 基线=第 34 轮归档 B；历史运行证据、分母、各轮结论不变。

状态标记：SRC=源码审查；RUN=运行证据；ENF=实际参与拒止；GAP=缺证；
SCOPE=已限定范围；BLOCKED=运行前提阻塞。基线=第 23 轮映射 + 24–27 轮补充；
历史原始数据未改写。

## B1（原始调用者到判定点）
- ESP 写（5/401）：统一钩子 ENTER caller=A + VFS_JOIN 同线程（RUN/ENF，06/12/16/21）。
- MediaProvider 写（6/501）：caller=A/B 到 proxy/backing 决策点（RUN/ENF，15/16）；
  pending 分支（22 轮，RUN/ENF）。
- **redacted 读分支**：CONTEXT_ENTER caller=B + PUBLISH + 能力 upper open 决策
  同 provider 线程；daemon lower open/read 无 caller 上下文（no_context），但
  不是交付前判定点（RUN/ENF，25 轮）。
- **公开入口 C1/C2**：txn23 openTypedAssetFile 与 txn14 openFile 均 ENTER
  caller 正确 + PUBLISH（RUN/ENF，27 轮）。
- **并发**：160/160 请求按 seq/context_id 唯一映射，caller 正确，无跨请求串入
  （RUN/ENF，26 轮）。
- **异常后同线程复用**：每 boot 12 触发 + 30 恢复（两 boot 24 触发 + 60 恢复，29b 更正口径）后归属正确（RUN，24 轮）。
- SettingsProvider/DP：正式分母 40/40（RUN/ENF，历史）。
- 转发读：origin 丢失（RUN，不计防御）。
- 第三方 OpenKeychain（13/1301）：endpoint/caller 解析正确，发布被 SELinux 阻断
  （BLOCKED_RUNTIME_PRECONDITION，19/20 轮）。32 轮静态审计补充：控制设备 write
  单一承载 PUSH/POP+POLICY_ADD/POLICY_CLEAR、无消息/凭据核验、主体字段自报——
  专用域写权无法限定为 publish-only（DESIGN_BLOCKED_PUBLISH_INTERFACE，32 轮；
  0 构建/0 部署/0 运行，未执行注入/清除/身份伪造攻击）。

## B2（对象/能力对应）
- ESP：backing 254:96 权威对象；proxy 0:45 同 ino 为投影（RUN）。
- MediaProvider：proxy/backing 同 ino；pending 分支双 join（RUN，22 轮）。
- **redacted 读**：能力对象=upper 0:45/ino=3000；辅助 lower open=254:96/0x8000
  为另一对象，二者可区分（RUN，25 轮）。
- 证据等级：两条直接写=运行对应证据；通用对象替换/竞态防御=GAP。

## B3（能力关系/失配）
- 直接写路径正向对应=provider 同线程 open→PFD、无转交（SRC+RUN）。
- **redacted 读（25 轮新证据）**：构造链 + cookie/文件身份（upper join
  cookie==FUSE proxy cookie==交付 fd）+ 字节级真值（41/911 差异全在 6 个 GPS
  EXIF 区间清零）共同建立“真实代理/合法非恒等变换”的正向对应；未观察到错误
  归属（RUN，构造不变式层面）。
- 明确限制：文件身份**不独自**证明内容视图；当前规则**没有显式脱敏状态字段**；
  本轮只证明“已确认路线可被限制”，不宣称通用视图识别；原始/脱敏视图不合并为
  完全相同的能力语义。
- **通用 B3 失配检测：未实现（GAP）**；运行时 κ 指纹复验仍未实现（SRC；18/20
  轮已写入论文）。论文未继续承诺该能力 → 列为未实现能力，不列为必须补齐项。
- pending 观察不是 B3 失配证据（22 轮）。

## B4（暴露前拒止）
- ESP：拒止在 backing open 后、PFD 构造/Binder 交付前；close-listener 仅在成功
  后注册（SRC+RUN）。
- MediaProvider：provider 线程、交付前（RUN）；pending 同（22 轮）。
- **redacted 读**：拒止在能力构造 upper open 的 security_file_open，之后无
  FUSE 回程、无 PFD、无 Binder 转交；App EACCES；backing 不变（RUN/ENF，25 轮）。
- **公开入口 C1/C2**：两链判定点均为能力 upper open、交付前拒止；双规则下每链
  3/3（RUN/ENF，27 轮）。
- **异常路径**：异常与拒止请求返回前均未交付目标能力（无 PFD、文件不变，24 轮）。
- 21 轮 17 项真实拒止全部满足“无能力交付 + 无副作用 + file_open_deny 增量”。

## 异常清理与生命周期（24 轮）
- E1 非法模式、E2 已删除对象均发布后/join 前；24 触发 + 60 恢复全 PASS；
  framework EXIT depth=0 + POP 发布 msg6 ok；kernel POP depth=0；0 mismatch；
  boot1 push=pop=141、boot2 124/124（RUN）。
- 同线程复用 boot1 22 对/boot2 27 对，后续归属正确（RUN）。
- 删除重建：X0 ino≠X1 ino（两 boot 均未复用）；旧 X0 规则不命中 X1，更新为 X1
  规则后真实拒止恢复，撤规恢复（RUN/ENF，两 boot）。
- “未发现资源遗留”**仅限本轮观测对象与采样范围**；取消/超时、inode 复用、
  路径键/路径尾生命周期未覆盖（SCOPE/GAP）。

## 真实并发归属（26 轮）
- 2 boot × 20 波 × 4 请求；40/40 波服务端活动区间重叠（不是所有判定指令同时
  执行）；160/160 请求唯一映射；40 目标拒止 + 120 允许分列；240 请求对=重叠
  佐证，不是 240 次独立试验；预试 3 波单列（RUN/ENF）。
- 0 STACK_MISMATCH；EXIT/POP depth=0；boot1 push=pop=178、boot2 110/110；
  FD 快照 NONE×3/boot；撤规恢复 3/3/boot（RUN）。
- 范围：仅 4 请求并发规模，不宣称任意并发度（SCOPE）。

## 公开入口覆盖与兼容（27 轮）
- C1=txn23 openTypedAssetFile、C2=txn14 openFile 两条实际链，均解析 6/501，
  在 openFileCommon 汇合；原生 18/18（RUN）。
- 单入口精确规则只覆盖相应 operation：R23 只拒 C1、R14 只拒 C2（RUN/ENF）。
- 两条精确规则实现两入口一致的目标限制：每链 S1 3/3 真实拒止、S2/S3/S4 各 3/3
  （RUN/ENF）。
- 能力等价仅限同一主体、对象及已核验操作/视图（全文件 O_RDONLY）。
- 当前 Android 制品接口兼容 ≠ 旧系统/OEM/其它 Provider/其它 API 族已验证
  （SCOPE）。
- 单入口规则放行另一接口=冻结规则的范围差异；逻辑目标覆盖两入口时规则集必须
  覆盖两者；不推荐未经验证的 operation 通配为通用方案（SRC/RUN）。

## 资格范围 vs 执法范围（22 轮结论保留）
- 静态资格把 picker/redacted/transcode/pending 标为未审查；运行时没有按分支
  类型自动 abstain（SRC）。
- pending 经 6/501 端点被真实拒止 → 执法以 (service,op) 为键（RUN/ENF，22 轮）。
- **redacted 观察同样说明**：该未资格分支经 6/501 被评估/执法，新增路线证据
  不自动证明整个 Provider 所有分支均满足资格（25 轮，与 22 轮一致）。
- 形式定理前提 / 离线路线审查 / 运行时实际检查 / 已测试执行范围 四者保持区分；
  措辞修订≠实现了自动分支隔离（GAP，保留）。

## 规则规模（21 轮）
- 正确性：N∈{1,8,32,128} 每规模 1 条 A+X 目标拒绝 + N−1 条合成填充；
  61 项检查=17 拒止 + 44 允许/健康/撤规（不是 61 次拒止）。61/61 PASS（RUN/ENF）。
- 延迟：2 boot × 20 区组 × 5 规模 × 5 记录=1000 行；主估计量=同区组 T(N)−T(0)；
  逐 boot 中位数 −3.34..+2.25ms；区组级 bootstrap CI（中位数/均值分列）全跨零
  → **未分辨增量**（RUN，限本会话条件）。

## 核心贡献声明（第 23–27 轮整合后保留）
- 跨层 join + 路由化决策：DP/Settings 40/40、ESP/MediaProvider 3/3（RUN/ENF）；
  全局覆盖=GAP。
- 运行时策略/撤规/主体反转：RUN（多轮）。
- 截断副作用差异：RUN（所测路径/模式）。
- L/C 公平比较：功能平局（12/13/16 RUN）；适配边际工作相近（16 账本）。
  **24–27 轮未新增 L 对照** → 不宣称对复杂路线防御更强或适配更省。
- 无 CDAC 性能：S2−S0 均值 +2.72ms（2.16–3.96）、S3−S0 +2.26ms（1.71–3.02）
  （11/12 RUN，仅 ESP 制品/负载）。
- 规则规模延迟：1→128 条未分辨增量（21 RUN）。
- 第三方接入：BLOCKED_RUNTIME_PRECONDITION（19/20 RUN），下游未验证。
- pending/redacted 范围观察：端点级执法 ≠ 分支级资格（22/25 RUN）。
- 异常清理/同线程复用、4 请求并发归属、代理视图对应、跨入口规则覆盖：RUN（24/25/
  26/27，均限定样本）。

## 收紧项（不写）
- 通用 B3 失配检测已实现；跨进程转发后身份保持；OEM/全局覆盖已验证；
  “未资格分支必被运行时 abstain/report-only”（22 轮推翻为“按端点执法”）；
  rule_match_total 可作为 file-open 命中计数；61 项正确性=61 次拒止；
  “边际成本亚微秒级”；1–128 规则“零成本/等效”；1000 请求=1000 独立 boot。
- 新增收紧（24–27 轮）：文件身份独自证明内容视图；规则字段含脱敏状态选择器；
  原始/脱敏视图能力语义相同；复杂路线已获通用视图识别；CDAC 对复杂路线防御
  更强/适配更省（无新 L 对照）；operation 通配已验证可作通用方案；任意并发度
  已证明；异常后全对象/全寿命无资源遗留；旧 Android/OEM 接口兼容已验证。


## 第 29b 轮更正后的口径状态（并入本轮，历史文件未改）
- 平台来源：本机无可核验旧版本运行时证据；a15/Pixel8 命名材料=Android 16 或
  SDK 桩（SRC）；论文平台来源段加排除句。跨版本结论保持
  `ARTIFACT_INSUFFICIENT_OLD_VERSION`（UNVERIFIED，非兼容/不兼容判断）。
- 并发归属范围：同一 Provider 服务内、不同服务线程重叠的逐请求归属
  （SCOPE，26 轮）；不补齐多跳转发身份。
- 异常计数口径：12 触发 + 30 恢复/boot；两 boot 24 + 60（RUN，24 轮）。
- R1（txn14/openFile）主体反转：**RUN/ENF（第 35 轮补齐，2026-10-29）**。
  35 轮在 C19 制品 cvd-35 上按原 27 轮协议补齐唯一缺项：规则
  `caller_uid=B operation=openFile ino=X s_dev=0:45 f_flags 0x3/0x0 deny` 下
  B→X 3/3 REAL_DENY（matched=1 reason=cdac35_rev + real-enforce errno=-13
  verdict=deny-now + 无 PFD + backing 不变 + file_open_deny 0→3→6），同一反转规则
  A→X 3/3 恢复放行、B→Y 3/3 放行，撤规后 A→X/B→X 3/3 恢复；同 boot 内固定规则
  (R14A) A→X 3/3 拒止、B→X/A→Y 3/3 放行。30/30 请求、6 真实拒止+24 允许。
  证据：35_r1_reversal_and_data_provenance_20261028/{07_results,08_conclusions}。
  第 25 轮 B→X 拒止仍=txn23 redacted 相关机制证据，不计入 R1（SCOPE）。

## 第 30 轮：对象别名、改名与名称联合（path_tail）
- R_obj（无 path_tail，ino+s_dev 精确）：改名后 3/3 DENY_PASS/boot；原名称新
  对象 3/3 ALLOW_PASS 且原对象 3/3 DENY_PASS/boot；硬链接 A 3/3 DENY_PASS、
  B 3/3 ALLOW_PASS/boot；撤规 12/12 ALLOW_PASS/boot（RUN/ENF，两 boot）。
- R_obj_name（path_tail=W.bin）：改名前 3/3 DENY_PASS/boot；改名后同一对象仍
  3/3 实测拒止（ALLOW_FAIL，不并入预期通过分母）；新别名 H2 3/3 ALLOW_PASS/boot；
  撤规 3/3 恢复（RUN/ENF，两 boot）。
- path_tail 数据流（31 轮审计）：
  - 匹配=精确 strcmp；want==NULL 通配；省略键→内核 NULL；读回 path_tail=-（SRC）。
  - 对象键=do_dentry_open 处 `file->f_path.dentry->d_name.name`（当次打开 file
    的 dentry，非 inode 反查 alias；SRC）。
  - ESP 写分支经 FUSE BPF 打开查找期缓存的 backing_path dentry；rename 路径不
    刷新该缓存（SRC）；运行观测=同请求 daemon lower open 用新名、判定打开用旧名、
    proxy 用新名（RUN）。
  - decision/decision-apply/real-enforce 打印 obj->path_tail=观测键（SRC）；
    H2 matched=0 打印 H2.bin 证明非规则回显（RUN）。
  - A 行为=成立；B 观测键取值=成立；C 成因主链=闭合（缓存 dentry 复用），
    底层 dentry/命名空间细节=UNRESOLVED_DETAIL（最小诊断方案见 OPEN_ISSUES）。


## 发布接口与 TCB 边界（32 轮 design-only；34 轮入稿）
- 可信生产者职责：从受审 Binder 入口读取原始调用者事实并写帧（框架
  CdacBinderContext，平台 Provider 域内运行）。
- 内核职责：按写入者 TID 的线程栈做实际存在性/对象/操作/谓词检查与裁决；
  内核**不独立认证**所有自报主体字段（SRC，32 轮）。
- 当前原型：发布（PUSH/POP）与规则管理（POLICY_ADD/CLEAR）共用同一
  /dev/iguard_ctl write；SELinux 只能整体授 write；无消息/凭据级检查；
  debugfs policy_ctl 同类无凭据（SRC）。
- 专用域补丁=DESIGN-ONLY（未编译/未部署/未运行）；不新增第三方执法通过样本；
  未实际实施规则注入/清除/身份伪造（32 轮自证）。
- 信任范围=被授写权的整个 SELinux 域，而非“只信任某个入口函数”（34 轮表述）。
- 第 33 轮（本目录）完成：编译策略层面穷举潜在写入域——直授 write 的 6 个
  域（mediaprovider、mediaprovider_app、platform_app、priv_app、radio、system_server）
  + userdebug 调试主体 su（typepermissive，规则管理写入由此发生）；dev_type/
  mlstrustedobject 属性无 chr_file write 载体允许；运行态写入者 scontext 未逐条
  记录（域由进程/包映射推断），radio/system_server 有 allow 无写入证据。详见
  EFFECTIVE_WRITER_MATRIX.csv。
