# INTEGRATION_COST.md — N/L/C 接入成本与贡献判断（运行结果填写后定稿）

## 三侧对照表（运行后填写）
| 维度 | N 原生 | L 局部检查 | C 完整 CDAC |
|---|---|---|---|
| 目标调用被拒 | (运行后) | (运行后) | (运行后) |
| 合法调用保留 | | | |
| 返回能力实际可用 | | | |
| 文件副作用(主对照/截断) | | | |
| 身份信息来源 | 无附加策略 | Binder.getCallingUid()（provider 入口，身份未清除） | 统一 Binder 钩子发布的 caller + VFS join（backing dev/ino） |
| 对象信息来源 | | provider documentId（provider 自身解析键） | do_dentry_open 后 backing dev/ino（f_flags/f_mode） |
| 检查位置 | | openDocument 入口（打开前） | backing do_dentry_open 之后、PFD 构造/Binder 交付之前 |
| 修改文件/代码量 | 0 | 1 文件 ~45 行（applied_L.diff） | framework(registry/Binder/ContentProvider/ESP…) + JNI + kernel(iguard_ctx/binder/fuse/open) + 模块（89 行 delta + ESP 2 条） |
| 新路径适配 | 无 | 每 provider/入口各需一段检查 | 注册端点 + 一条规则（无代码改动） |
| 策略配置 | 无 | setprop（uid|docId） | iguardctl v2 规则 add/clear |
| 清理/维护 | | 清空属性 | policy clear（计数器可核） |

## 逐项判断（运行后填写完成）
1. 直接路径行为差异：N 无附加策略；L/C 均在 A+X 拒绝（FNF）并保留 A→Y、B→X；
   截断模式 L 拒止且文件不变，C 拒止但文件已截断。
2. 差异来源：主要是检查位置与对象信息（L=入口前+documentId；C=backing 打开后
   +dev/ino）；身份信息在该路径等价（都是可信调用者 uid）。
3. 局部检查是否已足够：当前 ESP 单入口案例——是（行为上），且截断副作用更少。
4. CDAC 实际增加：跨层对象证据、统一路由化决策、运行时规则（不改代码）、
   可复用与生命周期计数；本单路径未显现行为收益。
5. 尚无实测证据：多入口/转交/B3-B4 下的收益、更大规模与错误率，均未实测。

## 论文依据核对（仅机制分析，不冒充复现）
- 论文 VI 表述："a file hook lacks the Binder caller and framework entry；
  an LSM implementation would still need equivalent protected publication and
  B1-B4 evidence；CDAC contributes the cross-layer join and route-qualified
  decision, not a new hook substrate."
- 核对：该论断针对内核侧 hook（LSM/BPF 位于 VFS），并非声称 framework 入口
  局部检查"不可能"。L 恰好把检查放在 framework 入口本身（provider Binder
  线程），对"单一已知入口+单一对象键"这一情形可不跨层即可获得主体/对象。
  L 不构成对论文论断的反驳，也不复现 B1-B4 的跨层关系证据；以下为机制分析，
  未把 L 表述为已复现 LSM/BPF 实验，也不笼统声称 LSM/BPF 无法实现。
