# PAPER_INSERTION_DRAFT.md — 建议插入论文/审稿回复的 R1 补证段落（第 35 轮草稿）

仅提供插入草稿，**不修改历史论文归档、不做完整论文整合**。基线=第 33 轮
02_paper_revision（第 34 轮人工 B 版）。所有数字来自本轮
07_results/PER_REQUEST_LEDGER.csv 与 08_conclusions/R1_RESULT_AND_LIMITATIONS.md。

## 1. 建议插入正文（英文，追加到 evaluation_completed.tex
   §Cross-entry rule scope and compatibility 段末，label sec:eval:entrycoverage）

> A subject-reversal control completes this entry's caller-selectivity evidence.
> On the same 6/501 artifact, a reviewed rule that differs only in the bound
> caller (caller~$B$, \codepath{operation=openFile}, object $X$) denies $B$'s
> read of $X$ in 3/3 trials before descriptor return
> (\codepath{real-enforce, errno=-13}, no PFD, backing file unchanged), while
> the same reversed rule restores $A$'s read of $X$ in 3/3 trials and keeps
> $B$'s read of the nonmatching object $Y$ usable in 3/3 trials; rule
> withdrawal then restores $A{\to}X$ and $B{\to}X$ in 3/3 trials each. Within
> the same boot, the fixed caller-$A$ rule denies $A{\to}X$ in 3/3 trials while
> $B{\to}X$ and $A{\to}Y$ remain usable. This separates fixed-rule caller
> selectivity from rule-subject reversal on the \codepath{openFile} entry; it
> supports caller-selectivity for this route only and does not establish
> device-boundary authentication of self-reported subject fields or a
> publish-only permission split.

（如章节有字数压力，可仅保留前两句并把最后一句并入限制段。）

## 2. 建议补充表格行（evaluation_completed.tex §Supplementary 表，可选项）
> & 2 entries, 1 boot; txn14 subject reversal: 3/3 deny ($B{\to}X$), 3/3
> recovered ($A{\to}X$), 3/3 object control ($B{\to}Y$), withdrawal 3/3 each;
> fixed-rule selectivity re-confirmed in-boot

## 3. 审稿回复段落建议（中文，替换 REVIEW_RESPONSE_DRAFT 中 R1 行）
> R1（txn14/openFile 主体反转）已在第 35 轮按原第 27 轮冻结协议补齐：在
> service 6/501 的 openFile 入口上，仅将规则主体由 A 改为 B（同操作/同对象），
> B→X 3/3 在能力交付前被真实拒止（matched=1 + real-enforce errno=-13
> verdict=deny-now，无 PFD，backing 不变），同一反转规则下 A→X 3/3 恢复可用、
> B→Y 3/3 保持可用，撤规后 A→X/B→X 3/3 恢复；同 boot 内固定规则（caller=A）
> 的调用者选择性亦分别复验。30/30 请求一次通过（6 真实拒止+24 允许/恢复）。
> 这证明该入口的调用者选择性，不证明设备边界独立认证自报主体字段，也不改变
> publish-only 权限耦合结论。第 25 轮 txn23 redacted 证据仍单列为相关机制证据。

## 4. 与旧数据的关系（必须标明）
- 本轮新增运行证据=**仅 R1 主体反转块与同 boot 内对照**（B0–B3，30 请求，
  1 boot，cvd-35，C19 制品）。
- 第 27 轮 C2 原生前提/PhaseA/PhaseB（18+4+30 请求）与第 25/16 轮证据=旧数据，
  本轮不改写、不并入新分母。
- 数据口径核验（METRIC_PROVENANCE.csv）为旧数据核对，**不是新增实验**；重算与
  汇报一致，无修改。

## 5. 不扩大范围（草稿自限）
- 不写：跨启动可靠性、任意并发、其它 Provider/API 族、旧版本兼容、设备边界
  认证、publish-only 已解决。
- 不修改：history archives、33_main.diff、A/B 基线、unified_results_table
  （如正文并入，需另由后续轮次完成全文整合与编译）。
