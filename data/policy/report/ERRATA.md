# ERRATA.md — 2026-11-02 范围绑定与策略核算收尾（相对 091724 修正轮）

本轮把权威主稿 `paper_snapshot/102901.txt`（Library 版次 8，
SHA-256 `e18ef6a5…`) 与既有字段修正/原始证据对齐。没有新增实验、没有
改动机制、没有改主稿；只做离线范围绑定与重算。

## A. 输入身份（实际核验）
- `CDAC_ACCOUNTING_SCOPE_INPUT_20261102.zip`：422427 字节，
  SHA-256 `59daca84b49d45c94361aaab09e74139d6e7047d376b32dceb998985c06e124b`。
- `paper_snapshot/102901.txt`：121715 字节，SHA-256 `e18ef6a5e584b0d9f984f430e7ab617b7c92d9bcf98102e7cbcbeec9496181a1`
  （版次 8；`REVISION_MANIFEST.json` 的 `updated_main_sha256` 一致，
  `base_main_sha256=4871e368…` 是修改前基线，不再被当作本次主稿）。
- 服务器既有包 `policy_accounting_correction_20261102_091724.tar.gz`：
  587979 字节，SHA-256 `952d9b226366fdd9d9dae5264e632ab73dd6da33ab2a7f879041e1ef31dd754b`。
- 三者在全新目录解压/读取后逐一核验通过（见 `outputs/CHECK_LOG.txt` I01–I07）。

## B. 范围绑定结论（不再用“main 5”冒充全文总数）
上一轮 `MAIN_LASTKNOWN` 31 行 + `MAIN_INCLUDED` 5 行逐项对照当前主稿重判，
写入 `outputs/accounting/PAPER_BINDING.csv` / `SCOPE_MANIFEST.csv`。要点：

- **已入稿（IN_PAPER）**：SettingsProvider（8/701）、DownloadProvider（4/301）、
  ESP N/L/C 与 wt 诊断、ESP 并发（160）、ESP 规则数 61 项检查与 1000 条时延、
  ESP no-grant（R41, 28）、MediaProvider 调用者—对象矩阵（R39-ma/mb, 600）、
  方法标签矩阵（R39-lr/lw, 480）、写对比（R16）、更早 30/48 请求批（R35/R36）、
  末跳转发读（R38, 42）、A15/A17 平台移植（修正/历史制品分列）。
- **已完成待入稿（COMPLETED_PENDING）**：R40-72 与 R40-720（72/720 分母分别
  保留，正文只定性保留 B1“不可判定”结论）、R24-lc0/lc1、R25、R27-eq23、R30-obj/name-W。
- **诊断/无效（DIAGNOSTIC_INVALID）**：R36-INVALID、R38-ABORTED、R39-preflight(204)、
  R27-probe、R29（0 boot 非实验）、A15 兼容性诊断 boot。
- **证据不足（INSUFFICIENT_EVIDENCE）**：R30-name-O（仅报告级，add/dump 原件未定位）。
- 两个同名 R39 分开：矩阵任务（1080 条正式请求）≠ 来源恢复任务（0 科学请求，
  对应 app:media-build-provenance）。

## C. 保留的语义修正（未回退）
- R39 LR/LW 六份真实 dump：`f_flags_mask/value=0x0`、`f_mode=0x0/0x0`、
  `s_dev=0:0`、operation 分别为 openFile/openAssetFile；LR↔R36-SR、
  LW↔R36-SW 同键合并（请求实际打开 flags 不写入规则谓词）。
- 设备 exact `0:45/0:46/254:96` 与 wildcard `0:0` 分开；path/name、
  relation type/stage、主体角色全部保留在键中。
- operation 只以权威 dump 为准；add 回显缺字段 → `UNKNOWN`，只在同
  (round,boot,reason,caller) 存在唯一 dump 时标 `dump-inherited`。
  未知≠默认值：R12×6、R16×8 共 14 条 add-only 行保持候选状态。
