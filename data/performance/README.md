# RQ3 性能证据 — 服务器检索、离线复算与打包回传包

打包时间：2026-10-29（Asia/Shanghai）。性质：**只找回并核对已有实验**。
本包未启动/重启 CVD，未构建，未刷机，未修改开关/策略，未修改论文；
所有脚本为纯离线统计，只读原始归档并在本包副本上运行。

任务书所称“RQ3 性能”在论文中的真实编号是 **RQ4（Application-Visible Latency）**
（RQ3=转发边界 10/10）。本包锚点对应论文
`evaluation_completed.r34b_baseline.tex` 的 “RQ4: Application-Visible
Latency”、“Pristine matched baseline”、“Rule-count scaling” 三段。

## 0. 包内目录

| 目录 | 内容 |
|---|---|
| `01_esp_paired/` | ESP 5/401 openDocument 写配对实验：00_impl_minimal（ESP 两条补丁 diff + AOSP base manifest）、10_controls（构建/控制/计时 APK 源码）、11_perf_paired（协议、16 个有效状态块 CSV、日志诊断、统计、boot 日志）、12_perf_audit（独立重算/勘误、磁盘时间线、N/L/C 机制比较、最小构建证明） |
| `02_settingsprovider_abc/` | 历史 SettingsProvider A/B/C + 独立拒止 D（RQ4 v2 前瞻性能）：预注册协议/随机排程/种子、两 boot 全部科学行+逐 block app.csv、冻结分析与 bootstrap 副本、fig_runtime_cost 两套图及其输入清单 |
| `03_h4_dp/` | H4 DP 性能：RAW_SAMPLES.csv（12000 行）、156 个逐块 CSV、块序/配对/统计与 CI 输出 |
| `04_rule_count_scaling/` | N∈{0,1,8,32,128} 规则规模：1000 行逐次计时 CSV、每配置规则读回、冻结分析与图 |
| `05_concurrent_attribution/` | ESP 四请求并发归属（无应用侧时延）：ledger/overlap/逐波证据 |
| `06_metric_provenance/` | 35 轮数据口径核验（METRIC_PROVENANCE.csv/md、审稿回复映射、插入草稿） |
| `07_paper_snapshot/` | 当前论文 tex（33 轮 r34b 基线 + NDSS 当前版）供对照，未修改 |
| `recompute/` | 包内可运行的离线复算入口与输出（`bash recompute/run_all.sh`） |
| 根目录 | README.md、SOURCE_INDEX.csv、CLAIM_CHECK.csv、MISSING_ITEMS.md、DENOMINATOR_EXCLUSIONS.csv、SHA256SUMS.txt |

## 1. 核心发现（锚点核对）

### 1.1 ESP 配对（S0/S1/S2/S3，round 11 + 12 独立重算）
- 状态定义（PERF_PROTOCOL.md，正式采集前冻结）：
  - **S0**：完全无 CDAC——v1-S stripped fresh 构建（源码等价审计：共享文件
    1,749,478 字节逐字节一致、0 未授权差异、CDAC marker 0 命中），运行时无
    /dev/iguard_ctl、无 iguard 模块、无 debugfs iguard。不是同工件内关开关。
  - **S1**：enabled + `ablate_disable_runtime=1` + `ablate_disable_ctx=1` + policy
    clear——仅消融**运行时规则查找**与**调用者上下文发布**；静态规则与全部钩子保留，
    只作组成解释，不作主部署成本。
  - **S2**：enabled 完整、policy clear（无规则）。
  - **S3**：enabled 完整 + A+X deny 规则（caller=10122, ino=X, s_dev=254:96,
    f_flags_mask=0x3/f_flags_value=0x1）；计时应用 uid=10121≠A，请求为
    **合法且不命中拒绝规则**的写（不是“命中允许规则”）。
- 4 对 boot、交替侧序（P1 S0 先，P2 enabled 先，P3 S0 先，P4 enabled 先）；
  enabled 内状态顺序固定 S1,S2,S3 / S3,S1,S2 / S2,S3,S1 / S1,S3,S2（16 块
  meta 时间戳逐块核实一致）。
- 每状态每 boot：预热 20 + 记录 200；16 块全部 n=200、invalid=0；每状态合计
  800 条有效记录。p4 首次 SAF 授权失败 boot（3×200 SecurityException）单独保留、
  由同顺序重试 boot 补齐（原始行未保留，仅 FAILURE_RECORD.txt，见 MISSING_ITEMS #3）。
