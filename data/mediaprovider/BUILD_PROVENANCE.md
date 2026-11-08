# BUILD_PROVENANCE.md — 第 39 轮构建来源与二进制一致性（2026-10-29）

## 1. 使用的冻结构建（复用，不重新构建）
| 制品 | 路径 | sha256 |
|---|---|---|
| system.img | 19_…/artifacts/C19_media/system.img | 009b68dc765c460e08daf39dcadf288667fab8714a0499ad95cb35bd35fd5a48 |
| super.img | 19_…/artifacts/C19_media/super.img | 55f51a092a2ff2161a95f10ff3c900f6441144d8b3da1262682f8c423acf3838 |
| boot.img | 19_…/artifacts/C19_media/boot.img | cd536baa67ee367646f522d16ac5112abf56a16c983321fd6aa7baba1edec763 |
| init_boot.img | 19_…/artifacts/C19_media/init_boot.img | 7bd04994e08c25455865b1e1563fc1c737576325ed599da5555825d97974f160 |
| vendor_boot.img | 19_…/artifacts/C19_media/vendor_boot.img | fe7240cfc9bf8214360dc05a04e7865b0b5c4e5c60b81f3c4c3db62091b4585e |
| vbmeta.img | 19_…/artifacts/C19_media/vbmeta.img | 4138bcbbc30ac3e3428637661f542b36a01a3982defce200e695655db1b0a4e7 |
| product/vendor/system_ext/odm | 19_…/artifacts/C19_media/*.img | 3df08b8c/b8e097ad/4ad16329/98f24195 |
| kernel bzImage | 19_…/artifacts/kernel_openkeychain_dist/bzImage | 0c0f7e4cde1ac2e4745737f271eb4d3434c5b09e4fc2ed5cafcdc2d5e20a653b |
| initramfs.img | 19_…/artifacts/kernel_openkeychain_dist/initramfs.img | 0fa2d5599d311e7d4790f238efd0fd1536b12b27be55ea67ad6214f9ed2aa992 |
| vmlinux | 19_…/artifacts/kernel_openkeychain_dist/vmlinux | c9d0e9ab4575fd82d48880e953f1131b89f6798103f637983470807783229c25 |
| System.map | 19_…/artifacts/kernel_openkeychain_dist/System.map | 0ed0301198347e15ca93efab21731e03f4bea7c62e596eccc9fddd9bbe23fdec |
本轮对 `19_…/artifacts/ARTIFACT_HASHES.txt` 执行 `sha256sum -c` → 全部 OK（14/14）。
主机工具：aosp16/out/host/linux-x86/{launch_cvd,stop_cvd,crosvm}。

## 2. 运行时属性（每个 boot 在 07_results/boot<N>/device_info/ 实测记录）
ro.build.fingerprint、ro.build.version.release、ro.build.version.sdk、uname -r、
/proc/version、getenforce、MediaProvider 版本（dumpsys package com.android.providers.media.module）、
ro.boot.* 等。历史 C19 fingerprint 文件：
`19_…/artifacts/C19_media/build_fingerprint-aosp_cf_x86_64_only_phone.txt`
（运行时值以实测为准，缺失项如实记录，不以版本字符串代替二进制一致性）。

## 3. 与历史构建的关系
- 与 R35/R36 完全相同（同一 C19_media 镜像 + kernel_openkeychain_dist 内核），
  不重新编译；二进制哈希复验一致，因此不是“相同版本字符串”。
- 源码构建树=aosp16（本轮零改动）；策略工具 iguardctl_test
  sha=493e8e80db4598d669509482f20deb7a7d2ce3d31d983211dd4cbbdc049d7b08。
- A15/A17/R38 及其它任务构建不参与本轮。