- 相同键做 UNION 合并（sources/purposes/scope 全保留），不再字典覆盖；
  R39-mb 的 target 用途与 R35-rev 的 subject-reversal 共存 = MIXED_target+control，
  分类由用途集合推导、与读取顺序无关。

## D. 同范围算法比较（旧 → 修正；固定实验行范围）
- CDAC deny 配置：26 → 24（Δ −2）。逐项：R39-lr 假键并入 R36-SR（−1）、
  R39-lw 假键并入 R36-SW（−1）、exact 0:45 不再按前缀当 wildcard 使
  R27-eq23 与 R40-RA 拆分（+1）、R30-name-O 无原件被剔除（−1）。
- 目标/MIXED：19 → 17；其它控制：7 → 7（R16-flags1 由目标改判控制、
  R35-rev/R39-mb 由控制改判 MIXED，净 0）。filler 1 → 1；L 1 → 2。
- 实例：45 → 56（R39 LR/LW 六份 +6、MA/MB boot2/3 +4、R27-probe +1）。
- 命令：29 add → 39 add（R39 三 boot add 原件），clear 10 → 10。
- 事后结构签名 8 → 9；模板口径 7 canonical + 2 生成函数 + 历史可执行模板
  NOT_RECORDED（不再是“9 个专家目标模板”）。

## E. 固定修正算法下的范围比较
见 `COUNT_CHANGE_DECOMPOSITION.csv` Panel B：
- 上轮确认子集（R39 四配置 + R41）= **5**（非全文总数）。
- 当前全文（IN_PAPER）= 11 个目标/MIXED + 7 个其它控制 + 1 filler 家族
  （= 18 个 deny 逻辑配置）；其中 2 目标 + 6 控制为缺字段候选（op/rel UNKNOWN）。
- pending-only = 8（7 目标 + 1 控制）；IN_PAPER∩PENDING = 1
  （openFile A,X exact 0:45：R39-ma/R35 已入稿、R27-eq14 待入稿同键）。
- IN_PAPER∪PENDING deny = 26。
- 无法确定的等价关系单列：R38 `X(proxy)` ↔ R40-RD `X`（同一规则、reason 派生
  对象标签不同）；R12-C/R16 add-only ↔ 有 dump 的 ESP A,X；A15 exact `0:46`
  ↔ A16/A17 exact `0:45`（跨平台设备号）。

## F. 模板/实例/部署口径
- 模板：7 条 canonical 路线描述 + 2 个 R21 生成函数（target/filler）+
  9 种事后字段结构签名 + 历史可执行模板 NOT_RECORDED（状态，不是“1 个模板”）。
  历史专家模板总数 = **UNRESOLVED**。
- 实例：“56 deny + 127 filler”作为**已解析子集**成立（本轮加 A15/A17 后
  deny 实例 62，口径未变）；实例键 = (round,boot,caller_uid,ino,s_dev,flags,
  mode,decision,reason)，同 boot 同绑定值重复部署合并；证据层次
  DUMP_AUTHORITATIVE / DUMP_INHERITED；A17 boot2 与 R30-name-O 缺原件单列。
- 部署：“39 add + 10 clear”是解析到的命令记录（本轮含 A15/A17 为 45 add）。
  add 与同 (round,boot,reason,caller) 的有效 dump 读回配对 → **可核验成功部署 31**；
  无读回的 14 条（R12×6、R16×8）为候选。clear 单列，不计 deny 部署。

## G. 成本结论边界（保留）
- MediaProvider registry +21/−6、内核 allowlist +1：既有共同机制上的端点增量。
- A15 历史 892/763 **已含** checkfc（机制口径 890/762）；审稿所称修正版
  891/763 标 DERIVED（分析说明不替代原始 diff），历史与修正分列。
- 专家主动工时 = NOT_MEASURED；不以 LOC/墙钟/工具耗时推算人力。
- 四 RQ、20/23 源码分母、origin 跨跳传播限制、通用 κ 复验边界均未改动。
