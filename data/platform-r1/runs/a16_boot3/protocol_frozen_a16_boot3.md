# protocol_frozen_a16_boot3.md — A16B3 冻结协议（采样前冻结）

冻结时间：2026-11-02T11:32:36+08:00（早于首次正式请求）。语义/规则形状与 R35 原协议一致，绑定值为本 boot 实测。

## 本 boot 实测绑定
- instance=cvd-98 / ADB 0.0.0.0:6617；boot_id=30f4e9c8-8a25-4142-ad38-074602b08943
- fingerprint=generic/aosp_cf_x86_64_only_phone/vsoc_x86_64_only:Baklava/BP4A.251205.006/eng.test:eng/test-keys
- release=16 sdk=36 Baklava；kernel=6.12.74-android16-6-maybe-dirty；SELinux=Enforcing
- uidA=10121 uidB=10122；A/B=untrusted_app；MediaProvider=mediaprovider_app
- URI_X=content://media/external_primary/images/media/19；URI_Y=content://media/external_primary/images/media/20
- INO_X=2994；INO_Y=3013；App 视图 dev=0:45

## 规则（R35 形状）
- B1：caller_uid=10121 ino=2994 s_dev=45 decision=deny reason=cdac35_r14a
- B2：caller_uid=10122 reason=cdac35_rev
- 装规/撤规 policy_dump 读回；撤规 clear + runtime_policy_count=0 读回。

## 矩阵（30 次）
B0 A→X×3、B→X×3；B1 A→X×3(拒)、B→X×3、A→Y×3；B2 B→X×3(拒)、A→X×3、B→Y×3；
B3 A→X×3、B→X×3。预期 6 拒止+24 允许/恢复。
