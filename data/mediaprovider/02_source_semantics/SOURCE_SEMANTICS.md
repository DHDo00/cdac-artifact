# SOURCE_SEMANTICS.md — 第 39 轮 API→Binder→方法标签→Provider→决策点映射（采样前）

结论（依据 R36/R37 源码核对，路径见 R37_R36_EVIDENCE_REVIEW.md §2 引用）：
1. `ContentProviderClient.openFile(uri,"r")` → Binder transaction **14 (openFile)**；
2. `ContentResolver.openFileDescriptor(uri,"w")` → Binder transaction **15 (openAssetFile)**；
3. 两事务都经 `CdacEndpointRegistry` 解析到同一注册入口 **service_id=6 / op_id=501**
   （MediaProvider；registry 的 isProviderFileOpenTransaction 同时接受 txn14/15/23）；
4. 发布到内核的 **operation** = `providerTransactionName()` 映射的方法标签字符串
   `"openFile"` / `"openAssetFile"`（内核 `iguard_match_str` 精确字符串比较）；
5. Provider 侧两标签汇聚到 `MediaProvider.openFileCommon(uri, mode)`，仅 mode 参数
   （"r" vs "w"）不同 → **方法标签选择性 ≠ 同一方法内读写模式选择性**；
6. 运行时实测 join/decision：读 obj_f_flags=0x28000（access=O_RDONLY=0）、
   写 obj_f_flags=0x28042（access=O_RDWR=0x2）；本轮 L 规则 f_flags_mask=0 不使用
   访问标志，读写分离唯一由 operation 枚举承担。

决策点：preview-enforce 位于 6/501 入口、PFD 交付前（deny→real-enforce errno=-13
deny-now，无 PFD；matched=1 reason=<规则 reason>；allow→decision matched=0/VFS_JOIN）。

## 入口/对象真值
- A=com.demo.espafdtest（owner）；B=com.demo.espafdtestb（READ_MEDIA_IMAGES）。
- X/Y 由 A 经 MediaStore.Images insert 创建；能力对象键=FUSE upper 0:45 同 ino；
  backing=/data/media/0/Pictures/*.jpg（254:96）。每 boot 重新解析 dev/ino。
- 真值字节（历史 R35 实测并本轮预检复验）：
  - A→X：911B，sha=e22785cd…，marker_present=true（CDAC25GPSMARK_AAAA）；
  - B→X：911B，redacted sha=96f60e27…，marker_present=false；
  - A→Y：911B，sha=f3d29cc2…，marker_present=true（CDAC25GPSMARK_BBBB）；
  - B→Y：911B，redacted sha=3116065d…，marker_present=false。
