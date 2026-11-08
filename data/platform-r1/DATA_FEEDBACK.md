# DATA_FEEDBACK.md — 三版本 R1 数据反馈（自包含，供论文修改对话直接使用）

生成：2026-11-02（Asia/Shanghai）。轮次目录
three_version_r1_3boot_scope_alignment_20261102_100240/。
本轮只交付数据反馈、表格数据、证据索引与归档；未修改论文、未编译 TeX、未生成 PDF。

## 0. 一句话结论
CDAC 三版本（A15 修正版 / A16 R35 / A17）代表性 openFile 路线现各有 **3 个独立启动、
每 boot 30 个正式请求、每版 90 个正式请求**：每版 **18 次真实拒止 + 72 次允许/恢复**，
0 失败、0 无效、0 重试（正式请求阶段）。全部为逐请求核验的实际值，不是预填。

## 1. 可直接用于论文的表格数据（Table XV，实际核验值）
| 项目 | A15 修正制品 | A16 R35 制品：原批次及重复 | A17 既有制品及重复 |
|---|---|---|---|
| 独立启动数 | 3 | 3 | 3 |
| 每 boot 正式请求 | 30 | 30 | 30 |
| 全组正式请求 | 90 | 90 | 90 |
| 真实拒止 | 18 | 18 | 18 |
| 允许/恢复 | 72 | 72 | 72 |

每 boot 明细（9 行，见 PER_BOOT_SUMMARY.csv）：
- A15：boot1=A15CLEAN-R1(历史) 30/30=6+24；boot2=A15R1-B2 30/30=6+24
  （boot_id cf1d72c2-e1c2-41d0-8df5-0cb56d63877e，inoX=3363，deny 0→3→6，push=pop=41）；
  boot3=A15R1-B3 30/30=6+24（boot_id 9c9530e6-ec5d-43cf-b6d8-fb1521cead63，inoX=3338）。
- A16：boot1=R35 cvd-35(历史) 30/30=6+24；boot2=R35-B2 30/30=6+24
  （boot_id be17e2f6-8d1c-4b7c-9edd-ff32e95f04f8，inoX=2967）；boot3=R35-B3 30/30=6+24
  （boot_id 30f4e9c8-8a25-4142-ad38-074602b08943，inoX=2994）。
- A17：boot1=cvd-73(历史) 30/30=6+24；boot2=cvd-74(历史) 30/30=6+24
  （boot_id 86a4d79b-7725-4fe6-ae5e-1e6ad0771570）；boot3=A17R1-B3 30/30=6+24
  （boot_id 9b1a4228-0745-4391-9579-a680a919ab62，inoX=3544）。

脚注必须随表：
1. 每版同一冻结制品、三个独立启动；A16 列=R35 冻结制品（原始批次 boot1 + 新增重复
   boot2/3），不能把 90 全写成历史 R35 原有数据；A15 采用修正制品（system.img=70c2ab35…、
   Binder.java=859a38a7…），新增批次原件单列；A15 旧制品（system.img=186ea808…）单列
   历史，不与修正版合并。
2. 正式分母不含空策略预检、装规/读回/撤规、4/301 清理诊断、全局发布计数；静态结论
   与源码资格不计运行请求。
3. 三版共用 CDAC Linux 6.12.74 A16 谱系内核制品 kernel_openkeychain_dist
   （bzImage=0c0f7e4c…、initramfs=0fa2d559…）；A15 原生 6.6 未做 CDAC 回移，
   A17 未做任意内核兼容验证。
4. 只支持 MediaProvider txn14 openFile→6/501 单路线 + 指定组合的调用者选择性、
   主体反转、撤规恢复；B0–B3 是实验块，不是论文资格条件 B1–B4。
5. 3 boot 是本项目重复验证设计，不是统计充分性的通用门槛；9 个 boot 分属三版各自
   制品，不是 9 个独立平台，三版不合并为 270/270。

## 2. 可更新的其他数字/描述
- 内核：三版均 6.12.74-android16-6-maybe-dirty；A15 release=15/sdk=35、
  A16 release=16/sdk=36 Baklava、A17 release=17/sdk=37；SELinux=Enforcing。
- 复用：历史 4 个完整 boot 全部逐请求账本 sha256 复验一致（各 30=6+24），直接纳入；
  新增 5 个 boot / 150 个正式请求全部为 2026-11-02 实测。
- 成本口径（维持 porting_reuse_and_adaptation_cost 轮 + ER6 勘误）：
  A15 修正制品接入规模 891/763（892/763 含 checkfc；修正 Binder 净少 1 空行）；
  A17=890/763；CDAC 自有 R1 源文件原样复用 4/5（Binder 钩子按 fragment 计，
  Binder 不在分母）；人工主动时间 UNMEASURED。