- 复算（type-7 分位，逐位一致；原 round-11 analyze.py 在包内副本重放字节级一致）：
  - **S2−S0**：逐 boot 中位数差 2.225950 / 3.961812 / 2.161134 / 2.550305 ms；
    **均值 2.724800 ms**；范围（min–max，非 CI）2.161–3.962 ms；
    配对比值 1.6691/2.4638/1.6910/1.8406，**均值 1.916129**（比值之均值 1.893765）。
  - **S3−S0**：1.886152 / 3.024278 / 2.424583 / 1.714802 ms；**均值 2.262454 ms**；
    范围 1.715–3.024 ms；配对比值均值 **1.756203**（比值之均值 1.742110）。
  - pooled（合并 800 请求，仅描述性，**不替代配对估计**）：S0/S1/S2/S3 中位数
    3.045218 / 6.237511 / 5.735940 / 5.385918 ms；P95 10.819647 / 13.423468 /
    14.028540 / 14.614968 ms。
  - 与任务书锚点差异：中位数锚点（3.05/6.24/5.74/5.39）是两位小数四舍五入，
    与精确值一致；**P95 锚点 10.80/13.40/14.00/14.60 与精确值不符**（两位小数应为
    10.82/13.42/14.03/14.61）——凡引用处需更正（见 MISSING_ITEMS #19）。
  - S1 未比 S2 快（组成解释：剩余成本主要在 enabled 共有的钩子/审计，而非运行时
    规则查找或调用者上下文发布）；S2 与 S3 在本精度未分辨（3/4 对 S3≤S2，不表述
    为零成本）。4 对无正式 CI，不把差值范围标为 CI。
- 日志诊断（同 boot、同 S2、ON/OFF/OFF/ON 四块×30）：
  - LOG_ON 块中位数 20.426 / 23.427 ms；LOG_OFF 6.213 / 7.022 ms
    （历史文本写 20.8–23.6 / 6.3–7.0，精确值见 recompute，MISSING_ITEMS #20）。
  - 控制台量 ON≈1.39–1.40 MB/30 请求 → OFF≈43.9–44.0 KB/30 请求，
    **下降 96.85% / 96.87%**。跨批次差值不相加分解历史耗时。
- 计时 APK 核查（源码入包）：`SystemClock.elapsedRealtimeNanos`，区间=
  openFileDescriptor 调用前→PFD 返回/异常；写入+fstat 能力验证、close、CSV 序列化、
  夹具恢复均在区间外；mode="w"、14 字节 X.bin、SAF 持久 rw grant；
  esp-timing-signed.apk sha256=8ca8cd21…（S0–S3 同一 APK）。
- boot 身份：host 侧 launch pid/时间 + 每次 fresh-userdata 的 X inode + kernel.log
  哈希可重建；**guest boot_id 未记录**（MISSING_ITEMS #2）。配对映射表：
  `01_esp_paired/11_perf_paired/04_samples/BOOT_STATE_PAIRING_MAP.csv`。

### 1.2 历史 SettingsProvider A/B/C + 独立拒止 D（RQ4 v2）
- 协议/排程/种子齐全（预注册先于任何执行；SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE=0）。
- 两 boot（uuid 62411444-e1c2-488f-9140-cd68dc4608a0 / 6fcb6347-b703-439e-ab21-dbce04a65a78），
  每 boot 50 个随机配对 block × 每 A/B/C 5 次；D 独立 50 block×5；**正式 2000 次
  （A/B/C/D 各 500）、预热 120 次**；0 排除。
- 冻结分析脚本在本包副本**未修改重放，六项输出字节级一致**；独立 stdlib 重算一致：
  - A/B/C pooled 中位数 13.857924 / 16.117391 / 15.872181 ms；
    IQR（type-7 q75−q25）4.058978 / 5.770717 / 5.310286 ms。
  - **B−A**=1.924708 ms，95% 分层整块 percentile bootstrap（10000 reps，seed
    1679099201949269052）CI [1.396098, 2.707998] ms。
  - **C−B**=−0.200872 ms，CI [−0.730023, 0.361999] ms。另有 C−A 1.726082 ms。
  - D 绝对拒止时延 mean/P50/P95 = 13.743391 / 14.165937 / 18.446476 ms
    （独立 schedule/oracle/分母，不计算任何 D 减某臂的开销）。
- 估计量=**每配对 block 内中位数（每臂 5 值）之差的中位数**；bootstrap 按 boot
  分层、整块重采样、不逐请求独立。历史与重算均与任务书锚点一致。
- fig_runtime_cost.pdf（两套变体 + 绘图脚本 + FROZEN_INPUT_REFERENCES.tsv）入包；
  注意它未被任何打包论文 tex 引用（MISSING_ITEMS #21）。

