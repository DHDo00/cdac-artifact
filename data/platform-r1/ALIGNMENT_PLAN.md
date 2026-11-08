# ALIGNMENT_PLAN.md — 三版本 3 boot / 90 请求范围对齐与最小补齐计划（冻结）

冻结时间：2026-11-02T10:02+08:00（Asia/Shanghai）。本计划在启动任何新增 boot 前冻结；
新增批次按本计划顺序执行，不在看结果后按成败挑 boot。计划之外的额外批次与失败一律在索引披露。

## 1. 目标
每版使用各自冻结的 CDAC 制品，3 次独立启动，每 boot 30 个正式请求，每版共 90 个正式请求。
90 是计划正式尝试数，不是预填成功数。实际结果支持时才报告 18 拒止 / 72 允许恢复。
3 boot 是本项目重复验证设计；9 个 boot 分属三个版本/各自制品，不是 9 个独立平台，
三版不合并成 270/270 成功率。

## 2. 已发现可复用批次（冻结前核查，2026-11-02）
| 版本 | 制品 | 已合格 boot | 状态 |
|---|---|---|---|
| A15 | 修正制品 system.img=70c2ab35…（Binder=859a38a7…） | 1 boot（A15CLEAN-R1, cvd-8, 30/30 = 6拒+24允许） | 纳入为 boot1 |
| A16 | R35 C19 冻结制品 system.img=009b68dc… | 1 boot（R35, cvd-35 boot1, 30/30 = 6+24） | 纳入为 boot1 |
| A17 | A17 冻结制品 system.img=ce6dc748… | 2 boots（cvd-73 + cvd-74, 各 30/30 = 6+24） | 纳入为 boot1/boot2 |

- A15 旧制品（system.img=186ea808…，cvd-7 的 30 请求）为历史结果，单列，不与修正制品合并。
- R36（operation selectivity 48 请求）、R39 M（600 请求大矩阵、不同客户端 APK）均不符合
  "独立冻结的完整 30 请求 R35 批次" 标准，排除；不得从大样本事后挑 30 行。
- 未发现 A17 第三 boot → 本轮补 1 boot。

## 3. 差额与冻结执行顺序
| 版本 | 目标 | 已有 | 需新增 | 新增批次 | 实例/ADB | comparison_boot_index |
|---|---|---|---|---|---|---|
| A15 | 3 | 1 | 2 boots / 60 请求 | A15B2 → A15B3 | cvd-95/6614, cvd-96/6615 | 2, 3 |
| A16 | 3 | 1 | 2 boots / 60 请求 | A16B2 → A16B3 | cvd-97/6616, cvd-98/6617 | 2, 3 |
| A17 | 3 | 2 | 1 boot / 30 请求 | A17B3 | cvd-99/6618 | 3 |
| 合计 | 9 | 4 | 5 个正式 boot / 150 个正式请求 | 顺序：A15B2, A15B3, A16B2, A16B3, A17B3 | — | — |

实例/端口在 2026-11-02T10:02 实测全部空闲（adb 空、无 crosvm/launch_cvd 进程、端口无监听），
不与其他任务冲突。原始 batch_id/boot 名称保留，另设 comparison_boot_index=1..3 映射。

## 4. 新增 boot 每版制品（复用冻结镜像/内核/host/APK，不重编译）
- A15B2/B3：aosp15_cleanup_20261030_171705/out_cdac_r1_cleanup_20261030/target/product/vsoc_x86_64_only
  （system.img=70c2ab35…、super.img=36ae6e22…、boot.img=7b0bd5c0…）；host=
  aosp15_cleanup_20261030_171705/out_cdac_r1_cleanup_20261030/host/linux-x86
  （cvd_internal_start=595c988e…，复制 cvd-host_package 到运行盘）。
- A16B2/B3：cdac_esp_endpoint_validation_20261022/19_external_provider_qualification_20261026/artifacts/C19_media
  （system.img=009b68dc…）；host=aosp16/out/host/linux-x86（2021b5e8…）。
- A17B3：aosp17/out_cdac_r1_20261029/target/product/vsoc_x86_64_only
  （system.img=ce6dc748…）；host=aosp17/out_cdac_r1_20261029/host/linux-x86（81216ac5…）。
- 三版共用内核：kernel_openkeychain_dist bzImage=0c0f7e4c… initramfs=0fa2d559…（A16 谱系 6.12.74）。
- 夹具：app_a=b2c52635…、app_b=f2d4da73…、iguardctl_test=493e8e80…、image1=e22785cd…、
  image2=f3d29ccd…（三版同哈希，2026-11-02 实测）。

## 5. 运行隔离与保护
- 运行盘：three_version_r1_3boot_scope_alignment_20261102_100240/a15_boot2 等，
  每 boot 独立 images 副本（reflink/sparse）、新 8GiB userdata、独立 instance/assembly/early_tmp/home。
- 规范镜像只读；launcher 只在其私有副本内工作，不就地修改原 super.img 等输入（前后哈希复核）。
- 每 boot 实测记录 boot_id、时间、fingerprint、release/sdk/REL、uname、Enforcing、
  /dev/iguard_ctl 标签、UID/dev/inode/URI/Provider 进程身份；不照抄历史绑定值。
- 结束：撤规读回 runtime_policy_count=0；仅 stop 本轮实例；核验无残留进程/端口。
- 不构建/不 repo sync/不下载源码；不改 Binder/SELinux/发布接口/选择器/端点；不扩大实验；
  不删文件、不改冻结镜像、不写历史目录；其他任务实例与共享配置链接不动。

## 6. 复用脚本与局部修正
- 复用历史 launch/preflight/matrix/ledger 脚本语义；路径/实例号/端口按本轮改写为
  runs/<boot>/ 下的副本并保留 diff 记录；不修改生产机制。
- A16 本轮新增 boot 亦补充 boot_id 记录与连续 logcat/dmesg 流（R35 原 boot 无 boot_id
  记录属历史缺证，保留，不回填）。
