# 制品来源与哈希（第 21 轮复用清单，2026-10-26）

本轮**不重建平台**，只复用已验证制品；只读引用，不写回来源目录。

## 部署输入（已验证 ESP 5/401 直接写路线，与 round-11 PERF_PROTOCOL 相同组合）
来源目录：`cdac_esp_endpoint_validation_20261022/02_build/android_matchedimg_newsystem/`
（部署时以实际文件哈希为准，逐项记录到 boot 运行时目录）：

| 文件 | sha256（2026-10-26 实测） | 说明 |
|---|---|---|
| system.img | 54193b1fb6319ffa29ae221bdec57030f69222f187c0581b17e8f3c120671e6d | 含 ESP 5/401 registry（round-6） |
| super.img  | a90df40720bb8bf31c964abb54c2f8906ce705f51d3d00da9c6c4708b0579ef6 | 动态分区，包 system 54193b1f |
| boot.img   | 1d1a25f8124ade7b671a349c2e4877c5cc65a30bd45de97aa33eb12d44ae4adc | matched 基线 boot 链 |
| init_boot.img | e3b6e1f5e08e6470d37e24043a980369c10902f49929fa0fc1049c034b42f6b2 | |
| vendor_boot.img | 4d8101099d3d8cb9c6474fd51373baae489d0fa52832a69fb960ed2bc9ed2f18 | |
| vbmeta.img  | b2772643a8e4d0037674e210bbd46c080f771a328e872636e8c27ed4186357c0 | |
| vbmeta_system.img | 4c52399ce09784bfd1327dd266491e1495c04fcb988fdbe60e290d630cd4ac06 | |

内核：`02_build/kernel_esp_dist/`
| bzImage | 5e89e6050f38ae97ee41bdacb92d7eaf63b51ba8cfa08ce2619f601d597010b9 |
| initramfs.img | 95af695af3065fcc0462bbba695253fcec11a1c9e19a9402f974817c6d41be17 |
（含 (5,401) 白名单；iguard_ctl 随 dist）

## 工具与夹具（已验证二进制，复用）
| 项 | 路径 | sha256 |
|---|---|---|
| 计时 APK | 10_controls…/03_timing_app/build/esp-timing-signed.apk | 8ca8cd211f764d1f7875076b23ba5c46be545a740b51246dbbe80ec2f9a6ebe2 |
| App A | 07_side_effect_order/fixtures/app_diag/build/espafdtest-signed.apk | 000f1bb519b1d8a16e2aaea1ba815e4244d21aa49e1e3abd693506bdf6ca8aff |
| App B | 01_fixtures/app_b/build/espafdtest-signed.apk | c0139af277055abceb4ae0f2ec9d0de583b4b39890042f004107056b62fdd1e0 |
| 规则工具 | cdac_esp_afd_wrapper_runtime_validation_20261022/01_device_preflight/iguardctl_test | 493e8e80db4598d669509482f20deb7a7d2ce3d31d983211dd4cbbdc049d7b08 |

## 路线与协议复用
- 路线：ESP 5/401 openDocument 写分支（R-ESP-P-ESP-004-004），round-6
  `06_final/FINAL_REPORT.md` 12/12 PASS；round-11 `03_protocol_frozen/PERF_PROTOCOL.md`
  的 LOG_OFF 配置与计时 APK 用法被本轮冻结协议沿用。
- 计时边界：沿用 round-10/11 的 `com.demo.esptiming` elapsedRealtimeNanos
  （openFileDescriptor 调用前 → PFD 返回/异常），能力验证/写/close/CSV 在区间外。

## 明确不复用的口径
- 旧 RQ4“额外一次查询”对照（S10 路线，A/B/C/D 臂）不是规模实验，不并入。
- round-12 的旧制品差值仅作历史上下文，**不与本轮差值拼接计算总开销**。
- 本轮 N=0 是**同一 CDAC 制品的空规则参考**，不是无 CDAC 基线。
