# RESULTS_SUMMARY.md — R1 主体反转最小矩阵结果（第 35 轮，cvd-35 boot1）

制品：C19_media + kernel_openkeychain_dist（只读复用，哈希已核）。
boot：aosp_cf_x86_64_only_phone / Baklava BP4A.251205.006 / Android 16 /
kernel 6.12.74-android16-6-maybe-dirty / SELinux Enforcing。
UID：A=10121、B=10122。X ino=2931、Y ino=2951；backing dev=65120(254:96)；
App 视图 0:45。X sha=e22785cd…、Y=f3d29ccd…；B redacted X=96f60e…、Y=3116065d…。

## 冻结矩阵结果（每腿 3 次，C2=txn14 openFile→6/501）
| 块 | 规则（policy_dump 读回） | 请求 | 预期 | 实测 |
|---|---|---|---|---|
| B0 | 无（count=0） | A→X | 原生可用 | 3/3 ALLOW（原字节） |
| B0 | 无 | B→X | 原生可用 | 3/3 ALLOW（redacted） |
| B1 | caller=10121,operation=openFile,ino=2931,s_dev=0:45,reason=cdac35_r14a | A→X | CDAC 真实拒止 | **3/3 DENY_PASS** |
| B1 | 同一 R14A | B→X | 保持可用 | 3/3 ALLOW（matched=0, caller=10122） |
| B1 | 同一 R14A | A→Y | 保持可用 | 3/3 ALLOW（matched=0, obj 2951） |
| B2 | caller=10122,operation=openFile,ino=2931,s_dev=0:45,reason=cdac35_rev | B→X | CDAC 真实拒止 | **3/3 DENY_PASS** |
| B2 | 同一 R_rev | A→X | 恢复可用 | 3/3 ALLOW（matched=0, caller=10121） |
| B2 | 同一 R_rev | B→Y | 保持可用 | 3/3 ALLOW（matched=0, obj 2951） |
| B3 | 撤规（count=0 读回） | A→X | 恢复可用 | 3/3 ALLOW |
| B3 | 撤规 | B→X | 恢复可用 | 3/3 ALLOW |

## 拒止证据（6 次，逐条满足冻结六判据）
1. policy_dump：B1/B2 各 count=1 且字段核对（caller/operation/ino/s_dev/f_flags/decision）。
2. ENTER caller 正确（A=10121/B=10122）→ PUBLISH msg5 ok。
3. 命中 join/decision：obj_ino=2931、obj_s_dev=0:45、obj_f_flags=0x28000、
   matched=1、reason=cdac35_r14a(×3)/cdac35_rev(×3)。
4. `real-enforce … errno=-13 verdict=deny-now`（各 3 条，logcat main 捕获）。
5. App=FileNotFoundException:EACCES，无 READ_CPC ok（无 PFD 交付）。
6. backing X 全程不变（ino=2931、size=911、mtime、sha256=e22785…）；B1/B2 各
   file_open_deny +3（quiet_counters 0→3→6；B3 撤规后保持 6）。
   context_push_ok=context_pop_ok 全平衡（5→11→20→29→35），0 嵌套失配。

## 区分两类“反转”（本轮直接证据）
- **固定规则调用者选择性**：R14A 下 B→X matched=0 放行（caller≠A）。
- **规则主体反转**：R_rev(caller=B) 下 B→X matched=1 真实拒止，A→X 恢复放行。
两者分别成立，本轮不以前者替代后者。

## 原始文件
- PER_REQUEST_LEDGER.csv（30 行，verdict: 6 DENY_PASS + 24 ALLOW_PASS）
- B*/_app.txt、B*/_framework.txt、B*/_kernel.txt、B*/_am.txt（逐请求）
- b1_rule_dump.txt、b2_rule_dump.txt、*_rule_dump_clear.txt、final_policy_dump.txt
- setup_pre/b0_post/b1_pre/b1_post/b2_pre/b2_post/b3_post_qc.txt（计数器快照）
- b*_backingX/Y.txt、*.sha（对象前后状态）
- proc_attr_*/proc_attr_end_*（进程域采样：A/B=untrusted_app、MediaProvider=mediaprovider_app）
