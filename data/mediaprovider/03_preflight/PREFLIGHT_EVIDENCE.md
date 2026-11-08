# PREFLIGHT_EVIDENCE.md — 预检证据位置（第 39 轮）

预检协议见 PROTOCOL.md §7；预检结论在每个 boot 的 ledger.log 输出为
"preflight notes: …"。原始证据（单列，scientific=0）：
- 07_results/boot<N>/raw/PRE-B<N>-MAKE-{image1,image2}_*.txt（建对象）
- 07_results/boot<N>/raw/PRE-B<N>-READ-{AX,BX,AY,BY}_*.txt（四个视图读 oracle）
- 07_results/boot<N>/raw/PRE-B<N>-W_*.txt 与 PRE-B<N>-RESTORE_*.txt（写 oracle + 恢复）
- 07_results/boot<N>/raw/PRE-B<N>-RULE-{MA,MB,LW,LR}_{add,dump,dump_clear}.txt（规则往返）
每 boot 预检全部 PASS：读 sha/marker 与冻结真值一致；写 app sha==离线期望==backing sha；
restore 回 e22785cd…；四条规则 dump 逐字段正确且 clear 后 count=0。
