# MISSING_ITEMS.md — 第 39 轮缺失项登记

2. MediaProvider 版本：dumpsys versionName=Baklava（运行时版本字符串）；
   APEX 精确构建来源哈希未在本轮重建，缺失项如实记录，不以版本字符串代替二进制一致性
   （内核/镜像的二进制哈希已逐项复验，见 BUILD_PROVENANCE.md）。
3. 内核构建→vmlinux 的源码编译哈希：沿用 R37 已登记的缺口（vmlinux/iguard_ctl.ko
   文本级对应有据，但无历史构建源码哈希）；本轮不重新构建，缺口保留。
4. 未记录逐请求 scontext：/proc/<pid>/attr/current 为采样时刻域证据（setup 与 end 各一次），
   与历史能力一致，无逐条写请求的 scontext 观测；如实保留限制。
