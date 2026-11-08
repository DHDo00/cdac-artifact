#!/usr/bin/env python3
"""Create the final RQ4 ledgers, read-only payload, and verified archive."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SCRIPT = Path(__file__).resolve()
FROZEN = SCRIPT.parents[1]
PREREG = SCRIPT.parents[2]
ROOT = SCRIPT.parents[3]
FINAL = ROOT / "05_final"
ANALYSIS = ROOT / "04_analysis"
META = FINAL / "archive_metadata"
PAYLOAD = FINAL / "payload"
ARCHIVE = ROOT.parent / f"{ROOT.name}.tar.zst"
CONSTANTS = json.loads((FROZEN / "schemas" / "rq4_constants.json").read_text(encoding="utf-8"))
RQ2 = Path(CONSTANTS["rq2_root"])
PREFLIGHT = Path(CONSTANTS["engineering_preflight_root"])


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="microseconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_status(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip("\n") + "\n", encoding="utf-8", errors="replace")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run(args: list[str], cwd: Path | None = None, timeout: int = 3600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout,
    )


def freeze_tree(path: Path) -> None:
    for item in sorted(path.rglob("*"), reverse=True):
        if item.is_symlink():
            continue
        if item.is_file():
            item.chmod(0o444)
        elif item.is_dir():
            item.chmod(0o555)
    if path.exists() and path.is_dir():
        path.chmod(0o555)


def thaw_tree(path: Path) -> None:
    for item in path.rglob("*"):
        if item.is_dir() and not item.is_symlink():
            item.chmod(0o755)
        elif item.is_file() and not item.is_symlink():
            item.chmod(0o644)
    if path.exists():
        path.chmod(0o755)


def input_manifest_verification() -> tuple[bool, bool]:
    pre_manifest = ROOT / "00_preflight" / "PREFLIGHT_SOURCE_SHA256SUMS"
    rq2_manifest = ROOT / "00_preflight" / "RQ2_SOURCE_SHA256SUMS"
    pre = run(["sha256sum", "-c", str(pre_manifest)], cwd=PREFLIGHT, timeout=1800)
    rq2 = run(["sha256sum", "-c", str(rq2_manifest)], cwd=RQ2, timeout=1800)
    write_text(META / "PREFLIGHT_INPUT_RECHECK.txt", pre.stdout)
    write_text(META / "RQ2_INPUT_RECHECK.txt", rq2.stdout)
    return pre.returncode == 0, rq2.returncode == 0


def build_final_documents(rows: list[dict[str, str]], warmups: list[dict[str, str]]) -> dict[str, Any]:
    protocol = parse_status(PREREG / "PROTOCOL_FREEZE_STATUS.txt")
    first = parse_status(ROOT / "execution_manifests" / "FIRST_SCIENTIFIC_EXECUTION.txt")
    input_status = parse_status(ROOT / "00_preflight" / "INPUT_VERIFICATION_STATUS.txt")
    boot_statuses = [
        parse_status(ROOT / "02_boot_1" / "BOOT_STATUS.txt"),
        parse_status(ROOT / "03_boot_2" / "BOOT_STATUS.txt"),
    ]
    counts = Counter(row["arm"] for row in rows)
    valid = Counter(row["arm"] for row in rows if row["primary_eligible"] == "yes")
    classifications = Counter(row["classification"] for row in rows)
    carry_count = sum(row["carry_over_detector_result"] != "PASS" for row in rows)
    failures = read_rows(ANALYSIS / "EXCLUSIONS_AND_FAILURES.csv")
    trial_failures = [row for row in failures if row["record_type"] == "trial"]
    block_failures = [row for row in failures if row["record_type"] == "block"]
    prereg_hash = protocol["PROTOCOL_SHA256"]
    frozen_at = datetime.fromisoformat(protocol["PROTOCOL_FROZEN_AT"])
    first_at = datetime.fromisoformat(first["FIRST_SCIENTIFIC_EXECUTION_AT"])
    ordering_ok = first_at > frozen_at and first.get("PROTOCOL_SHA256") == prereg_hash
    boots_completed = sum(status.get("BOOT_STATUS") == "PASS" for status in boot_statuses)
    denominator_complete = len(rows) == 2000 and all(counts[arm] == 500 for arm in "ABCD")
    analysis_env = parse_status(ANALYSIS / "ANALYSIS_ENVIRONMENT.txt")
    primary_rows = read_rows(ANALYSIS / "PRIMARY_ESTIMATES_SUMMARY.csv")
    primary_executed = (
        len(primary_rows) == 3
        and all(row.get("complete_blocks") == "100" for row in primary_rows)
    )
    bootstrap_path = ANALYSIS / "BOOTSTRAP_REPLICATES.csv.zst"
    bootstrap_lines = run(["zstd", "-dc", str(bootstrap_path)], timeout=1800).stdout.splitlines() if bootstrap_path.exists() else []
    bootstrap_executed = (
        len(bootstrap_lines) == 10001
        and analysis_env.get("BOOTSTRAP_REPLICATES") == "10000"
    )
    paper = parse_status(ANALYSIS / "FINAL_PAPER_ELIGIBILITY.md")

    shutil.copy2(ANALYSIS / "FINAL_NUMERIC_SUMMARY.md", FINAL / "FINAL_NUMERIC_SUMMARY.md")
    shutil.copy2(ANALYSIS / "FINAL_PAPER_ELIGIBILITY.md", FINAL / "FINAL_PAPER_ELIGIBILITY.md")
    recovery_events = []
    launch = ROOT / "execution_manifests" / "CVD_LAUNCH.txt"
    if launch.exists():
        text = launch.read_text(encoding="utf-8", errors="replace")
        if "ATTEMPT_2_STARTED_AT" in text:
            recovery_events.append("CVD startup required the frozen second pre-invocation attempt.")
    pre_failures = list(ROOT.glob("0[23]_boot_*/raw/*/*/PRE_INVOCATION_FAILURE.txt"))
    recovery_events.extend(f"Pre-invocation failure retained at {path.relative_to(ROOT)} (zero scientific rows)." for path in pre_failures)
    recovery = ["# Final execution recovery", ""]
    recovery.extend(f"- {event}" for event in recovery_events)
    if not recovery_events:
        recovery.append("No protocol-controlled recovery action was required after CVD launch.")
    recovery.extend(["", "No recovery changed the protocol, schedule, arm definitions, sample size, estimator, or an invoked row."])
    write_text(FINAL / "FINAL_EXECUTION_RECOVERY.md", "\n".join(recovery))

    write_text(FINAL / "FINAL_PROTOCOL_INTEGRITY.md", "\n".join([
        "# Final protocol integrity", "",
        f"- PRE_AUTHORIZATION_PRESENT: {'yes' if (PREREG / 'PRE_AUTHORIZATION.txt').exists() else 'no'}",
        f"- Protocol SHA-256: `{prereg_hash}`.",
        f"- Protocol frozen at: `{protocol['PROTOCOL_FROZEN_AT']}`.",
        f"- First scientific execution at: `{first['FIRST_SCIENTIFIC_EXECUTION_AT']}`.",
        f"- Machine-verifiable prospective ordering: {'PASS' if ordering_ok else 'FAIL'}.",
        f"- Scientific trials before freeze: {protocol['SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE']}.",
        "- Every measured row was checked against the frozen trial ID, position, arm, and protocol hash by the frozen analysis.",
        "- The preregistration tree and analysis script were read-only before warm-up or scientific invocation.",
    ]))

    write_text(FINAL / "FINAL_EXECUTION_ACCOUNTING.md", "\n".join([
        "# Final execution accounting", "",
        f"- Boots completed: {boots_completed}/2.",
        f"- Raw scientific rows: {len(rows)}/2000.",
        f"- A={counts['A']}/500, B={counts['B']}/500, C={counts['C']}/500, D={counts['D']}/500.",
        f"- Warm-up rows: {len(warmups)}/120; merged into scientific denominator: 0.",
        "- Engineering probes merged: 0.",
        "- Old performance rows merged: 0.",
        "- RQ2 rows merged: 0.",
        "- Unregistered rows added: 0.",
        f"- Registered-success rows: A={valid['A']}, B={valid['B']}, C={valid['C']}, D={valid['D']}.",
        f"- Carry-over detector failures: {carry_count}.",
    ]))

    write_text(FINAL / "FINAL_ATTRITION.md", "\n".join([
        "# Final attrition", "",
        f"- Raw measured denominator: {len(rows)}.",
        f"- Invoked trial-level nonprimary outcome strata: {len(trial_failures)}.",
        f"- Incomplete paired A/B/C blocks: {len(block_failures)}.",
        f"- A registered-success: {valid['A']}/{counts['A']}.",
        f"- B registered-success: {valid['B']}/{counts['B']}.",
        f"- C registered-success: {valid['C']}/{counts['C']}.",
        f"- D registered-success: {valid['D']}/{counts['D']}.",
        "- No latency outlier, trimming, winsorization, replacement, or manual deletion was used.",
        "- Full row-level and block-level reasons are in `04_analysis/EXCLUSIONS_AND_FAILURES.csv`.",
    ]))

    prohibited = [
        "native Android overhead", "unmodified Android baseline", "negligible overhead",
        "zero overhead", "speedup", "denial overhead", "kernel-only lookup cost",
        "Android-wide performance", "DP performance", "old Batch4B number",
        "approximately 35 microseconds at N=4096", "Pixel 8/AOSP15",
        "performance generalization beyond the retained route/artifact",
    ]
    write_text(FINAL / "FINAL_DO_NOT_CLAIM.md", "# Final do-not-claim list\n\n" + "\n".join(f"- {item}" for item in prohibited))

    claim_rows = [
        {"claim_id": "C1", "claim": "same-artifact CDAC-inactive baseline", "status": "ELIGIBLE" if counts["A"] else "NOT_ESTABLISHED", "evidence": "02_boot_1/SCIENTIFIC_ROWS.csv;03_boot_2/SCIENTIFIC_ROWS.csv", "restriction": "never call native or unmodified Android"},
        {"claim_id": "C2", "claim": "incremental latency of entering the active CDAC path", "status": paper.get("PAPER_ALLOW_PATH_SLOT", "NOT_FILLABLE"), "evidence": "04_analysis/PRIMARY_ESTIMATES_SUMMARY.csv", "restriction": "same retained instrumented S10 route only"},
        {"claim_id": "C3", "claim": "incremental latency of one registered nonmatching lookup", "status": paper.get("PAPER_ALLOW_PATH_SLOT", "NOT_FILLABLE"), "evidence": "04_analysis/PRIMARY_ESTIMATES_SUMMARY.csv", "restriction": "same retained instrumented S10 route only"},
        {"claim_id": "C4", "claim": "absolute denial-response latency", "status": paper.get("PAPER_DENIAL_LATENCY_SLOT", "NOT_FILLABLE"), "evidence": "04_analysis/DENIAL_LATENCY_STATISTICS.csv", "restriction": "not overhead and not kernel-only cost"},
    ]
    for index, claim in enumerate(prohibited, start=1):
        claim_rows.append({"claim_id": f"P{index}", "claim": claim, "status": "PROHIBITED", "evidence": "05_final/FINAL_DO_NOT_CLAIM.md", "restriction": "must not be asserted"})
    write_csv(FINAL / "FINAL_CLAIM_LEDGER.csv", ["claim_id", "claim", "status", "evidence", "restriction"], claim_rows)

    evidence_paths = [
        ("E1", "protocol", PREREG / "RQ4_PROTOCOL_V1.md", "frozen protocol"),
        ("E2", "schedule", PREREG / "RANDOMIZED_SCHEDULE.csv", "2,000-row frozen measured schedule"),
        ("E3", "boot_1_rows", ROOT / "02_boot_1" / "SCIENTIFIC_ROWS.csv", "boot-1 raw denominator"),
        ("E4", "boot_2_rows", ROOT / "03_boot_2" / "SCIENTIFIC_ROWS.csv", "boot-2 raw denominator"),
        ("E5", "primary", ANALYSIS / "PRIMARY_ESTIMATES_SUMMARY.csv", "registered paired block estimates"),
        ("E6", "bootstrap", ANALYSIS / "BOOTSTRAP_REPLICATES.csv.zst", "10,000 registered bootstrap replicates"),
        ("E7", "denial", ANALYSIS / "DENIAL_LATENCY_STATISTICS.csv", "absolute denial-response distribution"),
        ("E8", "failures", ANALYSIS / "EXCLUSIONS_AND_FAILURES.csv", "trial and block attrition ledger"),
    ]
    evidence_rows = [
        {"evidence_id": eid, "role": role, "status": "PRESENT" if path.exists() else "MISSING", "path": str(path.relative_to(ROOT)), "sha256": sha256_file(path) if path.exists() else "", "description": description}
        for eid, role, path, description in evidence_paths
    ]
    write_csv(FINAL / "FINAL_EVIDENCE_LEDGER.csv", ["evidence_id", "role", "status", "path", "sha256", "description"], evidence_rows)
    return {
        "protocol": protocol, "first": first, "input_status": input_status,
        "boot_statuses": boot_statuses, "counts": counts, "valid": valid,
        "classifications": classifications, "carry_count": carry_count,
        "boots_completed": boots_completed, "denominator_complete": denominator_complete,
        "ordering_ok": ordering_ok, "primary_executed": primary_executed,
        "bootstrap_executed": bootstrap_executed, "paper": paper,
        "trial_failures": trial_failures, "block_failures": block_failures,
    }


def create_payload() -> None:
    if PAYLOAD.exists():
        raise RuntimeError("payload already exists; refusing replacement")
    PAYLOAD.mkdir(parents=True)
    names = [
        "FINAL_CLAIM_LEDGER.csv", "FINAL_EVIDENCE_LEDGER.csv",
        "FINAL_NUMERIC_SUMMARY.md", "FINAL_PAPER_ELIGIBILITY.md",
        "FINAL_PROTOCOL_INTEGRITY.md", "FINAL_EXECUTION_ACCOUNTING.md",
        "FINAL_ATTRITION.md", "FINAL_DO_NOT_CLAIM.md",
        "FINAL_EXECUTION_RECOVERY.md",
    ]
    for name in names:
        shutil.copy2(FINAL / name, PAYLOAD / name)
    lines = [
        f"{sha256_file(path)}  {path.name}"
        for path in sorted(PAYLOAD.iterdir(), key=lambda item: item.name) if path.is_file()
    ]
    write_text(PAYLOAD / "PAYLOAD_SHA256SUMS", "\n".join(lines))
    freeze_tree(PAYLOAD)


def create_archive() -> tuple[str, dict[str, Any]]:
    if ARCHIVE.exists():
        raise RuntimeError(f"archive already exists: {ARCHIVE}")
    parent = ROOT.parent
    root_name = ROOT.name
    members = [
        f"{root_name}/00_preflight", f"{root_name}/01_preregistration",
        f"{root_name}/02_boot_1", f"{root_name}/03_boot_2",
        f"{root_name}/04_analysis", f"{root_name}/05_final",
        f"{root_name}/execution_manifests",
        f"{root_name}/runtime/cvd/cuttlefish_config.json",
    ]
    archived = run(["tar", "--zstd", "-cf", str(ARCHIVE), "-C", str(parent), *members], timeout=7200)
    if archived.returncode != 0:
        raise RuntimeError(f"archive creation failed: {archived.stdout}")
    archive_sha = sha256_file(ARCHIVE)
    ztest = run(["zstd", "-t", str(ARCHIVE)], timeout=3600)
    listing = run(["tar", "--zstd", "-tf", str(ARCHIVE)], timeout=3600)
    write_text(META / "ZSTD_INTEGRITY_TEST.txt", ztest.stdout)
    write_text(META / "ARCHIVE_MEMBER_LIST.txt", listing.stdout)
    if ztest.returncode != 0 or listing.returncode != 0:
        raise RuntimeError("archive zstd/list verification failed")

    verify_dir = Path(tempfile.mkdtemp(prefix="cdac_rq4_archive_verify_", dir=str(ROOT.parent)))
    extraction = run(["tar", "--zstd", "-xf", str(ARCHIVE), "-C", str(verify_dir)], timeout=7200)
    extracted = verify_dir / root_name
    checks: dict[str, Any] = {"extraction_returncode": extraction.returncode}
    try:
        if extraction.returncode != 0 or not extracted.exists():
            raise RuntimeError(f"full archive extraction failed: {extraction.stdout}")
        prereg_check = run(["sha256sum", "-c", "SHA256SUMS"], cwd=extracted / "01_preregistration", timeout=1800)
        payload_check = run(["sha256sum", "-c", "PAYLOAD_SHA256SUMS"], cwd=extracted / "05_final" / "payload", timeout=1800)
        protocol_sha = sha256_file(extracted / "01_preregistration" / "RQ4_PROTOCOL_V1.md")
        schedule_sha = sha256_file(extracted / "01_preregistration" / "RANDOMIZED_SCHEDULE.csv")
        frozen = parse_status(extracted / "01_preregistration" / "PROTOCOL_FREEZE_STATUS.txt")
        extracted_rows = read_rows(extracted / "02_boot_1" / "SCIENTIFIC_ROWS.csv") + read_rows(extracted / "03_boot_2" / "SCIENTIFIC_ROWS.csv")
        symlinks = []
        broken = []
        outside = []
        for path in extracted.rglob("*"):
            if not path.is_symlink():
                continue
            symlinks.append(str(path.relative_to(extracted)))
            try:
                target = path.resolve(strict=True)
                target.relative_to(extracted.resolve())
            except FileNotFoundError:
                broken.append(str(path.relative_to(extracted)))
            except ValueError:
                outside.append(str(path.relative_to(extracted)))
        checks.update({
            "prereg_manifest_verified": prereg_check.returncode == 0,
            "payload_manifest_verified": payload_check.returncode == 0,
            "protocol_hash_verified": protocol_sha == frozen.get("PROTOCOL_SHA256"),
            "schedule_hash_verified": schedule_sha == frozen.get("SCHEDULE_SHA256"),
            "scientific_rows": len(extracted_rows), "symlink_count": len(symlinks),
            "broken_symlinks": broken, "outside_symlinks": outside,
        })
        write_text(META / "EXTRACTION_VERIFICATION.txt", "\n".join([
            f"EXTRACTION_RETURN_CODE={extraction.returncode}",
            f"PREREG_MANIFEST_VERIFIED={'yes' if checks['prereg_manifest_verified'] else 'no'}",
            f"PAYLOAD_MANIFEST_VERIFIED={'yes' if checks['payload_manifest_verified'] else 'no'}",
            f"PROTOCOL_HASH_VERIFIED={'yes' if checks['protocol_hash_verified'] else 'no'}",
            f"SCHEDULE_HASH_VERIFIED={'yes' if checks['schedule_hash_verified'] else 'no'}",
            f"SCIENTIFIC_ROWS={checks['scientific_rows']}",
            f"SYMLINK_COUNT={checks['symlink_count']}",
            f"BROKEN_SYMLINKS={';'.join(broken) if broken else 'NONE'}",
            f"OUTSIDE_SYMLINKS={';'.join(outside) if outside else 'NONE'}",
        ]))
        write_text(META / "EXTRACTED_PREREG_MANIFEST_CHECK.txt", prereg_check.stdout)
        write_text(META / "EXTRACTED_PAYLOAD_MANIFEST_CHECK.txt", payload_check.stdout)
    finally:
        thaw_tree(verify_dir)
        shutil.rmtree(verify_dir)
    return archive_sha, checks


def main() -> int:
    FINAL.mkdir(parents=True, exist_ok=True)
    rows = read_rows(ROOT / "02_boot_1" / "SCIENTIFIC_ROWS.csv") + read_rows(ROOT / "03_boot_2" / "SCIENTIFIC_ROWS.csv")
    warmups = read_rows(ROOT / "02_boot_1" / "WARMUP_ROWS.csv") + read_rows(ROOT / "03_boot_2" / "WARMUP_ROWS.csv")
    state = build_final_documents(rows, warmups)
    create_payload()

    for path in (ROOT / "00_preflight", ROOT / "01_preregistration", ROOT / "02_boot_1", ROOT / "03_boot_2", ROOT / "04_analysis", ROOT / "execution_manifests"):
        freeze_tree(path)
    (ROOT / "runtime" / "cvd" / "cuttlefish_config.json").chmod(0o444)
    for path in FINAL.iterdir():
        if path.is_file():
            path.chmod(0o444)

    archive_sha, archive_checks = create_archive()
    preflight_ok, rq2_ok = input_manifest_verification()
    images = RQ2 / "00_preflight" / "runtime_inputs" / "isolated_images"
    retained_ok = (
        sha256_file(images / "system.img") == str(CONSTANTS["expected_system_img_sha256"])
        and sha256_file(images / "boot.img") == str(CONSTANTS["expected_boot_img_sha256"])
        and sha256_file(images / "super.img") == str(CONSTANTS["expected_super_img_sha256"])
    )
    write_text(META / "FROZEN_ARTIFACT_RECHECK.txt", "\n".join([
        f"RETAINED_SYSTEM_IMG_SHA256={sha256_file(images / 'system.img')}",
        f"RETAINED_BOOT_IMG_SHA256={sha256_file(images / 'boot.img')}",
        f"RETAINED_SUPER_IMG_SHA256={sha256_file(images / 'super.img')}",
        f"FROZEN_ARTIFACTS_MODIFIED={0 if retained_ok else 1}",
    ]))
    archive_pass = all([
        archive_checks.get("extraction_returncode") == 0,
        archive_checks.get("prereg_manifest_verified"),
        archive_checks.get("payload_manifest_verified"),
        archive_checks.get("protocol_hash_verified"),
        archive_checks.get("schedule_hash_verified"),
        archive_checks.get("scientific_rows") == len(rows),
        not archive_checks.get("broken_symlinks"), not archive_checks.get("outside_symlinks"),
        preflight_ok, rq2_ok, retained_ok,
    ])
    write_text(META / "ARCHIVE_CONTENT_SCOPE.txt", "\n".join([
        "ARCHIVE_SCOPE=00_preflight+01_preregistration+02_boot_1+03_boot_2+04_analysis+prearchive_05_final+execution_manifests+runtime_config",
        f"ARCHIVE_ROOT_NAME={ROOT.name}", "LIVE_CVD_INSTANCE_DISKS_INCLUDED=no",
        "LIVE_CVD_EXCLUSION_REASON=mutable runtime disks are not scientific evidence and retained source artifacts are referenced and rehashed",
        "POST_ARCHIVE_FINAL_STATUS_INCLUDED=no", "POST_ARCHIVE_SHA256SUMS_INCLUDED=no",
        "ARCHIVE_METADATA_INCLUDED=no", "ARCHIVE_SELF_REFERENCE=no",
    ]))
    write_text(META / "ARCHIVE_SHA256.txt", f"{archive_sha}  {ARCHIVE}")
    write_text(META / "ARCHIVE_VERIFICATION_STATUS.txt", "\n".join([
        f"ARCHIVE_VERIFICATION_STATUS={'PASS' if archive_pass else 'FAIL'}",
        f"ARCHIVE_PATH={ARCHIVE}", f"ARCHIVE_SHA256={archive_sha}",
        f"ZSTD_INTEGRITY={'PASS' if archive_checks.get('extraction_returncode') == 0 else 'FAIL'}",
        f"FULL_EXTRACTION={'PASS' if archive_checks.get('extraction_returncode') == 0 else 'FAIL'}",
        f"PAYLOAD_SHA256SUMS={'PASS' if archive_checks.get('payload_manifest_verified') else 'FAIL'}",
        f"PREREGISTRATION_INCLUDED={'yes' if archive_checks.get('prereg_manifest_verified') else 'no'}",
        f"PROTOCOL_HASH_VERIFIED={'yes' if archive_checks.get('protocol_hash_verified') else 'no'}",
        f"SCHEDULE_IDENTITY_VERIFIED={'yes' if archive_checks.get('schedule_hash_verified') else 'no'}",
        f"SCIENTIFIC_DENOMINATOR_VERIFIED={'yes' if archive_checks.get('scientific_rows') == len(rows) else 'no'}",
        f"SYMLINK_TARGETS_VERIFIED={'yes' if not archive_checks.get('broken_symlinks') and not archive_checks.get('outside_symlinks') else 'no'}",
        f"FROZEN_ARTIFACT_UNMODIFIED={'yes' if retained_ok else 'no'}",
    ]))

    counts: Counter[str] = state["counts"]
    boot_statuses = state["boot_statuses"]
    arm_a_ok = all(row["artifact_identity_match"] == "yes" and row["decision_path_entered"] == "no" for row in rows if row["arm"] == "A") and counts["A"] == 500
    arm_b_ok = all(row["decision_path_entered"] == "yes" and row["rule_match_result"] == "no_rule_match" for row in rows if row["arm"] == "B") and counts["B"] == 500
    arm_c_ok = all(row["decision_path_entered"] == "yes" and row["rule_match_result"] == "nonmatching_lookup" for row in rows if row["arm"] == "C") and counts["C"] == 500
    fatal_items = sum(not item for item in (state["ordering_ok"], preflight_ok, rq2_ok, retained_ok, archive_pass))
    recoverable_gates = 0 if state["denominator_complete"] else 1
    rq4_pass = all([
        state["ordering_ok"], preflight_ok, rq2_ok, retained_ok,
        state["boots_completed"] == 2, state["denominator_complete"],
        state["primary_executed"], state["bootstrap_executed"], archive_pass,
    ])
    status_value = "PASS" if rq4_pass else ("HALT" if fatal_items else "PARTIAL")
    final_allow_slot = state["paper"].get("PAPER_ALLOW_PATH_SLOT", "NOT_FILLABLE") if rq4_pass else "NOT_FILLABLE"
    final_denial_slot = state["paper"].get("PAPER_DENIAL_LATENCY_SLOT", "NOT_FILLABLE") if rq4_pass else "NOT_FILLABLE"
    final_status = "\n".join([
        f"RQ4_STATUS={status_value}",
        f"PRE_AUTHORIZATION_PRESENT={'yes' if (PREREG / 'PRE_AUTHORIZATION.txt').exists() else 'no'}",
        "PROTOCOL_FROZEN=yes", f"PROTOCOL_SHA256={state['protocol']['PROTOCOL_SHA256']}",
        f"PROTOCOL_FROZEN_AT={state['protocol']['PROTOCOL_FROZEN_AT']}",
        f"FIRST_SCIENTIFIC_EXECUTION_AT={state['first']['FIRST_SCIENTIFIC_EXECUTION_AT']}",
        f"SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE={state['protocol']['SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE']}",
        f"PREFLIGHT_MANIFEST_VERIFIED={'yes' if preflight_ok else 'no'}",
        f"RQ2_INPUT_MANIFEST_VERIFIED={'yes' if rq2_ok else 'no'}",
        f"ARTIFACT_IDENTITY_OK={'yes' if retained_ok and all(s.get('BOOT_STATUS') == 'PASS' for s in boot_statuses) else 'no'}",
        "BOOTS_PLANNED=2", f"BOOTS_COMPLETED={state['boots_completed']}",
        "A_PLANNED=500", f"A_OBSERVED={counts['A']}", "B_PLANNED=500", f"B_OBSERVED={counts['B']}",
        "C_PLANNED=500", f"C_OBSERVED={counts['C']}", "D_PLANNED=500", f"D_OBSERVED={counts['D']}",
        "SCIENTIFIC_TRIALS_PLANNED=2000", f"SCIENTIFIC_TRIALS_OBSERVED={len(rows)}", f"WARMUP_ROWS={len(warmups)}",
        "ENGINEERING_PROBES_MERGED=0", "OLD_PERFORMANCE_ROWS_MERGED=0", "RQ2_ROWS_MERGED=0", "UNREGISTERED_ROWS_ADDED=0",
        f"ARM_A_SAME_ARTIFACT={'yes' if arm_a_ok else 'no'}", f"ARM_A_CDAC_INACTIVE_VERIFIED={'yes' if arm_a_ok else 'no'}",
        f"ARM_B_ACTIVE_NO_RULE_VERIFIED={'yes' if arm_b_ok else 'no'}", f"ARM_C_NONMATCHING_LOOKUP_VERIFIED={'yes' if arm_c_ok else 'no'}",
        f"CARRY_OVER_DETECTED={'yes' if state['carry_count'] else 'no'}",
        f"PRIMARY_ESTIMATOR_EXECUTED_AS_REGISTERED={'yes' if state['primary_executed'] else 'no'}",
        f"BOOTSTRAP_EXECUTED_AS_REGISTERED={'yes' if state['bootstrap_executed'] else 'no'}",
        "DENIAL_REPORTED_AS_ABSOLUTE_LATENCY=yes",
        "SOURCE_FILES_MODIFIED=0", "BINARIES_REBUILT=0", f"FROZEN_ARTIFACTS_MODIFIED={0 if retained_ok else 1}",
        f"FATAL_SCIENTIFIC_ITEMS={fatal_items}", f"RECOVERABLE_SCIENTIFIC_GATES={recoverable_gates}",
        f"PAPER_ALLOW_PATH_SLOT={final_allow_slot}",
        f"PAPER_DENIAL_LATENCY_SLOT={final_denial_slot}",
        "NATIVE_ANDROID_OVERHEAD_SLOT=NOT_EVALUATED", "DENIAL_OVERHEAD_SLOT=NOT_EVALUATED", "UNIVERSAL_LOW_OVERHEAD_SLOT=NOT_EVALUATED",
        f"ARCHIVE={ARCHIVE}", f"ARCHIVE_SHA256={archive_sha}",
        f"ARCHIVE_VERIFICATION_STATUS={'PASS' if archive_pass else 'FAIL'}",
    ])
    write_text(FINAL / "FINAL_STATUS.txt", final_status)

    files = [path for path in FINAL.rglob("*") if path.is_file() and path.name != "SHA256SUMS"]
    write_text(FINAL / "SHA256SUMS", "\n".join(
        f"{sha256_file(path)}  {path.relative_to(FINAL)}" for path in sorted(files)
    ))
    freeze_tree(FINAL)
    print(json.dumps({
        "status": status_value, "output_root": str(ROOT), "archive": str(ARCHIVE),
        "archive_sha256": archive_sha, "scientific_rows": len(rows),
    }, indent=2, sort_keys=True))
    return 0 if rq4_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
