# MISSING_AND_LIMITATIONS.md — 缺证与限制

## 1. 本轮新增运行缺证
- A15B3：矩阵期间 debugfs 挂载丢失 → policy_dump debugfs 快照为空；以内核
  iguard_ctx policy_op add/clear 全字段日志（logcat 连续流）+ 结束重挂载读回
  runtime_policy_count=0 + 计数器 0→3→6 补偿；仍记为部分记录。
- 无逐写 scontext：域身份为采样时点证据（/proc/<pid>/attr/current），不升级为
  每次 write 的域证据（沿用原协议限制）。
- A16 新增 boot 的 boot_id 已记录（be17e2f6…）；R35 原 boot 无 boot_id 记录（历史缺证，保留）。

## 2. 三版本范围限制（保留原口径）
- A15 原生 6.6 内核未做 CDAC 回移；A17 未做任意内核兼容验证；三版共用
  kernel_openkeychain_dist（6.12.74 A16 谱系）。
- 只支持 MediaProvider txn14 openFile→6/501 单路线 + 指定组合的 caller 选择性、
  主体反转、撤规恢复；不覆盖其余端点/perf/origin 跨跳/全部 B1–B4 运行条件。
- 公开 API 只限被核实调用 ContentProviderClient.openFile(uri,"r")；签名不变不扩展为
  全部 API/CTS/OEM/内核兼容。
- 内核精确源码树 SOURCE_MISSING（制品级复用；不写内核源码 100% 复建）。

## 3. 诊断与静态结论限制
- 4/301 诊断 = su 域两进程夹具、UID0；不是 MediaProvider 执法路线；Error-after-recovery
  未建立；raw transact ok ≠ reply 无业务异常。
- E6/E7/E8：MediaProvider 侧为源码+配置链结论（observer==null 未逐 boot 运行时采样；
  trace tag 无全 boot 运行时采样）；system_server 窗口 UNKNOWN_BOUNDED。
- A16/A17 仅源码对照，不写成三版都做过异常运行验证。
- 20/23 为源码资格结果；不写成运行成功数；GraphicsStats 三路径宿主 system_server
  不在本轮 MediaProvider R1 运行范围（但在论文范围）。

## 4. 成本/统计限制
- 人工主动时间 UNMEASURED；墙钟/构建等待/guest 运行不改成人时。
- 4/5 文件级复用 ≠ 系统 80%；Binder 不在分母；无行级复用率。
- 3 boot 是项目重复验证设计，不是统计充分性通用门槛；9 boot 不合并为 270/270。

## 5. 本轮明确不做（按任务书）
- 不操作 Overleaf、不改论文/TeX/bib/图、不编译论文/不生成 PDF。
- 不构建 Android/framework/kernel/APK、不 repo sync、不下载源码。
- 不改 Binder/SELinux/发布接口/选择器/端点/原生授权模型。
- 不删除文件、不改冻结镜像、不写历史运行目录/归档。