## 3. 应保持/不可改的结论与口径
- 每条拒止的六判据链：规则读回 → txn14/6/501 与 caller/对象正确 → ENTER/PUBLISH 与
  PUSH/VFS_JOIN 可关联 → matched=1、reason 对应 → real-enforce errno=-13 deny-now →
  App EACCES 无可用 PFD → backing 前后状态/内容不变、file_open_deny 0→3→6。
- 每条允许/恢复：PFD 实际可用、读取 911B、sha 符合 owner(e22785cd…)/redacted(96f60e…)
  真值；B 的真值按 B 自己（不等于 A）。
- 发布 PUSH/POP 与管理 ADD/CLEAR 共享 /dev/iguard_ctl write，不是 publish-only；
  A15/A17 最小移植写域只有 mediaprovider(_app)，不与 A16 R33 六域套用。
- 90 是计划正式尝试数；本轮全部实现，但不允许把未来未补齐/失败的情况照抄为 90/90。

## 4. 四条证据线如何区分（写作时不要混用）
1. 三版本 R1 回归（本文 §1）：普通 A/B 应用、MediaProvider txn14 openFile→6/501、
   真实 PFD 与真实拒止——每版 3 boot/90 请求。
2. 4/301 清理诊断：su 域两进程 app_process 夹具、caller UID0、通用映射 4/301、
   无真实文件交付；5 次客户端尝试、4 个服务端 frame；D1 正常清理 / D2 RuntimeException
   后同 TID 继续 / D3 Error 展开完成一次 POP+内核清理成立，**Error 后同进程继续服务
   未建立**；不写成 MediaProvider 执法路线，不计入 90。
3. E6/E7/E8 静态结论（限定修正 A15 + 该路线/进程/冻结配置）：E6 checkParcel 仅
   return-void（删除“超大 reply 抛 RuntimeException”表述，不与 TransactionTooLargeException
   混同）；E8 observer.callStarted 不可达（MediaProvider sObserver==null）；E7
   traceEnd/observer.callEnded 不可达（冻结启动无 tracer、observer==null，exit 为
   finally 首条执行语句）；均为源码+配置链结论，不升级为全 boot 运行时事实。
4. GraphicsStatsService 源码资格：原 23 路径审计中的 3 条路径（requestBufferForProcess
   的 existing/new/stale 三分支，宿主 system_server）B1–B4 均 ESTABLISHED；
   20/23 是源码资格计数不是运行验收；system_server 不在本轮 MediaProvider R1 运行
   范围，但在论文范围；其 observer/trace unchecked 异常窗口保持 UNKNOWN_BOUNDED，
   三版本 R1 成功不能推出 system_server 已通过。

## 5. 仍缺证项（写作时保留限制句）
- A15B3、A17B3：矩阵期间 debugfs 挂载丢失，policy_dump 的 debugfs 快照为空；以内核
  iguard_ctx policy_op add/clear 全字段日志（连续 logcat 流）+ 结束重挂载读回
  runtime_policy_count=0 + 计数器 0→3→6 补偿，标“部分记录”。
- 历史 boot（A15CLEAN-R1、R35、A17 boot1）未记录 boot_id（历史缺证，保留不回填）；
  A17 boot1 另有清单记账缺陷 + 3 条未归因发布；A17 boot2 有 debugfs-after-root 顺序
  缺陷（不影响正式矩阵）。
- 无逐写 scontext：域身份为采样时点证据，不升级为每次 write 证据。
- 内核精确源码树 SOURCE_MISSING；人工主动时间 UNMEASURED。

## 6. 本轮执行边界（可向论文修改对话声明）
新增正式请求 150（计划 150）；构建/同步/下载/机制修改/论文编辑/PDF 生成均为 0；
正式请求阶段失败 0/无效 0/重试 0；启动尝试有 7 次基础设施失败（全部保留原始日志，
见 FAILURES_AND_EXCLUSIONS.md）：A15 launch_cvd 无 --enable_tap_devices 参数、
AF_UNIX 路径 118>108、userdata 路径错位、新实例号无预建 tap（改用 cvd-2/cvd-3）、
A16 脚本误删 --enable_tap_devices、A16 夹具 APK 子目录路径（A16B2 与 A16B3 各一次）。未删除任何文件、未改
冻结镜像、未写历史目录、未触碰其他任务实例。

归档入口：README.md、FINAL_STATUS.txt、TABLE_XV_DATA.md、PER_BOOT_SUMMARY.csv、
THREE_VERSION_SUMMARY.csv、ARTIFACT_AND_RUNTIME_IDENTITY.csv、SCOPE_ALIGNMENT.csv/.md、
GRAPHICSSTATS_SCOPE_RECONCILIATION.md/.csv、CLAIM_EVIDENCE_MAP.csv、
FAILURES_AND_EXCLUSIONS.md、MISSING_AND_LIMITATIONS.md、SHA256SUMS.txt、audit_package/。
