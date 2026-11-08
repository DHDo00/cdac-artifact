# PAPER_HANDOFF.md — 论文接入草稿（数据反馈 + 短片段，供 Overleaf 整合）

主稿不被修改。以下草稿只供用户在 Overleaf 整合；数字均有贡献行
（`outputs/accounting/COUNT_CONTRIBUTIONS.csv`）。

## English — paragraph 1 (policy configurations, full-paper scope)

> Across the runtime experiments reported in this paper---SettingsProvider,
> DownloadProvider, ESP, and the MediaProvider caller--object, method-label,
> write, and final-entry studies, including the A15/A17 ports---we re-derived
> every policy figure from the original add and readback records. After role
> normalization, which keeps exact device selectors (0:45, 0:46, 254:96)
> distinct from the wildcard (0:0), retains name/path selectors and relation
> type/stage, and merges only cross-boot UID/inode rebinds, the adopted
> evidence resolves to **11 target-deny logical configurations and 7
> control/reversal configurations**, plus one synthetic filler family that is
> reported separately. **Two target and six control configurations are
> add-only records whose operation field lacks a packaged dump and are listed
> as unresolved candidates**; the ESP deputy rule's object label across rounds
> and cross-platform device numbers remain separate equivalence questions.
> Rebinding or redeploying a configuration does not create a new logical
> configuration.

建议接入位置：`sec:eval:integration` 或附录核算小表；当前正文只声明
MediaProvider 四配置，**这段“11+7”全稿口径是可选项**，如采用必须带上
“2+6 候选”限定，否则退回现有四配置表述。

## English — paragraph 2 (templates and cost)

> Template provenance separates seven retained canonical route descriptions,
> two parameterized rule generators (one target, one synthetic filler), and
> nine post-hoc field-structure signatures; **no standalone historical
> template file was retained (NOT_RECORDED), and verified expert active hours
> remain NOT_MEASURED**. The MediaProvider endpoint increment over the shared
> mechanism remains **21 added and 6 removed registry code lines plus one
> kernel allowlist entry**. The historical A15 port totals **892 added diff
> lines (763 code) including the checkfc build fix, or 890 lines (762 code)
> for the mechanism alone**. The 20/23 source denominator, origin cross-hop
> propagation limits, and generic κ revalidation constraints are unchanged.

## 中文对应稿

1. 论文所报告的运行实验（SettingsProvider、DownloadProvider、ESP，以及
   MediaProvider 的调用者—对象、方法标签、写与末跳转发研究，含 A15/A17 移植）
   中，所有策略数字均由原始 add 与读回记录重建。角色归一后（精确设备选择器
   0:45、0:46、254:96 与通配 0:0 分开；path/name 选择器与 relation type/stage
   保留；仅合并跨 boot 的 UID/inode 重绑），已采用证据解析为 **11 个目标拒止
   逻辑配置 + 7 个控制/反转配置**，另有 1 个合成 filler 家族单列。**其中 2 个
   目标与 6 个控制配置是仅有 add、operation 缺 dump 的未决候选**；ESP deputy
   规则跨轮对象标签与跨平台设备号的等价问题继续单列。重复绑定或重复部署不产生
   新逻辑配置。
2. 模板按来源分列：7 条保留 canonical 路线描述、2 个参数化生成函数（目标 1 +
   filler 1）、9 种事后字段结构签名；**历史独立模板文件 NOT_RECORDED，经核验的
   专家主动工时 NOT_MEASURED**。MediaProvider 在共同机制上的端点增量维持
   **registry +21/−6 + allowlist +1**。历史 A15 移植 **892 行（763 代码行）已含
   checkfc 修复**，机制口径 890 行（762 代码行）。20/23 源码分母、origin 跨跳
   传播限制与通用 κ 复验边界不变。

## Appendix mini-table (optional)

| scope | CDAC target configs | control configs | filler family | note |
|---|---|---|---|---|
| current paper (v8) | **11** (2 candidates) | **7** (6 candidates) | 1 | candidates = add-only, op/rel UNKNOWN |
| previous confirmed subset (R39+R41) | 5 | 0 | — | not a whole-paper total |
| completed, pending adoption | 7 (+1 shared with paper) | 1 | — | R40-72 / R40-720 denominators kept |
| union (paper ∪ pending) | — | — | — | 26 deny logical configs |

## Short LaTeX snippet (optional; user integrates in Overleaf)

```latex
% optional: after the existing "four configurations" sentence in
% \subsection{Integration and Policy Effort}
Across all runtime experiments reported in this paper, the add/readback
records resolve to \textbf{11} role-normalized target-deny configurations and
\textbf{7} control/reversal configurations; two target and six control
configurations remain add-only candidates whose operation field lacks a
packaged dump. Exact device selectors (\texttt{0:45}, \texttt{0:46},
\texttt{254:96}) are never conflated with the wildcard \texttt{0:0}.
```

## 可以入稿 / 保持未知（一句话清单）
- 可入稿：registry +21/−6、allowlist +1（已在稿）；方法标签 flags=0、device
  0:0（已在稿）；7 canonical + 2 生成函数（分列）；NOT_RECORDED；NOT_MEASURED；
  892/763（含 checkfc）与 890/762 机制口径；全稿 11+7（须带 2+6 候选限定）。
- 保持未知：历史专家模板总数；专家主动工时；891/763（DERIVED，勿替换历史值）；
  R30-name-O、A17 boot2 与 SettingsProvider 变体的缺原件；等价关系候选。
