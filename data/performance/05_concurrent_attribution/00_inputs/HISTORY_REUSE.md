# HISTORY_REUSE.md — 第 26 轮历史证据复用（2026-10-27）

## 复用的已验证制品与路线（只读）
- ESP 5/401 openDocument 写分支（R-ESP-P-ESP-004-004），"w" 非截断模式
  （O_WRONLY|O_CREAT|O_LARGEFILE，join f_flags=0x8041 实测）。
- 镜像 `02_build/android_matchedimg_newsystem/` + 内核 `02_build/kernel_esp_dist/`
  （sha256 与第 21/24 轮一致，本轮复测记录见 FREEZE_MANIFEST）。
- 规则工具 iguardctl_test（493e8e80…）。
- 第 23 轮 COUNTER_SEMANTICS_AUDIT 计数口径；第 24 轮逐请求采集方法
  （framework ENTER/EXIT/PUBLISH + kernel PUSH/POP/decision/real-enforce 按 seq 关联）。

## 严格对应检查（不重复）
- 历史无"多主体真实并发下的选择性执法/主体-对象-结果关联"实验：
  - 第 24 轮只测异常后**同线程顺序复用**（明确不覆盖并发）；
  - 第 10/21 轮有串行时序与规模测试，非并发归属；
  - 第 22/25 轮为单请求分支诊断。
  → 本轮并发归属为新证据，不复用任何历史并发结论。
- 健康检查与第 21/24 轮同构，但对象为本轮自建 ccx/ccy、目标是并发前置条件，
  属本轮必要前置，不计为重复覆盖。

## 本轮夹具调整（最小，保存源码/构建命令/APK 哈希）
- App A/B 在原 write 动作上新增 `offset`（Os.lseek/Os.write，默认 0），
  供 A/Y 与 B/Y 并发写同一文件时使用预先划定的不同偏移（A=0，B=4096），
  避免夹具自身数据竞争。
- App A/B 新增 `wave` 动作：独立工作线程 + 动态 BroadcastReceiver 接收
  `com.demo.cdac26.RELEASE` + CountDownLatch 门闩，实现客户端 ready/release 协调。
  协调只在客户端；未改 Provider/内核等待或身份/判定过程。
- 源 diff：01_fixtures/app_{a,b}/MainActivity.patch；构建命令 build_apk.sh；
  APK sha256 见 FREEZE_MANIFEST。

## 明确不复用/不合并
- 不把第 24 轮"同线程顺序复用"结论外推为并发正确性。
- 不把历史 boot 的 server_tid/ino/UID 用于本轮关联（每 boot 动态）。
- 不把 rule_match_total 当 file-open 命中计数；不用全局 push/pop 平衡单独
  证明逐请求归属。
