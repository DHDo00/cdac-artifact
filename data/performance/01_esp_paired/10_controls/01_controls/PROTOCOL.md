# 10_controls 协议 — C1 撤规恢复 / C2 调用者反转 / C3 原生拒绝保持（2026-10-23）

沿用已验证的 ESP 非截断写路径（openAssetFile txn15 / mode "w" / SAF 持久 rw grant）。
UID 全部动态查询，不硬编码。测试文件 X.bin 预先存在（14 字节已知内容）。
规则 v2：service_id=5 op_id=401 operation=openAssetFile ino=<X> s_dev=<X 254:96 十进制>
i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 decision=deny。

## C1 撤规恢复
1. 记录 X 初态（S0 快照）。
2. 安装 A+X deny 规则 → A→X 请求 → 期望真实拒止（FNF/errno=-13 deny-now），
   记录规则命中、拒止、无交付、X 状态不变。
3. policy clear → policy_dump 确认 0 条 → A→X 请求 → 期望 WRITE_OK 且返回能力
   实际可用（PFD 写入成功 + 文件内容/大小变化 + 关闭回调），记录交付证据。
4. 恢复 X 初态（记录夹具操作）。

## C2 调用者策略反转（≠撤规、≠deny→allow）
1. 规则 caller_uid 从 A 改为 B，对象/操作条件不变（ino=X、f_flags 0x1）。
2. B→X 请求 → 期望真实拒止（B 不再命中"允许"路径）。
3. A→X 请求（规则仍在）→ 期望 WRITE_OK（A 不再命中 deny 规则）。
4. policy clear；恢复 X 初态。分别记录两次请求的 matched/caller_uid/交付/文件状态。

## C3 原生拒绝保持
- 原生授权失败：App A 打开其未持有 grant 的树 `primary:espafd_tree_b/XN.bin`
  （该树仅授予 B），预期 SecurityException（原生授权拒绝）。
- 对照态：
  (a) CDAC 机制开启、无规则；
  (b) 判定路径消融（debugfs ablate_disable_runtime=1 + ablate_disable_ctx=1；
      如实说明：仅消融运行时规则查找与调用者上下文发布，静态规则与全部钩子、
      日志仍在——这不是完整"关闭"，是可用开关的真实范围）。
- 断言：两种状态下均保持原生 SecurityException；CDAC 未将原生拒绝改为放行。
- 每个子序列一次，失败/重试单列；不扩大正式样本。
