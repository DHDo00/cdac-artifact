#!/usr/bin/env python3
"""Generate SOURCE_INDEX.csv: original path -> package path, category, size, sha256, status."""
import hashlib, os
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
ROWS = []

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def add_dir(src_root, pkg_root, category, prefix_note=""):
    n = 0
    for p in sorted(Path(pkg_root).rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(pkg_root)
        src = Path(src_root) / rel
        ROWS.append([str(src), str((Path(pkg_root) / rel).relative_to(PKG)), category,
                     str(p.stat().st_size), sha256(p), "已入包", prefix_note])
        n += 1
    return n

n = 0
n += add_dir("cdac_esp_endpoint_validation_20261022/10_controls_matched_builds_timing_20261023",
             PKG/"01_esp_paired/10_controls", "ESP-matched-builds-timing")
n += add_dir("cdac_esp_endpoint_validation_20261022/11_perf_paired_20261024",
             PKG/"01_esp_paired/11_perf_paired", "ESP-paired-perf")
n += add_dir("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/01_stats_recompute",
             PKG/"01_esp_paired/12_perf_audit/01_stats_recompute", "ESP-audit-stats")
n += add_dir("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/02_disk_timeline",
             PKG/"01_esp_paired/12_perf_audit/02_disk_timeline", "ESP-audit-disk")
n += add_dir("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/03_mech_compare",
             PKG/"01_esp_paired/12_perf_audit/03_mech_compare", "ESP-mech-compare")
n += add_dir("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/05_final",
             PKG/"01_esp_paired/12_perf_audit/05_final", "ESP-audit-final")
n += add_dir("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/runtime",
             PKG/"01_esp_paired/12_perf_audit/runtime", "ESP-audit-runtime")
n += add_dir("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/scripts",
             PKG/"01_esp_paired/12_perf_audit/scripts", "ESP-audit-scripts")

# minimal implementation deltas + base manifest
n += add_dir("cdac_esp_endpoint_validation_20261022/00_impl",
             PKG/"01_esp_paired/00_impl_minimal", "ESP-impl-minimal-diffs")
for p in sorted((PKG/"01_esp_paired/00_impl_minimal").rglob("*")):
    if p.is_file() and p.name.endswith("default.xml"):
        ROWS.append(["aosp16/.repo/manifests/default.xml", str(p.relative_to(PKG)),
                     "ESP-impl-minimal-diffs", str(p.stat().st_size), sha256(p), "已入包", ""]); n += 1

# 04_builds_minimal contains renamed files -> add manually
bmin = PKG/"01_esp_paired/12_perf_audit/04_builds_minimal"
for p in sorted(bmin.rglob("*")):
    if p.is_file():
        name = p.name
        if name == "nprime_vs_l_tree.diff":
            src = "cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/04_builds/nprime_vs_l_tree.diff"
        elif name.startswith("l_artifacts") or name == "android-info.txt" or name.startswith("build_fingerprint"):
            src = f"cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/04_builds/l_artifacts/{name.replace('l_artifacts_','')}"
        else:
            src = f"cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/04_builds/nprime_artifacts/{name.replace('nprime_artifacts_','')}"
        ROWS.append([src, str(p.relative_to(PKG)), "ESP-audit-builds-minimal", str(p.stat().st_size), sha256(p), "已入包", ""])
        n += 1

# A/B/C (renamed layout to original names 01_preregistration/02_boot_1/03_boot_2/04_analysis/05_final)
for sub in ["01_preregistration", "02_boot_1", "03_boot_2", "04_analysis", "05_final"]:
    n += add_dir(f"cdac_rq4_prospective_performance_v2_20260807_101100/{sub}",
                 PKG/"02_settingsprovider_abc"/sub, "SettingsProvider-A-B-C-D")
for sub in ["20260809_single", "20260810_ieee_variants"]:
    n += add_dir(f"{sub.replace('20260809_single','fig_runtime_cost_20260809_152716').replace('20260810_ieee_variants','fig_runtime_cost_ieee_variants_20260810_093113')}",
                 PKG/"02_settingsprovider_abc/fig_runtime_cost"/sub, "fig-runtime-cost")

# H4 (docs are flattened from top-level; raw_blocks preserved)
h4 = PKG/"03_h4_dp"
for p in sorted((h4/"docs").rglob("*")):
    if p.is_file():
        src = Path("legacy_cdac/cdac_dp_h4_app_visible_performance_20260628_024030") / p.name
        ROWS.append([str(src), str(p.relative_to(PKG)), "H4-DP-docs", str(p.stat().st_size), sha256(p), "已入包", ""]); n += 1
n += add_dir("legacy_cdac/cdac_dp_h4_app_visible_performance_20260628_024030/raw_blocks",
             h4/"raw_blocks", "H4-DP-raw-blocks")

# 21 rule count
r21 = PKG/"04_rule_count_scaling"
for sub in ["00_implementation_audit", "01_evidence_reuse", "02_protocol", "03_rulegen", "06_perf_raw", "07_analysis", "08_final", "scripts", "04_runtime"]:
    n += add_dir(f"21_rule_count_scaling_20261026/{sub}", r21/sub, "rule-count-scaling")
for p in sorted((r21/"05_correctness_minimal").rglob("*")):
    if p.is_file():
        src = Path("21_rule_count_scaling_20261026/05_correctness") / p.name
        ROWS.append([str(src), str(p.relative_to(PKG)), "rule-count-scaling-correctness-minimal", str(p.stat().st_size), sha256(p), "已入包", ""]); n += 1
for f in ["TIME_AND_FAILURES.md", "boot1_attempts.log", "boot2_attempts.log"]:
    p = r21/f
    if p.exists():
        ROWS.append([f"21_rule_count_scaling_20261026/04_runtime/{f}", str(p.relative_to(PKG)), "rule-count-scaling-runtime-minimal", str(p.stat().st_size), sha256(p), "已入包", ""]); n += 1

# 26 concurrent
r26 = PKG/"05_concurrent_attribution"
for sub in ["00_inputs", "02_protocol", "03_scripts", "05_results", "06_final"]:
    n += add_dir(f"26_concurrent_attribution_20261027/{sub}", r26/sub, "concurrent-attribution")
p = r26/"TIME_AND_FAILURES.md"
ROWS.append(["26_concurrent_attribution_20261027/TIME_AND_FAILURES.md", str(p.relative_to(PKG)), "concurrent-attribution", str(p.stat().st_size), sha256(p), "已入包", ""]); n += 1

# 35_r1 metric provenance
r35 = PKG/"06_metric_provenance"
for sub in ["02_metrics", "09_review_updates", "10_paper_draft", "07_results"]:
    n += add_dir(f"35_r1_reversal_and_data_provenance_20261028/{sub}", r35/sub, "metric-provenance")
for f in ["FINAL_STATUS.txt", "SHA256SUMS.txt", "SHA256SUMS_EXCLUSIONS.txt"]:
    p = r35/f
    if p.exists():
        ROWS.append([f"35_r1_reversal_and_data_provenance_20261028/{f}", str(p.relative_to(PKG)), "metric-provenance", str(p.stat().st_size), sha256(p), "已入包", ""]); n += 1

# paper snapshot
r33 = PKG/"07_paper_snapshot"
for p in sorted((r33/"02_paper_revision").rglob("*")):
    if p.is_file():
        ROWS.append([str(Path("33_publish_channel_tcb_audit_20261028/02_paper_revision")/p.name), str(p.relative_to(PKG)), "paper-snapshot", str(p.stat().st_size), sha256(p), "已入包", ""]); n += 1
for f in ["VERSION_RECONCILIATION.md", "MODIFICATION_NOTES.md", "evaluation_completed.tex", "conference_101719.tex"]:
    p = r33/f
    if p.exists():
        src = f"33_publish_channel_tcb_audit_20261028/{f}" if f.endswith(".md") else f"NDSS/{f}"
        ROWS.append([src, str(p.relative_to(PKG)), "paper-snapshot", str(p.stat().st_size), sha256(p), "已入包", ""]); n += 1

# recompute scripts + outputs
n += add_dir(str(PKG), PKG/"recompute", "recompute", prefix_note="NEW_IN_THIS_PACKAGE")

# found-not-packed rows (hash the moderate-size auxiliaries; multi-GB trees noted with size only)
def fnp(src, category, note=""):
    p = Path(src)
    h = sha256(p) if p.is_file() and p.stat().st_size < 200_000_000 else ""
    sz = p.stat().st_size if p.is_file() else "dir"
    ROWS.append([src, "(未入包)", category, str(sz), h, "找到未入包", note])
fnp("cdac_rq4_prospective_performance_v2_20260807_101100/02_boot_1/COUNTER_BASELINE_AND_DELTA.csv", "SettingsProvider-A-B-C-D")
fnp("cdac_rq4_prospective_performance_v2_20260807_101100/03_boot_2/COUNTER_BASELINE_AND_DELTA.csv", "SettingsProvider-A-B-C-D")
fnp("cdac_rq4_prospective_performance_v2_20260807_101100/02_boot_1/PRE_STATE_SNAPSHOTS.csv", "SettingsProvider-A-B-C-D")
fnp("cdac_rq4_prospective_performance_v2_20260807_101100/03_boot_2/PRE_STATE_SNAPSHOTS.csv", "SettingsProvider-A-B-C-D")
fnp("cdac_rq4_prospective_performance_v2_20260807_101100/02_boot_1/LOG_WATERMARK_AUDIT.csv", "SettingsProvider-A-B-C-D")
fnp("cdac_rq4_prospective_performance_v2_20260807_101100/03_boot_2/LOG_WATERMARK_AUDIT.csv", "SettingsProvider-A-B-C-D")
fnp("cdac_rq4_prospective_performance_v2_20260807_101100/02_boot_1/raw/scientific", "SettingsProvider-A-B-C-D-raw-per-block-aux", "per-block configuration.json/cleanup.json/counters_after_workload.json 等 6MB 辅助状态文件未复制")
fnp("cdac_rq4_prospective_performance_v2_20260807_101100/03_boot_2/raw/scientific", "SettingsProvider-A-B-C-D-raw-per-block-aux", "同上")
fnp("cdac_rq4_prospective_performance_v2_20260807_101100/05_final/archive_metadata", "SettingsProvider-A-B-C-D-final", "15MB archive metadata dir")
fnp("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/04_builds/l_system_tree", "ESP-audit-builds-tree")
fnp("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/04_builds/nprime_system_tree", "ESP-audit-builds-tree")
fnp("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/04_builds/l_artifacts", "ESP-audit-builds-images")
fnp("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/04_builds/nprime_artifacts", "ESP-audit-builds-images")
fnp("cdac_esp_endpoint_validation_20261022/12_perf_audit_mech_compare_20261025/04_builds/l_build.log", "ESP-audit-builds-log")
fnp("21_rule_count_scaling_20261026/04_runtime", "rule-count-scaling-runtime-images")
fnp("21_rule_count_scaling_20261026/05_correctness", "rule-count-scaling-correctness-full")
fnp("26_concurrent_attribution_20261027/04_runtime", "concurrent-attribution-runtime")
fnp("legacy_cdac/cdac_dp_h4_app_visible_performance_20260628_024030/raw", "H4-DP-raw-attempt-logs")

with open(PKG / "SOURCE_INDEX.csv", "w", newline="") as fh:
    import csv
    w = csv.writer(fh)
    w.writerow(["source_path", "package_path", "category", "size_bytes", "sha256", "status", "note"])
    for r in ROWS:
        w.writerow(r)
print("SOURCE_INDEX rows:", len(ROWS))
