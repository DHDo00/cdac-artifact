#!/usr/bin/env python3
"""Frozen prospective RQ4 V2 analysis.

Primary A/B/C analysis uses paired block medians.  Bootstrap resampling is
stratified by boot and samples whole blocks only.  D is reported only as
absolute denial-response latency.  No outlier deletion, trimming,
winsorization, or latency-based row selection is implemented.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve()
ANALYSIS = SCRIPT.parent
ROOT = SCRIPT.parent.parent
PREREG = ROOT / "01_preregistration"
CONSTANTS = json.loads((PREREG / "frozen_inputs" / "schemas" / "rq4_constants.json").read_text(encoding="utf-8"))
FREEZE_STATUS = PREREG / "PROTOCOL_FREEZE_STATUS.txt"
SCHEDULE = PREREG / "RANDOMIZED_SCHEDULE.csv"
BOOT_DIRS = {"boot_1": ROOT / "02_boot_1", "boot_2": ROOT / "03_boot_2"}
BOOTSTRAP_SEED = int(CONSTANTS["bootstrap_seed_v2"])
BOOTSTRAP_REPLICATES = int(CONSTANTS["bootstrap_replicates"])


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="microseconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_status(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def write_text(path: Path, value: str) -> None:
    path.write_text(value.rstrip("\n") + "\n", encoding="utf-8", errors="replace")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def finite(values: list[float] | np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    return result[np.isfinite(result)]


def statistic(values: list[float] | np.ndarray, kind: str) -> float:
    data = finite(values)
    if not len(data):
        return math.nan
    if kind == "mean":
        return float(np.mean(data))
    if kind == "median":
        return float(np.median(data))
    if kind == "p95":
        return float(np.percentile(data, 95, method="linear"))
    if kind == "p99":
        return float(np.percentile(data, 99, method="linear"))
    raise ValueError(kind)


def fmt_ns(value: float) -> str:
    return "NA" if not math.isfinite(value) else f"{value:.3f}"


def fmt_us(value: float) -> str:
    return "NA" if not math.isfinite(value) else f"{value / 1000.0:.3f}"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    deviations: list[str] = []
    status = parse_status(FREEZE_STATUS)
    protocol_sha = sha256_file(PREREG / "RQ4_PROTOCOL_V2.md")
    if status.get("PROTOCOL_SHA256") != protocol_sha:
        raise RuntimeError("protocol hash does not match frozen status")
    schedule = pd.read_csv(SCHEDULE, dtype=str)
    if len(schedule) != 2000 or schedule["trial_id"].duplicated().any():
        raise RuntimeError("frozen schedule denominator or uniqueness failure")
    frames: list[pd.DataFrame] = []
    for boot_id, directory in BOOT_DIRS.items():
        path = directory / "SCIENTIFIC_ROWS.csv"
        if not path.exists():
            deviations.append(f"{boot_id}:SCIENTIFIC_ROWS_MISSING")
            continue
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        frame["source_boot_dir"] = boot_id
        frames.append(frame)
    rows = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if rows.empty:
        raise RuntimeError("no measured scientific rows available")
    if rows["trial_id"].duplicated().any():
        raise RuntimeError("duplicate measured trial IDs")
    schedule_ids = set(schedule["trial_id"])
    unexpected = sorted(set(rows["trial_id"]) - schedule_ids)
    if unexpected:
        raise RuntimeError(f"unregistered measured trial IDs: {unexpected[:5]}")
    merged = rows.merge(schedule, on="trial_id", how="left", suffixes=("", "_schedule"), validate="one_to_one")
    for field in ("boot_id", "stage", "block_id", "block_index", "global_schedule_position", "boot_schedule_position", "randomized_position", "arm", "trial_index"):
        schedule_field = field + "_schedule"
        mismatch = merged[field].astype(str) != merged[schedule_field].astype(str)
        if mismatch.any():
            raise RuntimeError(f"row/schedule mismatch in {field}")
    if not (merged["protocol_sha256"] == protocol_sha).all():
        raise RuntimeError("one or more measured rows have the wrong protocol hash")
    if "protocol_version" not in merged or not (merged["protocol_version"] == "V2").all():
        raise RuntimeError("non-V2 measured row found")
    if any(str(value).startswith("RQ4-B") for value in merged["trial_id"]):
        raise RuntimeError("V1 trial identifier merged into V2")
    if not (merged["scientific_row"] == "yes").all():
        raise RuntimeError("non-scientific rows found in SCIENTIFIC_ROWS.csv")
    expected_order = schedule[schedule["trial_id"].isin(set(rows["trial_id"]))].sort_values("global_schedule_position", key=lambda x: x.astype(int))["trial_id"].tolist()
    actual_order = merged.sort_values("global_schedule_position", key=lambda x: x.astype(int))["trial_id"].tolist()
    if expected_order != actual_order:
        raise RuntimeError("observed row order differs from frozen schedule order")
    if len(merged) != 2000:
        deviations.append(f"SCIENTIFIC_DENOMINATOR_INCOMPLETE:{len(merged)}/2000")
    counts = Counter(merged["arm"])
    for arm in "ABCD":
        if counts[arm] != 500:
            deviations.append(f"ARM_{arm}_DENOMINATOR:{counts[arm]}/500")
    merged["latency_numeric_ns"] = pd.to_numeric(merged["latency_ns"], errors="coerce")
    return merged, schedule, deviations


def primary_blocks(rows: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    allow = rows[rows["arm"].isin(list("ABC"))].copy()
    eligible = allow[
        (allow["primary_eligible"] == "yes")
        & (allow["classification"] == "VALID_ALLOW_PATH_SAMPLE")
        & (allow["reset_oracle_result"] == "PASS")
        & (allow["reset_completion_pair"] == "yes")
        & allow["latency_numeric_ns"].notna()
    ]
    output: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    for (boot_id, block_id), block in allow.groupby(["boot_id", "block_id"], sort=False):
        medians: dict[str, float] = {}
        counts: dict[str, int] = {}
        for arm in "ABC":
            selected = eligible[(eligible["boot_id"] == boot_id) & (eligible["block_id"] == block_id) & (eligible["arm"] == arm)]
            counts[arm] = len(selected)
            if len(selected) == 5:
                medians[arm] = float(np.median(selected["latency_numeric_ns"].astype(float)))
        if all(counts[arm] == 5 for arm in "ABC"):
            output.append({
                "boot_id": boot_id, "block_id": block_id,
                "A_eligible_n": counts["A"], "B_eligible_n": counts["B"], "C_eligible_n": counts["C"],
                "median_A_ns": medians["A"], "median_B_ns": medians["B"], "median_C_ns": medians["C"],
                "Delta_BA_ns": medians["B"] - medians["A"],
                "Delta_CB_ns": medians["C"] - medians["B"],
                "Delta_CA_ns": medians["C"] - medians["A"],
                "paired_block_eligible": "yes",
            })
        else:
            incomplete.append({
                "record_type": "block", "trial_id": "", "boot_id": boot_id,
                "block_id": block_id, "arm": "ABC", "classification": "INCOMPLETE_PAIRED_BLOCK",
                "primary_eligible": "no",
                "exclusion_reason": f"registered block requires 5 eligible rows per arm; observed A={counts['A']},B={counts['B']},C={counts['C']}",
                "failure_codes": "INCOMPLETE_PAIRED_BLOCK", "latency_ns": "",
                "raw_evidence_path": "",
            })
    return pd.DataFrame(output), incomplete


def bootstrap(blocks: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, tuple[float, float]]]:
    columns = ["Delta_BA_ns", "Delta_CB_ns", "Delta_CA_ns"]
    grouped = {
        boot: frame[columns].to_numpy(dtype=float)
        for boot, frame in blocks.groupby("boot_id")
    }
    if set(grouped) != {"boot_1", "boot_2"} or any(len(grouped[boot]) == 0 for boot in grouped):
        return pd.DataFrame(), {}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    records: list[dict[str, Any]] = []
    for replicate in range(1, BOOTSTRAP_REPLICATES + 1):
        sampled_arrays = []
        for boot in ("boot_1", "boot_2"):
            array = grouped[boot]
            indices = rng.integers(0, len(array), size=len(array))
            sampled_arrays.append(array[indices])
        medians = np.median(np.vstack(sampled_arrays), axis=0)
        records.append({
            "replicate": replicate, "bootstrap_seed": BOOTSTRAP_SEED,
            "Delta_BA_ns": float(medians[0]),
            "Delta_CB_ns": float(medians[1]),
            "Delta_CA_ns": float(medians[2]),
            "boot_1_blocks_resampled": len(grouped["boot_1"]),
            "boot_2_blocks_resampled": len(grouped["boot_2"]),
        })
    frame = pd.DataFrame(records)
    intervals = {
        contrast: (
            float(np.percentile(frame[contrast], 2.5, method="linear")),
            float(np.percentile(frame[contrast], 97.5, method="linear")),
        )
        for contrast in ("Delta_BA_ns", "Delta_CB_ns", "Delta_CA_ns")
    }
    return frame, intervals


def compress_bootstrap(frame: pd.DataFrame) -> None:
    plain = ANALYSIS / "BOOTSTRAP_REPLICATES.csv"
    compressed = ANALYSIS / "BOOTSTRAP_REPLICATES.csv.zst"
    frame.to_csv(plain, index=False, lineterminator="\n")
    proc = subprocess.run(
        ["zstd", "-19", "-f", str(plain), "-o", str(compressed)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    write_text(ANALYSIS / "BOOTSTRAP_COMPRESSION.txt", "\n".join([
        f"RETURN_CODE={proc.returncode}", proc.stdout,
    ]))
    if proc.returncode != 0:
        raise RuntimeError("zstd bootstrap compression failed")
    plain.unlink()


def descriptive(rows: pd.DataFrame) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for scope, subset in [("pooled", rows)] + [(boot, rows[rows["boot_id"] == boot]) for boot in ("boot_1", "boot_2")]:
        for arm in "ABC":
            arm_rows = subset[subset["arm"] == arm]
            valid = arm_rows[
                (arm_rows["primary_eligible"] == "yes")
                & (arm_rows["classification"] == "VALID_ALLOW_PATH_SAMPLE")
                & arm_rows["latency_numeric_ns"].notna()
            ]["latency_numeric_ns"].astype(float).to_numpy()
            output.append({
                "scope": scope, "arm": arm, "raw_denominator_n": len(arm_rows),
                "registered_success_n": len(valid), "mean_ns": statistic(valid, "mean"),
                "median_ns": statistic(valid, "median"), "P95_ns": statistic(valid, "p95"),
                "P99_ns": statistic(valid, "p99"), "latency_unit": "ns",
                "outlier_deletion": "none",
            })
    return output


def denial_statistics(rows: pd.DataFrame) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for scope, subset in [("pooled", rows)] + [(boot, rows[rows["boot_id"] == boot]) for boot in ("boot_1", "boot_2")]:
        raw = subset[subset["arm"] == "D"]
        valid = raw[
            (raw["primary_eligible"] == "yes")
            & (raw["classification"] == "VALID_ABSOLUTE_DENIAL_LATENCY_SAMPLE")
            & raw["latency_numeric_ns"].notna()
        ]["latency_numeric_ns"].astype(float).to_numpy()
        output.append({
            "scope": scope, "raw_denominator_n": len(raw), "registered_denial_success_n": len(valid),
            "mean_ns": statistic(valid, "mean"), "median_P50_ns": statistic(valid, "median"),
            "P95_ns": statistic(valid, "p95"), "P99_ns": statistic(valid, "p99"),
            "latency_unit": "ns", "result_name": "absolute denial-response latency",
            "overhead_computed": "no",
        })
    return output


def failure_ledger(rows: pd.DataFrame, incomplete: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    failures = rows[
        (rows["primary_eligible"] != "yes")
        | ~rows["classification"].isin(["VALID_ALLOW_PATH_SAMPLE", "VALID_ABSOLUTE_DENIAL_LATENCY_SAMPLE"])
    ]
    for _, row in failures.iterrows():
        output.append({
            "record_type": "trial", "trial_id": row["trial_id"], "boot_id": row["boot_id"],
            "block_id": row["block_id"], "arm": row["arm"],
            "classification": row["classification"], "primary_eligible": row["primary_eligible"],
            "exclusion_reason": row["exclusion_reason"], "failure_codes": row["failure_codes"],
            "latency_ns": row["latency_ns"], "raw_evidence_path": row["raw_evidence_path"],
        })
    output.extend(incomplete)
    return output


def main() -> int:
    analysis_started = now()
    rows, schedule, deviations = load_inputs()
    blocks, incomplete = primary_blocks(rows)
    block_fields = [
        "boot_id", "block_id", "A_eligible_n", "B_eligible_n", "C_eligible_n",
        "median_A_ns", "median_B_ns", "median_C_ns", "Delta_BA_ns", "Delta_CB_ns",
        "Delta_CA_ns", "paired_block_eligible",
    ]
    write_csv(ANALYSIS / "PRIMARY_BLOCK_ESTIMATES.csv", block_fields, blocks.to_dict("records") if not blocks.empty else [])
    bootstrap_frame, intervals = bootstrap(blocks)
    if len(bootstrap_frame) == BOOTSTRAP_REPLICATES:
        compress_bootstrap(bootstrap_frame)
    else:
        deviations.append("BOOTSTRAP_NOT_EXECUTABLE:complete blocks missing from one or both boots")
        compress_bootstrap(pd.DataFrame(columns=[
            "replicate", "bootstrap_seed", "Delta_BA_ns", "Delta_CB_ns",
            "Delta_CA_ns", "boot_1_blocks_resampled", "boot_2_blocks_resampled",
        ]))

    estimate_rows: list[dict[str, Any]] = []
    contrast_columns = {"Delta_BA": "Delta_BA_ns", "Delta_CB": "Delta_CB_ns", "Delta_CA": "Delta_CA_ns"}
    for scope in ("pooled", "boot_1", "boot_2"):
        selected = blocks if scope == "pooled" else blocks[blocks["boot_id"] == scope]
        for name, column in contrast_columns.items():
            estimate = statistic(selected[column].to_numpy() if not selected.empty else [], "median")
            low, high = intervals.get(column, (math.nan, math.nan)) if scope == "pooled" else (math.nan, math.nan)
            estimate_rows.append({
                "scope": scope, "contrast": name, "estimate": "median_of_paired_block_differences",
                "estimate_ns": estimate, "ci_low_ns": low, "ci_high_ns": high,
                "ci_method": "95% percentile stratified block bootstrap" if scope == "pooled" else "not_registered_for_boot_specific_summary",
                "complete_blocks": len(selected), "bootstrap_replicates": BOOTSTRAP_REPLICATES if scope == "pooled" and intervals else 0,
            })
    write_csv(ANALYSIS / "BOOT_SPECIFIC_ESTIMATES.csv", list(estimate_rows[0]), estimate_rows)
    write_csv(ANALYSIS / "PRIMARY_ESTIMATES_SUMMARY.csv", list(estimate_rows[0]), [row for row in estimate_rows if row["scope"] == "pooled"])

    arm_stats = descriptive(rows)
    write_csv(ANALYSIS / "ARM_DESCRIPTIVE_STATISTICS.csv", list(arm_stats[0]), arm_stats)
    denial_stats = denial_statistics(rows)
    write_csv(ANALYSIS / "DENIAL_LATENCY_STATISTICS.csv", list(denial_stats[0]), denial_stats)
    failures = failure_ledger(rows, incomplete)
    failure_fields = ["record_type", "trial_id", "boot_id", "block_id", "arm", "classification", "primary_eligible", "exclusion_reason", "failure_codes", "latency_ns", "raw_evidence_path"]
    write_csv(ANALYSIS / "EXCLUSIONS_AND_FAILURES.csv", failure_fields, failures)

    protocol_sha = parse_status(FREEZE_STATUS)["PROTOCOL_SHA256"]
    raw_counts = Counter(rows["arm"])
    valid_counts = Counter(rows[rows["primary_eligible"] == "yes"]["arm"])
    complete_by_boot = Counter(blocks["boot_id"]) if not blocks.empty else Counter()
    primary = {row["contrast"]: row for row in estimate_rows if row["scope"] == "pooled"}
    denial_pooled = next(row for row in denial_stats if row["scope"] == "pooled")
    prospective_ok = (ROOT / "execution_manifests" / "FIRST_SCIENTIFIC_EXECUTION.txt").exists()
    denominator_complete = len(rows) == 2000 and all(raw_counts[arm] == 500 for arm in "ABCD")
    primary_executed = len(blocks) > 0 and len(bootstrap_frame) == BOOTSTRAP_REPLICATES
    denial_fillable = denominator_complete and denial_pooled["registered_denial_success_n"] > 0
    allow_fillable = denominator_complete and primary_executed

    deviation_text = ["# Protocol deviations", ""]
    if deviations:
        deviation_text.extend(f"- {item}" for item in deviations)
    else:
        deviation_text.append("No protocol deviation was detected by the frozen analysis checks.")
    deviation_text.extend([
        "", "Latency values, outcome direction, interval width, and statistical significance were not used as stopping or exclusion criteria.",
    ])
    write_text(ANALYSIS / "PROTOCOL_DEVIATIONS.md", "\n".join(deviation_text))

    numeric = [
        "# Final numeric summary", "",
        f"Protocol SHA-256: `{protocol_sha}`.",
        f"Raw measured denominator: A={raw_counts['A']}, B={raw_counts['B']}, C={raw_counts['C']}, D={raw_counts['D']}; total={len(rows)}.",
        f"Registered-success rows: A={valid_counts['A']}, B={valid_counts['B']}, C={valid_counts['C']}, D={valid_counts['D']}.",
        f"Complete paired A/B/C blocks: boot_1={complete_by_boot['boot_1']}, boot_2={complete_by_boot['boot_2']}, pooled={len(blocks)}.", "",
        "## Primary paired allow-path contrasts", "",
    ]
    for contrast in ("Delta_BA", "Delta_CB"):
        row = primary[contrast]
        numeric.append(
            f"- {contrast}: pooled median {fmt_ns(float(row['estimate_ns']))} ns ({fmt_us(float(row['estimate_ns']))} µs); "
            f"95% stratified block-bootstrap interval [{fmt_ns(float(row['ci_low_ns']))}, {fmt_ns(float(row['ci_high_ns']))}] ns "
            f"([{fmt_us(float(row['ci_low_ns']))}, {fmt_us(float(row['ci_high_ns']))}] µs)."
        )
    numeric.extend(["", "Boot-specific medians:", ""])
    for boot in ("boot_1", "boot_2"):
        for contrast in ("Delta_BA", "Delta_CB"):
            row = next(item for item in estimate_rows if item["scope"] == boot and item["contrast"] == contrast)
            numeric.append(f"- {boot} {contrast}: {fmt_ns(float(row['estimate_ns']))} ns ({fmt_us(float(row['estimate_ns']))} µs), complete blocks={row['complete_blocks']}.")
    numeric.extend([
        "", "## Secondary allow-path contrast", "",
        f"- Delta_CA: pooled median {fmt_ns(float(primary['Delta_CA']['estimate_ns']))} ns ({fmt_us(float(primary['Delta_CA']['estimate_ns']))} µs); "
        f"95% interval [{fmt_ns(float(primary['Delta_CA']['ci_low_ns']))}, {fmt_ns(float(primary['Delta_CA']['ci_high_ns']))}] ns.",
        "", "## Absolute denial-response latency", "",
        f"- Pooled registered denial N={denial_pooled['registered_denial_success_n']} (raw D denominator={denial_pooled['raw_denominator_n']}).",
        f"- Mean={fmt_ns(float(denial_pooled['mean_ns']))} ns ({fmt_us(float(denial_pooled['mean_ns']))} µs).",
        f"- P50={fmt_ns(float(denial_pooled['median_P50_ns']))} ns ({fmt_us(float(denial_pooled['median_P50_ns']))} µs).",
        f"- P95={fmt_ns(float(denial_pooled['P95_ns']))} ns ({fmt_us(float(denial_pooled['P95_ns']))} µs).",
        f"- P99={fmt_ns(float(denial_pooled['P99_ns']))} ns ({fmt_us(float(denial_pooled['P99_ns']))} µs).",
        "", "D is an absolute latency distribution. No D-A, D-B, D-C, percentage overhead, native-denial overhead, or kernel-only cost was computed.",
    ])
    write_text(ANALYSIS / "FINAL_NUMERIC_SUMMARY.md", "\n".join(numeric))

    eligibility = [
        "# Final paper eligibility", "",
        f"PAPER_ALLOW_PATH_SLOT={'FILLABLE' if allow_fillable else 'NOT_FILLABLE'}",
        f"PAPER_DENIAL_LATENCY_SLOT={'FILLABLE' if denial_fillable else 'NOT_FILLABLE'}",
        "NATIVE_ANDROID_OVERHEAD_SLOT=NOT_EVALUATED",
        "DENIAL_OVERHEAD_SLOT=NOT_EVALUATED",
        "UNIVERSAL_LOW_OVERHEAD_SLOT=NOT_EVALUATED", "",
        "Eligible wording is limited to the same-artifact CDAC-inactive baseline, incremental latency of entering the active CDAC path, incremental latency of one registered nonmatching lookup, absolute denial-response latency, and a two-boot result on one retained S10 artifact.",
        "The registered verbose-audit verification instrumentation was active for every invocation; results therefore describe this retained, instrumented route and are not a kernel-only cost.",
    ]
    write_text(ANALYSIS / "FINAL_PAPER_ELIGIBILITY.md", "\n".join(eligibility))

    reset_failures = int((rows["reset_oracle_result"] != "PASS").sum()) if "reset_oracle_result" in rows else len(rows)
    carry_failures = int((rows["carry_over_detector_result"] != "PASS").sum())
    reset_summary = [
        "# Reset and carry-over summary", "",
        f"V2 reset completion failures in invoked rows: {reset_failures}.",
        f"Rows with a failed carry-over detector: {carry_failures}.",
        "Broad counters were analyzed as pre-state baseline/delta; aliases were retained and not double-counted.",
        "A failed post-invocation completion oracle would be retained and would terminate execution under the frozen protocol.",
    ]
    write_text(ANALYSIS / "RESET_AND_CARRY_OVER_SUMMARY.md", "\n".join(reset_summary))

    env = [
        f"ANALYSIS_STARTED_AT={analysis_started}", f"ANALYSIS_COMPLETED_AT={now()}",
        f"ANALYSIS_SCRIPT_SHA256={sha256_file(SCRIPT)}", f"PROTOCOL_SHA256={protocol_sha}",
        f"PYTHON={sys.version.replace(os.linesep, ' ')}", f"PLATFORM={platform.platform()}",
        f"NUMPY={np.__version__}", f"PANDAS={pd.__version__}",
        f"BOOTSTRAP_SEED={BOOTSTRAP_SEED}", f"BOOTSTRAP_REPLICATES={BOOTSTRAP_REPLICATES}",
        "PERCENTILE_METHOD=numpy.percentile linear", "OUTLIER_DELETION=none",
        "BOOTSTRAP_UNIT=whole block within boot strata",
    ]
    zstd_version = subprocess.run(["zstd", "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip()
    env.append(f"ZSTD={zstd_version}")
    write_text(ANALYSIS / "ANALYSIS_ENVIRONMENT.txt", "\n".join(env))

    analysis_files = [path for path in ANALYSIS.iterdir() if path.is_file() and path.name != "SHA256SUMS"]
    write_text(ANALYSIS / "SHA256SUMS", "\n".join(
        f"{sha256_file(path)}  {path.name}" for path in sorted(analysis_files, key=lambda item: item.name)
    ))
    summary = {
        "protocol_sha256": protocol_sha, "scientific_rows": len(rows),
        "raw_arm_counts": dict(raw_counts), "valid_arm_counts": dict(valid_counts),
        "complete_blocks": dict(complete_by_boot), "primary_executed": primary_executed,
        "bootstrap_executed": len(bootstrap_frame) == BOOTSTRAP_REPLICATES,
        "allow_path_slot": "FILLABLE" if allow_fillable else "NOT_FILLABLE",
        "denial_latency_slot": "FILLABLE" if denial_fillable else "NOT_FILLABLE",
        "prospective_manifest_present": prospective_ok, "deviations": deviations,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
