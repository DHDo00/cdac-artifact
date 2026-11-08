# protocol_frozen_a15_boot3.md — A15B3 冻结协议（采样前冻结）

冻结时间：2026-11-02T11:07:23+08:00（早于首次正式请求）。语义/规则形状与 A15 修正版原协议一致，绑定值为本 boot 实测。

## 本 boot 实测绑定
- instance=cvd-3 / ADB 0.0.0.0:6522；boot_id=9c9530e6-ec5d-43cf-b6d8-fb1521cead63
- fingerprint=generic/aosp_cf_x86_64_only_phone/vsoc_x86_64_only:15/BP1A.250505.005.D1.cf1ab5d6/eng.test:userdebug/test-keys
- release=15 sdk=35 REL；kernel=6.12.74-android16-6-maybe-dirty；SELinux=Enforcing
- /dev/iguard_ctl crw-rw-rw- u:object_r:iguard_ctl_device:s0
- uidA=10115 uidB=10116；A/B=untrusted_app；MediaProvider=mediaprovider_app
- URI_X=content://media/external_primary/images/media/1000000015；URI_Y=content://media/external_primary/images/media/1000000016
- BACK_X=/data/media/0/Pictures/image1.jpg INO_X=3338；BACK_Y=…/image2.jpg INO_Y=3364
- App 视图 dev=0:46（SDEV_X=46）
- X 原字节 e22785cd…；B redacted 96f60e…（预检实测）

## 规则
- B1 R14A：service_id=6 op_id=501 caller_uid=10115 operation=openFile ino=3338 s_dev=46
  i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason=a15cdac_r14a
- B2 R_rev：同上 caller_uid=10116，reason=a15cdac_rev
- 装规/撤规 policy_dump 读回；撤规 clear + runtime_policy_count=0 读回。

## 矩阵（30 次）
B0 A→X×3、B→X×3；B1 A→X×3(拒)、B→X×3、A→Y×3；B2 B→X×3(拒)、A→X×3、B→Y×3；
B3 A→X×3、B→X×3。预期 6 拒止+24 允许/恢复。

## 判定/日志
同 PROTOCOL_FROZEN.md（六判据、连续流、唯一 label、失败/重试/无效全记账、结束清规、仅停本轮实例）。