### 1.3 H4 DP（0.252 ms 行）
- RAW_SAMPLES.csv 12000 行重算：pooled P0/P1/P2 中位数 28.618375 / 28.693838 /
  2.437371 ms；40 个会话内配对 block 中位数差的中位数 252025.25 ns=0.25202525 ms；
  相对 P0 block 中位数中位数 28601529 ns 的 0.881160%；块均值差的均值 −27629.103 ns。
- 95% CI：原始 bootstrap 脚本未保留（MISSING_ITEMS #12）。冻结输出
  [−183755.500, 925107.750] ns 保留为权威；用冻结 seed 复算下界逐位一致、上界
  947051.0 ns（+0.022 ms），区间均跨零，结论不变。
- P0=同补丁空策略引用（**不是 pristine/无 CDAC 基线**）；P2=绝对拒止时延。

### 1.4 规则规模 N∈{0,1,8,32,128} 与并发
- 21 轮 06_perf_raw 有**可比较时延记录**（1000 行，2 boot×20 block×5 N×5 记录）。
  逐块配对 T(N)−T(0) 中位数：boot1 −0.492..+0.227 ms，boot2 −3.344..+2.246 ms；
  8 个规模×boot 单元的 bootstrap 均值 CI 全部跨 0（重算与冻结 analysis.json 全等）。
  61/61 正确性步（17 拒止+44 允许/健康/撤规）单独保留，不作性能扫描。
- 26 轮四请求并发**没有应用侧逐请求时延**（ledger 只有服务端 epoch 时间戳）；
  归属 160/160（40 DENY_PASS + 120 ALLOW_PASS）。并发正确性与性能分别报告。

## 2. 复算入口（包内可运行）
```bash
cd rq3_performance_evidence_export_20261029/recompute
bash run_all.sh            # 全部六步，仅依赖 python3（无需 pandas/numpy 亦可跑 1/2/4/5/6；
                           # rq4_abc 会调用冻结脚本，需 pandas/numpy——服务器已具备且
                           # 与冻结分析环境一致 python3.12/pandas2.1.4/numpy1.26.4）
python3 esp_recompute.py       # ESP 主结果 + LOG 诊断
python3 rq4_abc_recompute.py   # A/B/C：冻结脚本重放 + 独立重算
python3 h4_recompute.py        # H4
python3 rulecount_recompute.py # 规则规模
python3 concurrency_check.py   # 并发归属计数
```
结果在 `recompute/outputs/*.txt` / `*.csv`。运行前 SHA256SUMS.txt 可按需校验
（`sha256sum -c SHA256SUMS.txt`）。

## 3. 来源与最小构建证明（按“历史哈希/本轮重算/源码推断/缺失”标记）
- 制品哈希：10 轮 ARTIFACT_PAIR_TSV.tsv（system/super/boot/vbmeta/vendor_boot/
  framework.jar/ExternalStorageProvider.apk/bzImage/initramfs/iguard_ctl.ko 两侧哈希，
  状态 VERIFIED/VERIFIED_IDENTICAL/VERIFIED_RUNTIME）；N'/L/C 三侧哈希在
  12 轮 RESULTS_COMPARE.md 与 04_builds_minimal 的 SHA256SUMS。
- 共同基础：AOSP Baklava BP4A.251205.006，aosp_cf_x86_64_only_phone eng，
  BUILD_NUMBER=cdacmsb20260818；boot.img 两侧字节相同 1d1a25f8…；CDAC delta 清单
  =v1 的 CDAC_DELTA_MANIFEST.tsv（89 行）+ ESP 两条（registry.diff、kernel
  whitelist.diff，见 10 轮 00_impl 引用）；L 局部检查=applied_L.diff（1 文件 ~45 行）。
- 运行环境：cpus=4、memory_mb=4096、SELinux Enforcing、kernel
  6.12.74-android16-6-maybe-dirty（两侧同串）、quiet 日志配置（每块读回）。
- 缺失/未复制项与哈希登记：见 MISSING_ITEMS.md 与 SOURCE_INDEX.csv
  （status=找到未入包，含大文件原路径/大小/SHA-256）。
- 未复制完整源码树或任何多 GB 镜像（任务书要求）。

## 4. 需要修改的论文表述（本轮不改论文，仅登记）
1. pooled P95 应写 10.82/13.42/14.03/14.61 ms（而非 10.80/13.40/14.00/14.60）。
2. LOG_ON/OFF 块中位数建议引用精确值 20.4–23.4 / 6.2–7.0 ms。
3. fig_runtime_cost.pdf（A/B/C）如需引用需另行全文整合。
4. 引用性能数字时按论文真实编号 RQ4（当前 RQ3=转发边界），避免“RQ3 性能”歧义。
5. 差值范围 2.16–3.96 / 1.71–3.02 是逐对差值最小–最大，不得标为 CI；4 对无正式 CI。
