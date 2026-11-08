# protocol_frozen_a16_boot2.md — A16B2 冻结协议（采样前冻结）

冻结时间：2026-11-02T11:24:21+08:00（早于首次正式请求）。语义/规则形状与 R35 原协议一致，绑定值为本 boot 实测。

## 本 boot 实测绑定
- instance=cvd-97 / ADB 0.0.0.0:6616；boot_id=be17e2f6-8d1c-4b7c-9edd-ff32e95f04f8
- fingerprint=generic/aosp_cf_x86_64_only_phone/vsoc_x86_64_only:Baklava/BP4A.251205.006/eng.test:eng/test-keys
- release=16 sdk=36 Baklava；kernel=6.12.74-android16-6-maybe-dirty；SELinux=Enforcing
- uidA=10121 uidB=10122；A/B=untrusted_app；MediaProvider=mediaprovider_app
- URI_X=content://media/external_primary/images/media/19；URI_Y=content://media/external_primary/images/media/20
- INO_X=2967；INO_Y=2990；App 视图 dev=0:45
- X 原字节 e22785cd…；B redacted 96f60e…（预检实测）

## 规则（R35 形状）
- B1：service_id=6 op_id=501 caller_uid=10121 operation=openFile ino=2967 s_dev=45
  i_mode=00 f_flags_mask=0x3 f_flags_value=0x0 decision=deny reason=cdac35_r14a
- B2：caller_uid=10122，reason=cdac35_rev
- 装规/撤规 policy_dump 读回；撤规 clear + runtime_policy_count=0 读回。

## 矩阵（30 次）
B0 A→X×3、B→X×3；B1 A→X×3(拒)、B→X×3、A→Y×3；B2 B→X×3(拒)、A→X×3、B→Y×3；
B3 A→X×3、B→X×3。预期 6 拒止+24 允许/恢复。
