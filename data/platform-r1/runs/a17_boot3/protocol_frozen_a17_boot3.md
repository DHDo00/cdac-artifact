# protocol_frozen_a17_boot3.md — A17B3 冻结协议（采样前冻结）

冻结时间：2026-11-02T11:40:28+08:00（早于首次正式请求）。语义/规则形状与 A17 原协议一致，绑定值为本 boot 实测。

## 本 boot 实测绑定
- instance=cvd-99 / ADB 0.0.0.0:6618；boot_id=9b1a4228-0745-4391-9579-a680a919ab62
- fingerprint=generic/aosp_cf_x86_64_only_phone/vsoc_x86_64_only:17/CP2A.260605.016/eng.test:userdebug/test-keys
- release=17 sdk=37；kernel=6.12.74-android16-6-maybe-dirty；SELinux=Enforcing
- uidA=10122 uidB=10123；A/B=untrusted_app；MediaProvider=mediaprovider_app
- URI_X=content://media/external_primary/images/media/19；URI_Y=content://media/external_primary/images/media/20
- INO_X=3544；INO_Y=3569；App 视图 dev=0:45

## 规则（沿用 A17 reason 文本）
- B1：caller_uid=10122 ino=3544 s_dev=45 decision=deny reason=cdac35_r14a
- B2：caller_uid=10123 reason=cdac35_rev
- 装规/撤规 policy_dump 读回；撤规 clear + runtime_policy_count=0 读回。

## 矩阵（30 次）
B0 A→X×3、B→X×3；B1 A→X×3(拒)、B→X×3、A→Y×3；B2 B→X×3(拒)、A→X×3、B→Y×3；
B3 A→X×3、B→X×3。预期 6 拒止+24 允许/恢复。
