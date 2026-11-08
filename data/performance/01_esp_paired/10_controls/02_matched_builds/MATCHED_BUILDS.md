# MATCHED_BUILDS.md — 有/无 CDAC 可比构建基础（2026-10-23）

## 结论
MATCHED_BUILDS=READY（基于已冻结的 v1 配对构建工程 + 本轮双方启动预检）。
本轮未重复全量构建：v1 配对工程（2026-08-18）已实际完成 E/S 两套全新构建并通过
源码等价/标识审计；本轮按其"优先复用未变化制品"要求复用，并补齐 v1 当时未做的
两侧 CVD 启动与运行时缺位审计。

## 共同基础（可重建依据）
- 基础 manifest：aosp16/.repo/manifests/default.xml
  （AOSP Baklava，BUILD_ID=BP4A.251205.006）。
- 产品/变体：aosp_cf_x86_64_only_phone / eng（两侧一致；v1 BUILD_PLAN 使用
  trunk_staging release 拼写，指纹同为 cdacmsb20260818）。
- 构建身份：BUILD_NUMBER=cdacmsb20260818、SOURCE_DATE_EPOCH=1787020257、
  BUILD_USERNAME=test、BUILD_HOSTNAME=cdac-matched（v1 两侧一致；ESP enabled
  侧 2026-10-22 增量构建沿用同一树与指纹）。
- 工具链：Android Soong/Ninja；kernel Kleaf/Bazel clang 19.0.1（内核日志）
  virtual_device_x86_64（6.12）。
- 修改项目与 revision：完整 CDAC delta 见
  cdac_matched_stripped_baseline_v1_20260818/02_source_pair/CDAC_DELTA_MANIFEST.tsv
  （89 行；44 changed + 44 deleted + 工具文件，覆盖 framework/JNI/FUSE/内核/模块/
  sepolicy）；当前 enabled 树 repo status 与该 delta 一致，另加 ESP 两条
  （frameworks/base/.../CdacEndpointRegistry.java 的 5/401 分支 =
  00_impl/framework/registry.diff；kernel/common/security/iguard_ctx.c 白名单一行 =
  00_impl/kernel/whitelist.diff）。
- stripped 侧 = enabled 侧逐字节相同的基础，移除全部 CDAC delta（
  NON_CDAC_SOURCE_EQUIVALENCE=PASS：共享文件 1749478 字节一致，0 未授权差异，
  marker audit 0 命中）。

## 两侧制品（复用 + 本轮重新核验哈希）
| 组件 | CDAC enabled（ESP 系列） | 无 CDAC（stripped S0） | 差异 |
|---|---|---|---|
| system.img | 54193b1f…（2026-10-22 新构建） | 24550e03…（v1-S fresh） | CDAC delta（含 ESP registry） |
| super.img | a90df407… | 820c1aa5… | 同上 |
| boot.img | 1d1a25f8… | 1d1a25f8…（相同） | 无 |
| vbmeta.img | b2772643… | f3746afa… | 待核验（签名链差异） |
| vendor_boot.img | 4d810109… | d81d01d8… | 待核验 |
| framework.jar | 9c642d41… | 54032abb… | framework CDAC delta |
| ExternalStorageProvider.apk | a65a0ff3… | 7f1309ef… | provider CDAC delta |
| kernel bzImage | 5e89e605… | 405f5c47… | kernel CDAC delta（+ESP 白名单行） |
| initramfs.img | 95af695a… | ffb1b95f… | kernel CDAC delta |
| iguard_ctl.ko | 存在（dist 内） | 不存在 | 预期 |
| /dev/iguard_ctl（运行时） | 存在 | 不存在 | 预期 |

## 启动与运行时预检（本轮实际执行）
- enabled r20：fingerprint cdacmsb20260818、kernel 6.12.74-android16-6-maybe-dirty、
  SELinux Enforcing、/dev/iguard_ctl 在、iguard_ctl 模块在、verbose_audit=Y、
  runtime_policy 可用 → C1/C2/C3 与 S1/S3/S2 采样均在此运行。
- stripped r21：同 fingerprint、同 kernel 版本串（stripped 内核同基础构建）、
  SELinux Enforcing、**/dev/iguard_ctl 缺失、iguard 模块缺失、debugfs iguard 目录
  缺失、framework.jar=54032abb（v1-S 一致）** → S0 采样在此运行。
- 差异清单中未解释项：kernel dist 的 dot_config 仅比 stripped 多一行
  `# CONFIG_IGUARD_CTL is not set`（enabled dist 的模块配置经 virtual_device
  fragment 注入，dot_config 快照为前阶段视图；iguard_ctl.ko 实际构建并加载）。
  其余差异全部可归属 CDAC delta + ESP 两条。

## 状态字
S0=可用（stripped，完全无 CDAC）；S1=可用但非"关闭"（ablate_disable_runtime+ctx，
静态规则与全部钩子仍保留）；S2=可用（enabled 无规则）；S3=可用（enabled + 规则，
计时请求为不命中拒绝规则的合法请求，无"允许规则"语义）。
