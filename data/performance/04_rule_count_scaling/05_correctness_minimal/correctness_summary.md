## 正确性结果表（boot1，每个非零规模 3 轮；boot2 仅健康块）

| 规模/步骤 | T1 A→X 拒止 | T2 A→Y 允许 | T3 B→X 允许 | T4 撤规后 A→X |
|---|---|---|---|---|
| N=1 | 3/3 | 3/3 | 3/3 | 3/3 |
| N=8 | 3/3 | 3/3 | 3/3 | 3/3 |
| N=32 | 3/3 | 3/3 | 3/3 | 3/3 |
| N=128 | 3/3 | 3/3 | 3/3 | 3/3 |

| 位置检查 N=128（目标规则最后安装）| 3/3 A→X 拒止 | - | - | - |

| 健康块 | boot1 | boot2 |
|---|---|---|
| H0 无规则 A→X 原生允许 | ALLOW_PASS | ALLOW_PASS |
| H1 无规则 T→X 计时能力可用 | WRITE_OK 行 | WRITE_OK 行 |
| H2 单目标规则 A→X 真实拒止 | DENY_PASS | DENY_PASS |
| H3 对象/调用者控制+撤规恢复 | 3× ALLOW_PASS | 3× ALLOW_PASS |

拒止判据（全部满足才算 DENY_PASS）：①policy_dump 含目标规则且字段核对（service_id=5 op_id=401 caller_uid=A operation=openAssetFile ino=X s_dev=254:96 decision=would-deny）②App WRITE_FAIL（无可用能力交付）③文件 size/sha 不变（无副作用）④quiet_counters file_open_deny +1 （真实执法分支计数；boot1 累计 deny=16=H2+T1×12+POS×3，boot2 累计 deny=3=H2+diag N1/N128）。LOG_OFF 下 real-enforce 文本行被门控关闭，由 diag 段在 LOG_ON 捕获（N=1、N=128 各一次，errno=-13 verdict=deny-now）。

每个非零规模安装后读回核实：runtime_policy_count 与逐槽行数 == N（N=1/8/32/128 各 3 次全部 verified=True）。
