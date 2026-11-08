# MECH_COMPARE_PROTOCOL.md — N/L/C 同场景机制比较（2026-10-25，计数前冻结）

## 共同目标
在原生授权本来允许这些请求的前提下，额外拒绝 A 获取 X 的指定写能力，同时保留
A→Y、B→X。这是同一附加授权目标的机制比较；原生系统未实现该附加策略不是漏洞。

## 三侧定义
- N：匹配原生 Android（v1 stripped 制品：system 24550e03…/boot 1d1a25f8…/
  super 820c1aa5… + stripped kernel 405f5c47…/initramfs ffb1b95f…），无 CDAC、
  无新增局部检查。如实记录其无附加策略执行能力。
- L：同一原生基础 + 仅 ExternalStorageProvider 的局部写检查补丁
  （L_patch/externalstorage_L.diff）；策略=persist.lab.lpolicy
  "uid|documentId"（空=关闭）；在 openDocument 打开任何资源前用
  Binder.getCallingUid()（可信调用者，身份未清除）与 provider 校验的 documentId
  做匹配；拒止抛 FileNotFoundException 并 Log.i(L_POLICY_DENY)；不调用 CDAC 的
  上下文/设备接口/内核决策。构建于独立提取的 stripped 源码树。
- C：现有完整 CDAC enabled（system 54193b1f…/super a90df407… + kernel_esp
  5e89e605…），v2 规则 service_id=5 op_id=401 caller_uid=A operation=
  openAssetFile ino=X s_dev=254:96 f_flags_mask=0x3 f_flags_value=0x1 deny。

## 夹具与输入
- A=com.demo.espafdtest、B=com.demo.espafdtestb、计时/观测 APK esp-timing-signed
  8ca8cd21…；SAF 持久 rw grant；X.bin/Y.bin 14 字节已知内容；写模式 "w"（主对照，
  既有非截断）；截断诊断用 "wt"。UID/对象身份每 boot 动态核实。

## 核心序列（每机制 3 次，开发尝试单列不计入）
1. 无新增拒绝策略，A→X（期望允许且能力可用）；
2. 策略针对 A＋X，A→X（L/C 期望拒止；N 无此能力，记录 N/A 与证据）；
3. 同一策略下 A→Y（期望允许）；
4. 同一策略下 B→X（期望允许）。

## L/C 追加最小序列（各 1 次）
5. 撤规后 A→X 恢复；
6. 策略主体 A→B：B→X 拒止、A→X 允许；
7. 原生拒绝请求（A 打开无 grant 的 espafd_tree_b/XN.bin）保持 SecurityException。

## 文件副作用诊断（每机制 1 条有合法对照）
- 合法对照：既有文件 "wt" 无策略 → 成功并截断（记录 S0/S1/S2）。
- 策略请求：策略针对 A＋X 时 A→X "wt" → 分别记录能力交付(A)与文件变化(B)。
- C 保留既有事实（能力阻断但文件已截断）；L 在打开前拒止，预期不截断——如实记录。

## 证据与通过标准
- 每步记录：App 返回结果/异常、能力是否实际可用（PFD 写入+fstat）、文件
  S0/S1/S2（exists/dev:ino/size/sha/mtime/ctime）、规则/策略读回、L 的
  L_POLICY_DENY 日志、C 的 quiet_counters/decision 记录（LOG_OFF 配置同 11 轮）。
- 允许条件=WRITE_OK 且内容变化；拒绝条件=负 errno/异常且无目标能力交付；
  对象/调用者控制不得误杀。失败与重试保留 ledger，不隐藏。

## 计数与顺序
- 每机制同一 boot 内按 1→4 顺序；3 次重复按固定顺序跑完；策略安装/撤除在各
  重复间按协议执行并记录。N/L/C 各独立 boot；boot 顺序 N→L→C 固定（机制比较
  非性能采样；构建完成后再启动）。
- 本协议冻结于计数开始前；开发/调试尝试单列。
