# RESULTS_COMPARE.md — N/L/C 同场景机制比较结果（2026-10-25，运行时）

制品：N'=nprime_artifacts（system da1267e3…/super 170c4b41…/boot 1d1a25f8…，
provider 7f1309ef…）；L=l_artifacts（system 253261f2…/super 95c1a228…/boot
1d1a25f8…，provider 7bd02b0b…）；C=enabled 配对（system 54193b1f…/super
a90df407…/boot 1d1a25f8…+kernel_esp 5e89e605…）。N'/L 内核同为 stripped
405f5c47…。N' vs L system 树仅 provider APK 与 build.prop 两文件不同（已核）。

## 核心序列（每机制 3 次；结果一致 3/3）
| 条件 | N（原生，无策略面） | L（局部检查） | C（完整 CDAC） |
|---|---|---|---|
| 1 无策略 A→X | WRITE_OK 3/3 | WRITE_OK 3/3 | WRITE_OK 3/3 |
| 2 策略 A+X，A→X | 原生放行 3/3（无策略面，记录 N/A） | WRITE_FAIL FNF 3/3（L_POLICY_DENY 日志） | WRITE_FAIL FNF 3/3（deny-now） |
| 3 同策略 A→Y | WRITE_OK 3/3 | WRITE_OK 3/3 | WRITE_OK 3/3 |
| 4 同策略 B→X | WRITE_OK 3/3 | WRITE_OK 3/3 | WRITE_OK 3/3 |

## L/C 最小序列（各 1 次）
| 项 | L | C |
|---|---|---|
| 撤规后 A→X 恢复 | WRITE_OK | WRITE_OK |
| 主体 A→B：B→X | WRITE_FAIL FNF | WRITE_FAIL FNF |
| 主体 A→B：A→X | WRITE_OK | WRITE_OK |
| 原生拒绝保持（A 无 grant 打开 tree_b/XN） | SecurityException | SecurityException |

## 文件副作用（既有文件 "wt"，各有合法对照）
| 机制 | 对照(无策略) | 策略请求 | A（交付阻断） | B（文件变化） |
|---|---|---|---|---|
| N | 16→3 截断+写 | n/a（无策略） | n/a | n/a |
| L | 16→3 截断+写 | FNF；D2 16B sha/mtime/ctime 不变 | true | **false（拒止先于打开，无截断）** |
| C | 16→3 截断+写 | FNF；D2 16→0 空 sha，mtime/ctime 变 | true | **true（截断先于拒止，复现既有事实）** |

## 三侧对照表（接入维度）
| 维度 | N | L | C |
|---|---|---|---|
| 身份信息 | 无附加策略 | Binder.getCallingUid()（provider 入口，身份未清除） | 统一 Binder 钩子 caller + VFS join |
| 对象信息 | — | provider documentId（provider 自身键） | backing dev/ino（B2 权威对象证据） |
| 检查位置 | — | openDocument 入口（打开前） | backing do_dentry_open 后、交付前 |
| 修改范围 | 0 | 1 文件 ~45 行 | 89 行 delta + ESP 2 条（framework/JNI/kernel/模块/sepolicy） |
| 新路径适配 | — | 每入口一段检查 | 注册端点+一条规则 |
| 策略配置 | — | setprop | iguardctl add/clear |
| 清理 | — | setprop "" | policy clear（计数器可核） |

## 行为差异与来源
- 直接路径三者存在差异：N 无附加策略；L/C 都能在目标条件拒绝、保留合法
  条件，能力不可用（FNF）。
- 差异来源=检查位置与对象信息：L 在 provider 入口用 documentId；C 在 backing
  打开后用 dev/ino。位置差异带来截断副作用差异（L 无、C 有）。
- 主体信息二者都取自信任调用者（L=Binder.getCallingUid；C=Binder 钩子发布），
  该路径两者等价；差别在于 C 的发布是跨层统一机制、L 是入口局部调用。

## 判断
- 当前直接路径（已知入口、同进程解析对象、无转交）：L 已足够实现该附加策略，
  且在该路径的截断副作用上更早拒绝（B=false）。C 无行为优势。
- C 的实际增量（本比较可陈述）：跨层对象证据（backing dev/ino，B2）、
  统一路由化决策/运行时策略无需改代码、可跨 provider/入口复用、关系/生命周期
  计数。这些在本单一路径未显现行为收益；更大范围或复杂转交路径的收益
  **尚无本实验实测证据**（B3/B4 与多入口只在机制层面，不冒充复现）。
- 论文 VI 关于 LSM/BPF 的表述针对内核侧 hook（无 Binder caller/框架入口），
  与 L（把检查放在框架入口）不冲突；L 不构成对论文论断的反驳，也不声称
  复现 LSM/BPF。以上为机制分析。
