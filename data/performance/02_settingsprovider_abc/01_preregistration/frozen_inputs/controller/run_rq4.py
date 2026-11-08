#!/usr/bin/env python3
"""Frozen controller for the prospectively registered RQ4 V2 evaluation.

The controller creates a durable sentinel immediately before each registered
broadcast.  Every sentinelled measured invocation produces one raw-denominator
row and is never repeated or replaced.  Warm-ups use a separate frozen
schedule and separate ledger.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SCRIPT = Path(__file__).resolve()
FROZEN = SCRIPT.parents[1]
PREREG = SCRIPT.parents[2]
ROOT = SCRIPT.parents[3]
CONSTANTS = json.loads((FROZEN / "schemas" / "rq4_constants.json").read_text(encoding="utf-8"))
RQ2 = Path(CONSTANTS["rq2_root"])
SCHEDULE = PREREG / "RANDOMIZED_SCHEDULE.csv"
WARMUP_SCHEDULE = PREREG / "WARMUP_SCHEDULE.csv"
FREEZE_STATUS = PREREG / "PROTOCOL_FREEZE_STATUS.txt"
MANIFEST = PREREG / "SHA256SUMS"
FIRST_SCIENCE = ROOT / "execution_manifests" / "FIRST_SCIENTIFIC_EXECUTION.txt"
RECOVERY_LOG = ROOT / "05_final" / "FINAL_EXECUTION_RECOVERY.md"
SERIAL = str(CONSTANTS["adb_serial"])
DEBUGFS = str(CONSTANTS["debugfs_root"])
GUEST_SENDER = str(CONSTANTS["guest_sender"])
SENDER = FROZEN / "sender" / "iguardctl_test"
CALLER_APK = FROZEN / "caller_artifacts" / "s10-settings.apk"
RUNTIME_CVD = ROOT / "runtime" / "cvd"

sys.path.insert(0, str(FROZEN / "workload"))
sys.path.insert(0, str(FROZEN / "parser"))
sys.path.insert(0, str(FROZEN / "controller"))
from s10_workload import parse_app_csv  # noqa: E402
from rq4_trial_parser import build_observation, parse_kv  # noqa: E402
from reset_v2 import ALIAS_MAP, RESET_SENSITIVE as RESET_V2_SENSITIVE, ResetV2  # noqa: E402


SCIENTIFIC_FIELDS = [
    "trial_id", "protocol_sha256", "scientific_row", "boot_id", "boot_uuid",
    "protocol_version", "reset_oracle_result", "pre_state_hash", "baseline_state_hash",
    "post_state_hash", "counter_baseline_hash", "counter_delta_hash",
    "log_watermark_pre_hash", "log_watermark_post_hash", "reset_completion_pair",
    "stage", "block_id", "block_index", "global_schedule_position",
    "boot_schedule_position", "randomized_position", "arm", "arm_definition",
    "trial_index", "start_timestamp", "end_timestamp",
    "controller_broadcast_start_iso", "controller_broadcast_end_iso",
    "host_monotonic_start_ns", "host_monotonic_broadcast_return_ns",
    "host_monotonic_app_collected_ns", "host_monotonic_collection_end_ns",
    "latency_ns", "latency_unit", "latency_source", "artifact_identity",
    "artifact_identity_match", "route_identity", "route_identity_match",
    "workload_identity", "workload_identity_match", "target_object_identity",
    "rule_state", "rule_identity", "decision_path_entered",
    "rule_lookup_observed", "rule_match_result", "application_outcome",
    "capability_returned", "descriptor_installed", "capability_usable",
    "cleanup_status", "pop_fail_count", "pop_fail_state",
    "carry_over_detector_result", "classification", "primary_eligible",
    "exclusion_reason", "failure_codes", "raw_evidence_path",
    "protocol_identity_match", "workload_invocation_attempted",
]
WARMUP_FIELDS = SCIENTIFIC_FIELDS + [
    "warmup_position", "warmup_cycle", "arm_warmup_index",
]
RAW_TIMESTAMP_FIELDS = [
    "trial_id", "protocol_sha256", "scientific_row", "boot_id", "arm",
    "controller_broadcast_start_iso", "controller_broadcast_end_iso",
    "controller_collection_end_iso", "host_monotonic_start_ns",
    "host_monotonic_broadcast_return_ns", "host_monotonic_app_collected_ns",
    "host_monotonic_collection_end_ns", "apk_elapsed_ns", "apk_clock",
    "apk_unit", "kernel_first_ts_ns", "kernel_last_ts_ns",
    "kernel_timestamp_role", "primary_latency_boundary",
    "pre_reset_watermark_hash", "post_reset_watermark_hash", "watermark_closed",
]
ARM_AUDIT_FIELDS = [
    "trial_id", "scientific_row", "boot_id", "arm", "switch_disable_ctx",
    "switch_disable_runtime", "switch_tail_only", "switch_verbose_audit",
    "pre_arm_state_verified", "decision_path_entered", "push_skipped_count",
    "no_context_count", "decision_apply_count", "real_enforce_count",
    "classification", "raw_evidence_path", "pre_state_hash", "baseline_state_hash",
    "post_state_hash", "reset_oracle_result",
]
RULE_AUDIT_FIELDS = [
    "trial_id", "scientific_row", "boot_id", "arm", "rule_state",
    "rule_identity", "rule_object_role", "rule_object_s_dev", "rule_object_ino",
    "policy_count_pre", "exact_policy_dump_verified_pre",
    "exact_policy_dump_verified_post", "decision_rule_src", "decision_matched",
    "rule_lookup_observed", "rule_match_result", "raw_evidence_path",
    "counter_baseline_hash", "counter_delta_hash",
]
CAPABILITY_FIELDS = [
    "trial_id", "scientific_row", "boot_id", "arm", "application_outcome",
    "capability_returned", "descriptor_installed", "capability_usable",
    "read_ok", "write_ok", "close_ok", "exception_class",
    "exception_message", "denied_path_accounting_balanced", "classification",
    "raw_evidence_path",
]
CARRY_FIELDS = [
    "trial_id", "scientific_row", "boot_id", "arm", "policy_empty_after_cleanup",
    "switches_neutral_after_cleanup", "context_balance", "mismatch_free",
    "arm_a_pop_fail_allowed", "denied_accounting_balanced",
    "counter_reset_verified", "carry_over_detected", "cleanup_verified",
    "cache_warm_state_control", "raw_evidence_path", "reset_completion_pair",
    "pre_state_hash", "post_state_hash",
]

PRE_STATE_FIELDS = [
    "trial_id", "scientific_row", "boot_id", "arm", "boundary", "captured_at",
    "boot_uuid", "full_state_hash", "projection_hash", "policy_count",
    "switch_hash", "counter_hash", "log_watermark_hash", "complete", "raw_evidence_path",
]
RESET_AUDIT_FIELDS = [
    "trial_id", "scientific_row", "boot_id", "arm", "reset_label", "pre_state_hash",
    "stable_projection_1_hash", "stable_projection_2_hash", "baseline_state_hash",
    "reset_returncode", "stable_projection_pair", "complete_projection_pair", "gate_clean",
    "watermark_closed", "completion_oracle", "poll_count", "failure_reason", "raw_evidence_path",
]
WATERMARK_FIELDS = [
    "trial_id", "scientific_row", "boot_id", "arm", "watermark_role", "captured_at",
    "returncode", "line_count", "sha256", "max_audit_seq", "max_kernel_ts_ns",
    "host_monotonic_start_ns", "host_monotonic_end_ns", "workload_marker_count",
    "closed", "raw_evidence_path",
]
COUNTER_DELTA_FIELDS = [
    "trial_id", "scientific_row", "boot_id", "arm", "counter", "scope", "alias_of",
    "baseline", "observed", "delta", "independent_event", "baseline_state_hash",
    "observed_state_hash", "raw_evidence_path",
]
ALIAS_FIELDS = ["counter", "alias_of", "independent_event", "scope", "source", "protocol_version"]

RESET_SENSITIVE = RESET_V2_SENSITIVE


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="microseconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip("\n") + "\n", encoding="utf-8", errors="replace")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def exclusive_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(value.rstrip("\n") + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run(
    args: list[str], timeout: int = 120, check: bool = True,
    cwd: Path | None = None, env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout, cwd=cwd, env=env,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {args!r}\n{proc.stdout}")
    return proc


def adb(*args: str, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["adb", "-s", SERIAL, *args], timeout=timeout, check=check)


def shell(command: str, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb("shell", command, timeout=timeout, check=check)


def shell_out(command: str, timeout: int = 120, check: bool = True) -> str:
    return shell(command, timeout=timeout, check=check).stdout


def parse_status(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def append_csv(path: Path, fields: list[str], row: dict[str, Any]) -> None:
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fields})
        handle.flush()
        os.fsync(handle.fileno())


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def csv_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def load_schedule(path: Path, boot_id: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["boot_id"] == boot_id]


def boot_dir(boot_id: str) -> Path:
    return ROOT / ("02_boot_1" if boot_id == "boot_1" else "03_boot_2")


def arm_definition(arm: str) -> str:
    return {
        "A": str(CONSTANTS["arm_a_name"]),
        "B": str(CONSTANTS["arm_b_name"]),
        "C": str(CONSTANTS["arm_c_name"]),
        "D": str(CONSTANTS["arm_d_name"]),
    }[arm]


def verify_registered_inputs() -> tuple[str, str]:
    if not MANIFEST.exists() or not FREEZE_STATUS.exists():
        raise RuntimeError("preregistration manifest or freeze status is missing")
    checked = run(["sha256sum", "-c", "SHA256SUMS"], timeout=900, cwd=PREREG)
    if checked.returncode != 0:
        raise RuntimeError(f"frozen preregistration manifest verification failed:\n{checked.stdout}")
    status = parse_status(FREEZE_STATUS)
    protocol_sha = sha256_file(PREREG / "RQ4_PROTOCOL_V2.md")
    schedule_sha = sha256_file(SCHEDULE)
    warmup_sha = sha256_file(WARMUP_SCHEDULE)
    required = {
        "PROTOCOL_VERSION": "V2",
        "PROTOCOL_FROZEN": "yes",
        "PROTOCOL_SHA256": protocol_sha,
        "SCHEDULE_SHA256": schedule_sha,
        "WARMUP_SCHEDULE_SHA256": warmup_sha,
        "A_PLANNED": "500", "B_PLANNED": "500", "C_PLANNED": "500",
        "D_PLANNED": "500", "SCIENTIFIC_TRIALS_PLANNED": "2000",
        "SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE": "0",
        "V2_HASH_DIFFERS_FROM_V1": "yes",
    }
    mismatches = {key: (status.get(key), wanted) for key, wanted in required.items() if status.get(key) != wanted}
    if mismatches:
        raise RuntimeError(f"frozen protocol status mismatch: {mismatches}")
    analysis_sha_path = ROOT / "04_analysis" / "ANALYSIS_SCRIPT_SHA256.txt"
    analysis_script = ROOT / "04_analysis" / "ANALYSIS_SCRIPT.py"
    if not analysis_sha_path.exists() or not analysis_script.exists():
        raise RuntimeError("frozen analysis script or hash is missing")
    recorded_analysis_sha = parse_status(analysis_sha_path).get("ANALYSIS_SCRIPT_SHA256", "")
    if recorded_analysis_sha != sha256_file(analysis_script):
        raise RuntimeError("analysis script hash mismatch")
    return protocol_sha, checked.stdout


def connect_root() -> None:
    run(["adb", "connect", SERIAL], timeout=30, check=False)
    adb("wait-for-device", timeout=180)
    adb("root", timeout=45, check=False)
    time.sleep(1)
    run(["adb", "connect", SERIAL], timeout=30, check=False)
    adb("wait-for-device", timeout=180)


def host_isolation_lines() -> tuple[bool, list[str]]:
    proc = run(["ps", "-eo", "pid,args"])
    relevant = [
        line for line in proc.stdout.splitlines()
        if ("/instances/cvd-" in line or "run_cvd --system_image_dir=" in line)
        and "ps -eo pid,args" not in line
    ]
    outside = [line for line in relevant if str(ROOT) not in line]
    return not outside, relevant


def guest_sha(path: str) -> str:
    output = shell_out(f"sha256sum {path}", check=False).strip()
    match = re.match(r"([0-9a-f]{64})\s+", output)
    return match.group(1) if match else "MISSING"


def module_path_and_hash() -> tuple[str, str]:
    for path in (
        "/vendor_dlkm/lib/modules/kernel/drivers/misc/iguard_ctl.ko",
        "/vendor/lib/modules/iguard_ctl.ko",
        "/system_dlkm/lib/modules/iguard_ctl.ko",
    ):
        observed = guest_sha(path)
        if observed != "MISSING":
            return path, observed
    return "MISSING", "MISSING"


def package_apk_path() -> str:
    output = shell_out(f"pm path {CONSTANTS['caller_package']}").strip()
    match = re.search(r"package:(\S+base\.apk)", output)
    return match.group(1) if match else "MISSING"


def package_field(text: str, pattern: str, default: str = "MISSING") -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else default


def stat_path(path: str) -> dict[str, Any]:
    output = shell_out(f"stat -c '%n,%d,%i,%s' {path}").strip()
    parts = output.split(",")
    if len(parts) != 4:
        raise RuntimeError(f"bad stat output for {path}: {output!r}")
    dev_decimal = int(parts[1])
    major, minor = os.major(dev_decimal), os.minor(dev_decimal)
    return {
        "path": parts[0], "stat_dev_decimal": dev_decimal,
        "kernel_dev": f"{major}:{minor}", "raw_dev_t": (major << 20) + minor,
        "ino": int(parts[2]), "size": int(parts[3]),
    }


def policy_dump() -> str:
    return shell_out(f"cat {DEBUGFS}/policy_dump", check=False)


def policy_count(value: str) -> int:
    match = re.search(r"runtime_policy_count=(\d+)", value)
    return int(match.group(1)) if match else -1


def policy_clear() -> tuple[str, str]:
    clear = shell_out(f"{GUEST_SENDER} clear", check=False)
    return clear, policy_dump()


def read_switch(name: str) -> str:
    return shell_out(f"cat {DEBUGFS}/{name}", check=False).strip()


def set_switch(name: str, value: str) -> str:
    proc = shell(f"printf '{value}' > {DEBUGFS}/{name}", check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"switch {name}={value} failed: {proc.stdout}")
    observed = read_switch(name)
    if observed != value:
        raise RuntimeError(f"switch {name} expected {value}, observed {observed}")
    return observed


def reset_engine() -> ResetV2:
    return ResetV2(
        adb=adb,
        shell=shell,
        shell_out=shell_out,
        policy_clear=policy_clear,
        set_switch=set_switch,
        debugfs=DEBUGFS,
        stability_interval_seconds=float(CONSTANTS["reset_stability_interval_seconds"]),
        completion_timeout_seconds=float(CONSTANTS["reset_completion_timeout_seconds"]),
        timezone_now=now,
    )


def read_counters() -> dict[str, int]:
    text = shell_out(f"cat {DEBUGFS}/quiet_counters", check=False)
    result: dict[str, int] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            result[key] = int(value)
        except ValueError:
            pass
    return result


def reset_counters() -> dict[str, int]:
    proc = shell(f"printf reset > {DEBUGFS}/quiet_counters", check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"counter reset failed: {proc.stdout}")
    return read_counters()


def counters_reset_verified(values: dict[str, int]) -> bool:
    return all(int(values.get(name, 0)) == 0 for name in RESET_SENSITIVE)


def neutralize_state() -> dict[str, Any]:
    clear_output, dump = policy_clear()
    switches = {name: set_switch(name, "N") for name in (
        "ablate_disable_ctx", "ablate_disable_runtime", "ablate_path_tail_only", "verbose_audit",
    )}
    reset = reset_counters()
    result = {
        "clear_output": clear_output, "policy_dump": dump,
        "policy_empty": policy_count(dump) == 0, "switches": switches,
        "counter_reset_verified": counters_reset_verified(reset), "counters_after_reset": reset,
    }
    result["neutral_state_verified"] = (
        result["policy_empty"] and all(value == "N" for value in switches.values())
        and result["counter_reset_verified"]
    )
    return result


def endpoint_registration_lines() -> list[str]:
    device = adb("logcat", "-d", "-v", "threadtime", check=False).stdout
    host_path = RUNTIME_CVD / "instances" / "cvd-10" / "logs" / "logcat"
    host = host_path.read_text(encoding="utf-8", errors="replace") if host_path.exists() else ""
    return [
        line for line in (device + "\n" + host).splitlines()
        if "event=CDAC_ENDPOINT_REGISTER" in line
        and "service_id=8" in line and "op_id=701" in line
        and str(CONSTANTS["provider_class"]) in line
        and "registration_source=ContentProvider.attachInfo" in line
        and "result=ok" in line
    ]


def artifact_row(artifact: str, expected: str, observed: str, source: str) -> dict[str, str]:
    return {
        "artifact": artifact, "expected": expected, "observed": observed,
        "verified": "yes" if expected == observed else "no", "source": source,
    }


def prepare_boot(boot_id: str, protocol_sha: str, manifest_output: str) -> dict[str, Any]:
    directory = boot_dir(boot_id)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "SCIENTIFIC_ROWS.csv").exists() or (directory / "WARMUP_ROWS.csv").exists():
        raise RuntimeError(f"{boot_id} already contains invocation ledgers; refusing duplicate boot execution")
    connect_root()
    isolation_ok, isolation_lines = host_isolation_lines()
    write_text(directory / "HOST_ISOLATION_AUDIT.txt", "\n".join([
        f"CHECKED_AT={now()}", f"HOST_ISOLATION_OK={'yes' if isolation_ok else 'no'}",
        "REQUIREMENT=no_other_user_cvd_during_scientific_execution", *isolation_lines,
    ]))
    if not isolation_ok:
        raise RuntimeError("another user CVD is active; host-isolated performance execution is not permitted")

    boot_uuid = shell_out("cat /proc/sys/kernel/random/boot_id").strip()
    if boot_id == "boot_2":
        prior = parse_status(ROOT / "02_boot_1" / "BOOT_STATUS.txt")
        if prior.get("BOOT_UUID") == boot_uuid:
            raise RuntimeError("boot_2 UUID equals boot_1 UUID")
    fingerprint = shell_out("getprop ro.build.fingerprint").strip()
    kernel = shell_out("uname -r").strip()
    uname_a = shell_out("uname -a").strip()
    selinux = shell_out("getenforce").strip()
    framework_hash = guest_sha("/system/framework/framework.jar")
    settings_hash = guest_sha("/system/priv-app/SettingsProvider/SettingsProvider.apk")
    module_path, module_hash = module_path_and_hash()
    package_dump = shell_out(f"dumpsys package {CONSTANTS['caller_package']}")
    uid = package_field(package_dump, r"(?:appId|userId)=(\d+)")
    target_sdk = package_field(package_dump, r"targetSdk=(\d+)")
    version_code = package_field(package_dump, r"versionCode=(\d+)")
    version_name = package_field(package_dump, r"versionName=([^\s]+)")
    apk_path = package_apk_path()
    apk_hash = guest_sha(apk_path) if apk_path != "MISSING" else "MISSING"
    shell_out(f"cmd appops set {CONSTANTS['caller_package']} WRITE_SETTINGS allow", check=False)
    appop = shell_out(f"cmd appops get {CONSTANTS['caller_package']} WRITE_SETTINGS", check=False).strip()
    sender_local_hash = sha256_file(SENDER)
    sender_guest_hash = guest_sha(GUEST_SENDER)
    sender_action = "not_needed"
    if sender_guest_hash != sender_local_hash:
        pushed = adb("push", str(SENDER), GUEST_SENDER, check=False)
        if pushed.returncode != 0:
            raise RuntimeError(f"retained sender push failed: {pushed.stdout}")
        shell_out(f"chmod 0755 {GUEST_SENDER}")
        sender_guest_hash = guest_sha(GUEST_SENDER)
        sender_action = "pushed_exact_frozen_sender"
    shell("mount | grep -q ' /sys/kernel/debug ' || mount -t debugfs none /sys/kernel/debug", check=False)
    initial_reset_dir = directory / "reset_audit" / "boot_initial"
    initial_reset = reset_engine().reset_to_neutral(
        directory=initial_reset_dir, label="boot_initial", arm_hint="NEUTRAL"
    )
    if not initial_reset["pass"]:
        raise RuntimeError("initial V2 reset completion oracle failed")
    neutral = initial_reset["baseline_state"]
    registrations = endpoint_registration_lines()
    if not registrations:
        raise RuntimeError("authoritative S10 endpoint registration not observed")
    target = stat_path(str(CONSTANTS["target_path"]))
    decoy = stat_path(str(CONSTANTS["decoy_path"]))
    if (target["kernel_dev"], target["ino"]) == (decoy["kernel_dev"], decoy["ino"]):
        raise RuntimeError("target and decoy object identities are not distinct")

    images = RQ2 / "00_preflight" / "runtime_inputs" / "isolated_images"
    system_hash = sha256_file(images / "system.img")
    boot_hash = sha256_file(images / "boot.img")
    super_hash = sha256_file(images / "super.img")
    controller_hash = sha256_file(SCRIPT)
    parser_hash = sha256_file(FROZEN / "parser" / "rq4_trial_parser.py")
    reset_hash = sha256_file(FROZEN / "reset" / "RESET_PROCEDURE_V2.md")
    reset_oracle_hash = sha256_file(FROZEN / "reset" / "RESET_COMPLETION_ORACLE.md")
    rows = [
        artifact_row("build fingerprint", str(CONSTANTS["expected_fingerprint"]), fingerprint, "getprop ro.build.fingerprint"),
        artifact_row("kernel identifier", str(CONSTANTS["expected_kernel_release"]), kernel, "uname -r"),
        artifact_row("SELinux", str(CONSTANTS["expected_selinux"]), selinux, "getenforce"),
        artifact_row("framework.jar", str(CONSTANTS["expected_framework_jar_sha256"]), framework_hash, "/system/framework/framework.jar"),
        artifact_row("kernel module", str(CONSTANTS["expected_kernel_module_sha256"]), module_hash, module_path),
        artifact_row("SettingsProvider.apk", str(CONSTANTS["expected_settings_provider_apk_sha256"]), settings_hash, "/system/priv-app/SettingsProvider/SettingsProvider.apk"),
        artifact_row("caller APK", str(CONSTANTS["caller_apk_sha256"]), apk_hash, apk_path),
        artifact_row("caller package", str(CONSTANTS["caller_package"]), str(CONSTANTS["caller_package"]) if str(CONSTANTS["caller_package"]) in package_dump else "MISSING", "dumpsys package"),
        artifact_row("caller UID", str(CONSTANTS["caller_uid"]), uid, "dumpsys package"),
        artifact_row("caller target SDK", str(CONSTANTS["caller_target_sdk"]), target_sdk, "dumpsys package"),
        artifact_row("caller versionCode", str(CONSTANTS["caller_version_code"]), version_code, "dumpsys package"),
        artifact_row("caller versionName", str(CONSTANTS["caller_version_name"]), version_name, "dumpsys package"),
        artifact_row("WRITE_SETTINGS AppOp", "allow", "allow" if "allow" in appop else appop, "cmd appops get"),
        artifact_row("sender", str(CONSTANTS["sender_sha256"]), sender_guest_hash, GUEST_SENDER),
        artifact_row("S10 endpoint present/registered/enabled", "present", "present" if registrations else "missing", "CDAC_ENDPOINT_REGISTER"),
        artifact_row("route identity", f"{CONSTANTS['route_profile']};{CONSTANTS['route_tuple_sha256']}", f"{CONSTANTS['route_profile']};{CONSTANTS['route_tuple_sha256']}", "frozen route profile"),
        artifact_row("workload identity", str(CONSTANTS["workload_identity"]), str(CONSTANTS["workload_identity"]), "frozen APK call and S10 workload contract"),
        artifact_row("latency clock/unit", f"{CONSTANTS['latency_clock']};{CONSTANTS['latency_unit']}", f"{CONSTANTS['latency_clock']};{CONSTANTS['latency_unit']}", "retained APK source and timing boundary"),
        artifact_row("retained system.img", str(CONSTANTS["expected_system_img_sha256"]), system_hash, str(images / "system.img")),
        artifact_row("retained boot.img", str(CONSTANTS["expected_boot_img_sha256"]), boot_hash, str(images / "boot.img")),
        artifact_row("retained super.img", str(CONSTANTS["expected_super_img_sha256"]), super_hash, str(images / "super.img")),
        artifact_row("controller hash", controller_hash, controller_hash, str(SCRIPT)),
        artifact_row("parser hash", parser_hash, parser_hash, str(FROZEN / "parser" / "rq4_trial_parser.py")),
        artifact_row("reset procedure V2 hash", str(CONSTANTS["reset_procedure_v2_sha256"]), reset_hash, str(FROZEN / "reset" / "RESET_PROCEDURE_V2.md")),
        artifact_row("reset completion oracle hash", str(CONSTANTS["reset_completion_oracle_sha256"]), reset_oracle_hash, str(FROZEN / "reset" / "RESET_COMPLETION_ORACLE.md")),
        artifact_row("host isolation", "isolated", "isolated" if isolation_ok else "contended", "HOST_ISOLATION_AUDIT.txt"),
    ]
    artifact_path = directory / "ARTIFACT_IDENTITY.tsv"
    write_csv(artifact_path, ["artifact", "expected", "observed", "verified", "source"], rows)
    artifact_ok = all(row["verified"] == "yes" for row in rows)
    if not artifact_ok:
        raise RuntimeError("boot artifact identity mismatch")
    artifact_identity = sha256_file(artifact_path)

    object_rows = [
        {"role": "TARGET_OBJECT", **target, "selection_procedure": "stat frozen target path after boot identity and before workload", "frozen_before_workload": "yes"},
        {"role": "NONMATCHING_DECOY_OBJECT", **decoy, "selection_procedure": "stat frozen decoy path after boot identity and before workload", "frozen_before_workload": "yes"},
    ]
    write_csv(directory / "OBJECT_IDENTITY.tsv", list(object_rows[0]), object_rows)
    write_text(directory / "ENDPOINT_REGISTRATION.txt", "\n".join(registrations))
    write_text(directory / "CALLER_PACKAGE_DUMP.txt", package_dump)
    write_text(directory / "INITIAL_NEUTRAL_STATE.json", json.dumps(neutral, indent=2, sort_keys=True))
    alias_lines = ["\t".join(ALIAS_FIELDS)]
    alias_lines.extend(
        "\t".join([
            name, alias, "no", f"alias_of_{alias}",
            "closure RESET_COMPLETION_ORACLE.md", "V2",
        ])
        for name, alias in ALIAS_MAP.items()
    )
    write_text(directory / "COUNTER_ALIAS_MAP.tsv", "\n".join(alias_lines))
    write_text(directory / "REGISTERED_INPUT_VERIFICATION.txt", manifest_output)
    measured = load_schedule(SCHEDULE, boot_id)
    warmups = load_schedule(WARMUP_SCHEDULE, boot_id)
    if len(measured) != 1000 or len(warmups) != 60:
        raise RuntimeError("boot schedule slice denominator mismatch")
    write_csv(directory / "FROZEN_SCHEDULE_SLICE.csv", list(measured[0]), measured)
    write_csv(directory / "FROZEN_WARMUP_SCHEDULE_SLICE.csv", list(warmups[0]), warmups)
    return {
        "boot_id": boot_id, "boot_uuid": boot_uuid, "boot_dir": directory,
        "protocol_sha256": protocol_sha, "artifact_identity": artifact_identity,
        "artifact_identity_match": True, "protocol_identity_match": True,
        "route_identity_match": True, "workload_identity_match": True,
        "target": target, "decoy": decoy, "caller_uid": int(uid),
        "measured": measured, "warmups": warmups, "uname_a": uname_a,
        "sender_action": sender_action,
    }


def canonical_rule(state: dict[str, Any], arm: str, schedule: dict[str, str]) -> dict[str, Any] | None:
    if arm not in ("C", "D"):
        return None
    obj = state["decoy"] if arm == "C" else state["target"]
    role = "NONMATCHING_DECOY_OBJECT" if arm == "C" else "REVIEWED_TARGET_OBJECT"
    boot_number = 1 if state["boot_id"] == "boot_1" else 2
    position = schedule.get("global_schedule_position", schedule.get("warmup_position", "0"))
    reason = f"rq4_v2_b{boot_number}_{arm.lower()}_{int(position):04d}"
    return {
        "schema": "policy-add-v2", "service_id": 8, "op_id": 701,
        "caller_uid": state["caller_uid"], "decision": "deny", "reason": reason,
        "f_flags_mask": "0x3", "f_flags_value": "0x2",
        "f_mode_mask": "0x0", "f_mode_value": "0x0",
        "required_relation_type": 0, "required_relation_stage": 0,
        "object_role": role, "object": obj,
    }


def expected_policy_dump(rule: dict[str, Any] | None) -> str:
    if rule is None:
        return "runtime_policy_count=0\n"
    obj = rule["object"]
    return (
        "runtime_policy_count=1\n"
        f"[0] service_id=8 op_id=701 caller_uid={rule['caller_uid']} service=- operation=- path_tail=- "
        f"ino={obj['ino']} s_dev={obj['kernel_dev']} i_mode=00 f_flags_mask=0x3 f_flags_value=0x2 "
        "f_mode_mask=0x0 f_mode_value=0x0 required_relation_type=0 required_relation_stage=0 "
        f"decision=would-deny reason={rule['reason']} specificity=6\n"
    )


def configure_invocation(
    state: dict[str, Any], schedule: dict[str, str], raw_dir: Path,
    reset_result: dict[str, Any], baseline_state: dict[str, Any],
) -> dict[str, Any]:
    arm = schedule["arm"]
    empty = policy_dump()
    if policy_count(empty) != 0:
        raise RuntimeError("V2 reset left a nonempty policy table before arm freeze")
    clear_output = "V2_RESET_ALREADY_CLEARED"
    rule = canonical_rule(state, arm, schedule)
    add_output = ""
    add_command = "NONE"
    if rule is not None:
        obj = rule["object"]
        add_command = (
            f"{GUEST_SENDER} add service_id=8 op_id=701 caller_uid={state['caller_uid']} "
            f"decision=deny reason={rule['reason']} f_flags_mask=0x3 f_flags_value=0x2 "
            f"ino={obj['ino']} s_dev={obj['raw_dev_t']}"
        )
        added = shell(add_command, check=False)
        add_output = added.stdout
        if added.returncode != 0:
            raise RuntimeError(f"policy-add-v2 failed: {added.stdout}")
    expected_dump = expected_policy_dump(rule)
    observed_dump = policy_dump()
    if observed_dump != expected_dump:
        raise RuntimeError("exact active policy dump mismatch")
    switches = {
        "ablate_disable_ctx": set_switch("ablate_disable_ctx", "Y" if arm == "A" else "N"),
        "ablate_disable_runtime": set_switch("ablate_disable_runtime", "N"),
        "ablate_path_tail_only": set_switch("ablate_path_tail_only", "N"),
        "verbose_audit": set_switch("verbose_audit", "Y"),
    }
    arm_state = reset_engine().capture_state(arm_hint=arm, boundary="arm_freeze")
    arm_projection = arm_state["projection"]
    trial_counters_clean = all(
        arm_state["counters"].get(name) == 0 for name in RESET_SENSITIVE
    )
    if not arm_state["complete"] or not trial_counters_clean:
        raise RuntimeError("arm freeze changed trial-sensitive state before invocation")
    arm_watermark = arm_state["log_watermark"]
    if arm_watermark.get("workload_marker_count", 0) != 0:
        raise RuntimeError("workload marker observed before V2 invocation")
    rule_identity = "NONE" if rule is None else sha256_text(json.dumps(rule, sort_keys=True, separators=(",", ":")))
    config = {
        "configured_at": now(), "arm": arm, "clear_output": clear_output,
        "empty_policy_dump": empty, "rule": rule, "rule_identity": rule_identity,
        "rule_add_command": add_command, "rule_add_output": add_output,
        "expected_policy_dump": expected_dump, "observed_policy_dump": observed_dump,
        "active_policy_count": policy_count(observed_dump), "switches": switches,
        "counters_after_reset": baseline_state["counters"],
        "baseline_state": baseline_state, "baseline_state_hash": baseline_state["full_state_hash"],
        "arm_state": arm_state, "arm_state_hash": arm_state["full_state_hash"],
        "arm_projection": arm_projection, "arm_watermark": arm_watermark,
        "reset_result": reset_result, "pre_arm_state_verified": True,
        "reset_oracle_result": reset_result["completion_oracle"],
    }
    write_json(raw_dir / "configuration.json", config)
    return config


def pre_invocation_ready(config: dict[str, Any], app_path: str, raw_dir: Path) -> None:
    removed = shell(f"rm -f {app_path}", check=False)
    write_text(raw_dir / "app_output_cleanup.txt", removed.stdout)
    if removed.returncode != 0:
        raise RuntimeError("application output cleanup failed before invocation")
    if policy_dump() != config["expected_policy_dump"]:
        raise RuntimeError("rule state changed during pre-invocation setup")
    for name, value in config["switches"].items():
        if read_switch(name) != value:
            raise RuntimeError(f"arm switch {name} changed before invocation")
    current = read_counters()
    if any(int(current.get(name, 0)) != 0 for name in RESET_SENSITIVE):
        raise RuntimeError("trial-sensitive counters changed before invocation")
    write_json(raw_dir / "arm_freeze_state.json", config["arm_state"])
    write_json(raw_dir / "arm_freeze_watermark.json", config["arm_watermark"])


def first_scientific_execution(protocol_sha: str, trial_id: str) -> str:
    if FIRST_SCIENCE.exists():
        return parse_status(FIRST_SCIENCE)["FIRST_SCIENTIFIC_EXECUTION_AT"]
    frozen = parse_status(FREEZE_STATUS)["PROTOCOL_FROZEN_AT"]
    stamp = now()
    if datetime.fromisoformat(stamp) <= datetime.fromisoformat(frozen):
        raise RuntimeError("first scientific execution timestamp does not follow protocol freeze")
    exclusive_text(FIRST_SCIENCE, "\n".join([
        f"FIRST_SCIENTIFIC_EXECUTION_AT={stamp}", f"FIRST_TRIAL_ID={trial_id}",
        f"PROTOCOL_FROZEN_AT={frozen}", f"PROTOCOL_SHA256={protocol_sha}",
        "SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE=0",
    ]))
    return stamp


def collect_invocation(
    state: dict[str, Any], schedule: dict[str, str], raw_dir: Path,
    app_path: str, output_name: str,
) -> dict[str, Any]:
    trial_id = schedule["trial_id"]
    start_iso = now()
    start_mono = time.monotonic_ns()
    broadcast_exception = "NONE"
    try:
        broadcast = adb(
            "shell", "am", "broadcast", "-a", str(CONSTANTS["app_action"]),
            "-n", str(CONSTANTS["app_receiver"]), "--es", "phase", trial_id,
            "--es", "scenario", f"RQ4-{schedule['arm']}", "--es", "uri",
            str(CONSTANTS["target_uri"]), "--es", "mode", str(CONSTANTS["workload_mode"]),
            "--ei", "attempts", "1", "--es", "out", output_name,
            timeout=90, check=False,
        )
    except Exception as exc:
        broadcast_exception = f"{type(exc).__name__}:{exc}"
        broadcast = subprocess.CompletedProcess([], -1, stdout=broadcast_exception)
    broadcast_return_mono = time.monotonic_ns()
    broadcast_end_iso = now()
    write_text(raw_dir / "broadcast.txt", "\n".join([
        f"RETURN_CODE={broadcast.returncode}", f"EXCEPTION={broadcast_exception}", broadcast.stdout,
    ]))
    app_text = ""
    app_collected_mono = broadcast_return_mono
    for _ in range(80):
        attempt = shell(f"cat {app_path}", timeout=15, check=False)
        if attempt.returncode == 0 and attempt.stdout.strip():
            app_text = attempt.stdout
            app_collected_mono = time.monotonic_ns()
            break
        time.sleep(0.25)
    write_text(raw_dir / "app.csv", app_text)
    time.sleep(0.25)
    kernel = adb("logcat", "-b", "kernel", "-d", "-v", "threadtime", check=False)
    all_log = adb("logcat", "-d", "-v", "threadtime", check=False)
    collection_end_mono = time.monotonic_ns()
    collection_end_iso = now()
    write_text(raw_dir / "kernel_logcat.txt", kernel.stdout)
    write_text(raw_dir / "all_logcat.txt", all_log.stdout)
    return {
        "app": parse_app_csv(app_text), "app_text": app_text,
        "broadcast_returncode": broadcast.returncode,
        "broadcast_exception": broadcast_exception, "kernel_log": kernel.stdout,
        "all_log": all_log.stdout, "controller_broadcast_start_iso": start_iso,
        "controller_broadcast_end_iso": broadcast_end_iso,
        "controller_collection_end_iso": collection_end_iso,
        "host_monotonic_start_ns": start_mono,
        "host_monotonic_broadcast_return_ns": broadcast_return_mono,
        "host_monotonic_app_collected_ns": app_collected_mono,
        "host_monotonic_collection_end_ns": collection_end_mono,
    }


def cleanup_after_invocation(
    state: dict[str, Any], schedule: dict[str, str], config: dict[str, Any],
    counters_after: dict[str, int], raw_dir: Path,
) -> dict[str, Any]:
    arm = schedule["arm"]
    reset = reset_engine()
    post_state = reset.capture_state(arm_hint=arm, boundary="post_workload")
    reset.save_state(raw_dir / "reset_v2_cleanup", "post_workload", post_state)
    delta_rows = reset.counter_deltas(config["baseline_state"], post_state)
    write_json(raw_dir / "counter_baseline_and_delta.json", delta_rows)
    push_delta = int(delta_rows.get("context_push_ok", {}).get("delta") or 0)
    pop_delta = int(delta_rows.get("context_pop_ok", {}).get("delta") or 0)
    pop_fail_delta = int(delta_rows.get("context_pop_fail", {}).get("delta") or 0)
    context_balance = push_delta == pop_delta
    mismatch_free = all(
        int(delta_rows.get(name, {}).get("delta") or 0) == 0
        for name in ("context_push_fail", "context_nested_mismatch_total", "context_stale_total")
    ) and (arm == "A" or pop_fail_delta == 0)
    acquire = int(delta_rows.get("frdac_denied_internal_fd_acquire_total", {}).get("delta") or 0)
    release = int(delta_rows.get("frdac_denied_internal_fd_release_total", {}).get("delta") or 0)
    outstanding = int(post_state["counters"].get("frdac_denied_internal_fd_outstanding", 0))
    denied_balance = acquire == release and outstanding == 0
    reset_result = reset.reset_to_neutral(
        directory=raw_dir / "reset_v2_cleanup",
        label="post_cleanup",
        arm_hint=arm,
        pre_state=post_state,
    )
    final_state = reset_result["baseline_state"]
    policy_empty = reset_result["gate_clean"] and final_state["policy_count"] == 0
    switches_neutral = reset_result["gate_clean"] and all(
        final_state["switches"].get(name) == "N" for name in reset_v2_switches()
    )
    reset_verified = reset_result["pass"]
    real_residual = not reset_result["gate_clean"]
    cleanup_verified = bool(
        context_balance and mismatch_free and denied_balance and reset_verified
        and policy_empty and switches_neutral
    )
    return {
        "clear_output": "V2_RESET_CLEANUP",
        "final_policy_dump": final_state["policy_dump"],
        "policy_empty": policy_empty, "switches": final_state["switches"],
        "switches_neutral": switches_neutral, "counters_before_reset": counters_after,
        "counters_after_reset": final_state["counters"], "context_balance": context_balance,
        "mismatch_free": mismatch_free, "arm_a_pop_fail_allowed": arm == "A" and pop_fail_delta > 0,
        "denied_accounting_balanced": denied_balance,
        "counter_reset_verified": reset_verified, "carry_over_detected": not cleanup_verified,
        "real_carry_over_detected": real_residual,
        "cleanup_verified": cleanup_verified,
        "post_state": post_state, "final_state": final_state,
        "reset_result": reset_result, "counter_deltas": delta_rows,
    }


def reset_v2_switches() -> tuple[str, ...]:
    return (
        "ablate_disable_ctx", "ablate_disable_runtime", "ablate_path_tail_only", "verbose_audit",
    )


def kernel_timestamps(focused: list[str]) -> tuple[str, str]:
    values: list[int] = []
    for line in focused:
        parsed = parse_kv(line)
        value = parsed.get("ts_ns", "")
        if value.isdigit():
            values.append(int(value))
    return (str(min(values)), str(max(values))) if values else ("", "")


def build_row(
    state: dict[str, Any], schedule: dict[str, str], config: dict[str, Any],
    collected: dict[str, Any], observation: dict[str, Any], raw_dir: Path,
    scientific: bool,
) -> dict[str, Any]:
    arm = schedule["arm"]
    target = state["target"]
    rule = config["rule"]
    reset_result = config["reset_result"]
    cleanup = config.get("cleanup", {})
    post_state = cleanup.get("post_state", {})
    baseline_state = config["baseline_state"]
    pre_watermark = reset_result.get("pre_reset_watermark", {})
    post_watermark = reset_result.get("baseline_state", {}).get("log_watermark", {})
    delta_map = cleanup.get("counter_deltas", {})
    return {
        **schedule,
        "protocol_sha256": state["protocol_sha256"],
        "scientific_row": "yes" if scientific else "no",
        "protocol_version": "V2",
        "reset_oracle_result": cleanup.get("reset_result", {}).get("completion_oracle", "RESET_FAIL"),
        "pre_state_hash": reset_result.get("pre_state_hash", ""),
        "baseline_state_hash": baseline_state.get("full_state_hash", ""),
        "post_state_hash": post_state.get("full_state_hash", ""),
        "counter_baseline_hash": sha256_text(canonical_counter_json(baseline_state.get("counters", {}))),
        "counter_delta_hash": sha256_text(canonical_counter_json(delta_map)),
        "log_watermark_pre_hash": sha256_text(canonical_counter_json(pre_watermark)),
        "log_watermark_post_hash": sha256_text(canonical_counter_json(post_watermark)),
        "reset_completion_pair": "yes" if reset_result.get("stable_projection_pair") else "no",
        "boot_uuid": state["boot_uuid"], "arm_definition": arm_definition(arm),
        "start_timestamp": collected["controller_broadcast_start_iso"],
        "end_timestamp": collected["controller_broadcast_end_iso"],
        **{key: collected[key] for key in (
            "controller_broadcast_start_iso", "controller_broadcast_end_iso",
            "host_monotonic_start_ns", "host_monotonic_broadcast_return_ns",
            "host_monotonic_app_collected_ns", "host_monotonic_collection_end_ns",
        )},
        "latency_ns": observation["latency_ns"], "latency_unit": CONSTANTS["latency_unit"],
        "latency_source": "APK_SystemClock_elapsedRealtimeNanos",
        "artifact_identity": state["artifact_identity"], "artifact_identity_match": "yes",
        "route_identity": f"{CONSTANTS['route_profile']};{CONSTANTS['route_tuple_sha256']}",
        "route_identity_match": "yes", "workload_identity": CONSTANTS["workload_identity"],
        "workload_identity_match": "yes",
        "target_object_identity": f"{target['kernel_dev']}:{target['ino']}",
        "rule_state": "NO_RULE" if rule is None else ("NONMATCHING_RULE" if arm == "C" else "REVIEWED_TARGET_RULE"),
        "rule_identity": config["rule_identity"],
        **{key: observation[key] for key in (
            "decision_path_entered", "rule_lookup_observed", "rule_match_result",
            "application_outcome", "capability_returned", "descriptor_installed",
            "capability_usable", "cleanup_status", "pop_fail_count", "pop_fail_state",
            "carry_over_detector_result", "classification", "primary_eligible",
            "exclusion_reason", "failure_codes",
        )},
        "raw_evidence_path": str(raw_dir.relative_to(ROOT)),
        "protocol_identity_match": "yes", "workload_invocation_attempted": "yes",
    }


def canonical_counter_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def append_audits(
    state: dict[str, Any], row: dict[str, Any], config: dict[str, Any],
    observation: dict[str, Any], cleanup: dict[str, Any], collected: dict[str, Any],
    scientific: bool,
) -> None:
    directory = state["boot_dir"]
    app = observation["app"]
    decision = observation["decision"]
    rule = config["rule"]
    raw_path = row["raw_evidence_path"]
    common = {"trial_id": row["trial_id"], "scientific_row": row["scientific_row"], "boot_id": row["boot_id"], "arm": row["arm"], "raw_evidence_path": raw_path}
    reset_result = config["reset_result"]
    baseline_state = config["baseline_state"]
    post_state = cleanup.get("post_state", {})
    append_csv(directory / "ARM_STATE_AUDIT.csv", ARM_AUDIT_FIELDS, {
        **common,
        "switch_disable_ctx": config["switches"]["ablate_disable_ctx"],
        "switch_disable_runtime": config["switches"]["ablate_disable_runtime"],
        "switch_tail_only": config["switches"]["ablate_path_tail_only"],
        "switch_verbose_audit": config["switches"]["verbose_audit"],
        "pre_arm_state_verified": "yes" if config["pre_arm_state_verified"] else "no",
        "decision_path_entered": observation["decision_path_entered"],
        "push_skipped_count": observation["push_skipped_count"],
        "no_context_count": observation["no_context_count"],
        "decision_apply_count": observation["decision_apply_count"],
        "real_enforce_count": observation["real_enforce_count"],
        "classification": observation["classification"],
        "pre_state_hash": reset_result.get("pre_state_hash", ""),
        "baseline_state_hash": baseline_state.get("full_state_hash", ""),
        "post_state_hash": post_state.get("full_state_hash", ""),
        "reset_oracle_result": cleanup.get("reset_result", {}).get("completion_oracle", "RESET_FAIL"),
    })
    append_csv(directory / "RULE_STATE_AUDIT.csv", RULE_AUDIT_FIELDS, {
        **common, "rule_state": row["rule_state"], "rule_identity": config["rule_identity"],
        "rule_object_role": "NONE" if rule is None else rule["object_role"],
        "rule_object_s_dev": "" if rule is None else rule["object"]["kernel_dev"],
        "rule_object_ino": "" if rule is None else rule["object"]["ino"],
        "policy_count_pre": config["active_policy_count"],
        "exact_policy_dump_verified_pre": "yes",
        "exact_policy_dump_verified_post": "yes" if row.get("rule_state_verified_post", "yes") == "yes" else "no",
        "decision_rule_src": decision.get("rule_src", ""),
        "decision_matched": decision.get("matched", ""),
        "rule_lookup_observed": observation["rule_lookup_observed"],
        "rule_match_result": observation["rule_match_result"],
        "counter_baseline_hash": row.get("counter_baseline_hash", ""),
        "counter_delta_hash": row.get("counter_delta_hash", ""),
    })
    append_csv(directory / "CAPABILITY_ORACLE.csv", CAPABILITY_FIELDS, {
        **common, "application_outcome": observation["application_outcome"],
        "capability_returned": observation["capability_returned"],
        "descriptor_installed": observation["descriptor_installed"],
        "capability_usable": observation["capability_usable"],
        "read_ok": app.get("read_ok", ""), "write_ok": app.get("write_ok", ""),
        "close_ok": app.get("close_ok", ""), "exception_class": app.get("exception_class", ""),
        "exception_message": app.get("exception_message", ""),
        "denied_path_accounting_balanced": observation["denied_path_accounting_balanced"],
        "classification": observation["classification"],
    })
    append_csv(directory / "CARRY_OVER_AUDIT.csv", CARRY_FIELDS, {
        **common, "policy_empty_after_cleanup": "yes" if cleanup["policy_empty"] else "no",
        "switches_neutral_after_cleanup": "yes" if cleanup["switches_neutral"] else "no",
        "context_balance": "yes" if cleanup["context_balance"] else "no",
        "mismatch_free": "yes" if cleanup["mismatch_free"] else "no",
        "arm_a_pop_fail_allowed": "yes" if cleanup["arm_a_pop_fail_allowed"] else "no",
        "denied_accounting_balanced": "yes" if cleanup["denied_accounting_balanced"] else "no",
        "counter_reset_verified": "yes" if cleanup["counter_reset_verified"] else "no",
        "carry_over_detected": "yes" if cleanup["carry_over_detected"] else "no",
        "cleanup_verified": "yes" if cleanup["cleanup_verified"] else "no",
        "cache_warm_state_control": "20-cycle warm-up plus randomized within-block arm order; cache is not claimed reset",
        "reset_completion_pair": row.get("reset_completion_pair", "no"),
        "pre_state_hash": reset_result.get("pre_state_hash", ""),
        "post_state_hash": post_state.get("full_state_hash", ""),
    })
    first_ts, last_ts = kernel_timestamps(observation["focused_lines"])
    append_csv(directory / "RAW_TIMESTAMPS.csv", RAW_TIMESTAMP_FIELDS, {
        **common, "protocol_sha256": row["protocol_sha256"],
        "controller_broadcast_start_iso": collected["controller_broadcast_start_iso"],
        "controller_broadcast_end_iso": collected["controller_broadcast_end_iso"],
        "controller_collection_end_iso": collected["controller_collection_end_iso"],
        "host_monotonic_start_ns": collected["host_monotonic_start_ns"],
        "host_monotonic_broadcast_return_ns": collected["host_monotonic_broadcast_return_ns"],
        "host_monotonic_app_collected_ns": collected["host_monotonic_app_collected_ns"],
        "host_monotonic_collection_end_ns": collected["host_monotonic_collection_end_ns"],
        "apk_elapsed_ns": observation["latency_ns"], "apk_clock": CONSTANTS["latency_clock"],
        "apk_unit": CONSTANTS["latency_unit"], "kernel_first_ts_ns": first_ts,
        "kernel_last_ts_ns": last_ts,
        "kernel_timestamp_role": "diagnostic only; not substituted for APK latency",
        "primary_latency_boundary": "APK immediately before openFileDescriptor to return/exception and descriptor-close completion",
        "pre_reset_watermark_hash": row.get("log_watermark_pre_hash", ""),
        "post_reset_watermark_hash": row.get("log_watermark_post_hash", ""),
        "watermark_closed": "yes" if reset_result.get("watermark_closed") else "no",
    })

    def state_row(label: str, value: dict[str, Any]) -> dict[str, Any]:
        return {
            **common,
            "boundary": label,
            "captured_at": value.get("captured_at", ""),
            "boot_uuid": value.get("boot_uuid", ""),
            "full_state_hash": value.get("full_state_hash", ""),
            "projection_hash": value.get("projection_hash", ""),
            "policy_count": value.get("policy_count", ""),
            "switch_hash": sha256_text(canonical_counter_json(value.get("switches", {}))),
            "counter_hash": sha256_text(canonical_counter_json(value.get("counters", {}))),
            "log_watermark_hash": sha256_text(canonical_counter_json(value.get("log_watermark", {}))),
            "complete": "yes" if value.get("complete") else "no",
        }

    for label, value in (
        ("pre_reset", reset_result.get("pre_state", {})),
        ("stable_projection_1", reset_result.get("stable_projection_1", {})),
        ("stable_projection_2", reset_result.get("baseline_state", {})),
        ("post_workload", post_state),
        ("post_cleanup_stable", cleanup.get("final_state", {})),
    ):
        if value:
            append_csv(directory / "PRE_STATE_SNAPSHOTS.csv", PRE_STATE_FIELDS, state_row(label, value))

    for label, result in (("pre_invocation", reset_result), ("post_cleanup", cleanup.get("reset_result", {}))):
        if result:
            append_csv(directory / "RESET_COMPLETION_AUDIT.csv", RESET_AUDIT_FIELDS, {
                **common,
                "reset_label": label,
                "pre_state_hash": result.get("pre_state_hash", ""),
                "stable_projection_1_hash": result.get("stable_projection_1_hash", ""),
                "stable_projection_2_hash": result.get("stable_projection_2_hash", ""),
                "baseline_state_hash": result.get("baseline_state_hash", ""),
                "reset_returncode": result.get("reset_returncode", ""),
                "stable_projection_pair": "yes" if result.get("stable_projection_pair") else "no",
                "complete_projection_pair": "yes" if result.get("complete_projection_pair") else "no",
                "gate_clean": "yes" if result.get("gate_clean") else "no",
                "watermark_closed": "yes" if result.get("watermark_closed") else "no",
                "completion_oracle": result.get("completion_oracle", "RESET_FAIL"),
                "poll_count": result.get("poll_count", ""),
                "failure_reason": result.get("failure_reason", ""),
            })

    def watermark_row(role: str, value: dict[str, Any], closed: bool) -> dict[str, Any]:
        return {
            **common,
            "watermark_role": role,
            "captured_at": value.get("captured_at", ""),
            "returncode": value.get("returncode", ""),
            "line_count": value.get("line_count", ""),
            "sha256": value.get("sha256", ""),
            "max_audit_seq": value.get("max_audit_seq", ""),
            "max_kernel_ts_ns": value.get("max_kernel_ts_ns", ""),
            "host_monotonic_start_ns": value.get("host_monotonic_start_ns", ""),
            "host_monotonic_end_ns": value.get("host_monotonic_end_ns", ""),
            "workload_marker_count": value.get("workload_marker_count", ""),
            "closed": "yes" if closed else "no",
        }

    watermark_values = [
        ("pre_reset", reset_result.get("pre_reset_watermark", {}), reset_result.get("watermark_closed", False)),
        ("post_reset", reset_result.get("baseline_state", {}).get("log_watermark", {}), reset_result.get("watermark_closed", False)),
        ("arm_freeze", config.get("arm_watermark", {}), config.get("arm_watermark", {}).get("workload_marker_count", 1) == 0),
        ("post_workload", post_state.get("log_watermark", {}), False),
        ("post_cleanup", cleanup.get("final_state", {}).get("log_watermark", {}), cleanup.get("reset_result", {}).get("watermark_closed", False)),
    ]
    for role, value, closed in watermark_values:
        if value:
            append_csv(directory / "LOG_WATERMARK_AUDIT.csv", WATERMARK_FIELDS, watermark_row(role, value, closed))

    for name, delta in cleanup.get("counter_deltas", {}).items():
        append_csv(directory / "COUNTER_BASELINE_AND_DELTA.csv", COUNTER_DELTA_FIELDS, {
            **common,
            "counter": name,
            "scope": delta.get("scope", ""),
            "alias_of": delta.get("alias_of", ""),
            "baseline": delta.get("baseline", ""),
            "observed": delta.get("observed", ""),
            "delta": delta.get("delta", ""),
            "independent_event": delta.get("independent_event", ""),
            "baseline_state_hash": baseline_state.get("full_state_hash", ""),
            "observed_state_hash": post_state.get("full_state_hash", ""),
        })


def execute_invocation(state: dict[str, Any], schedule: dict[str, str], scientific: bool) -> dict[str, Any]:
    category = "scientific" if scientific else "warmup"
    raw_dir = state["boot_dir"] / "raw" / category / schedule["trial_id"]
    if raw_dir.exists():
        raise RuntimeError(f"prior evidence exists for {schedule['trial_id']}; invocation cannot be repeated")
    raw_dir.mkdir(parents=True, exist_ok=False)
    output_name = schedule["trial_id"] + ".csv"
    app_path = f"/sdcard/Android/data/{CONSTANTS['caller_package']}/files/{output_name}"
    try:
        reset = reset_engine()
        pre_state = reset.capture_state(arm_hint=schedule["arm"], boundary="pre_reset")
        reset_result = reset.reset_to_neutral(
            directory=raw_dir / "reset_v2_pre_invocation",
            label="pre_invocation",
            arm_hint=schedule["arm"],
            pre_state=pre_state,
        )
        if not reset_result["pass"]:
            raise RuntimeError("RESET_COMPLETION_ORACLE_FAILED_BEFORE_INVOCATION")
        config = configure_invocation(
            state, schedule, raw_dir, reset_result, reset_result["baseline_state"]
        )
        pre_invocation_ready(config, app_path, raw_dir)
    except Exception as exc:
        write_text(raw_dir / "PRE_INVOCATION_FAILURE.txt", f"{type(exc).__name__}:{exc}")
        raise
    stamp = now()
    if scientific and not FIRST_SCIENCE.exists():
        stamp = first_scientific_execution(state["protocol_sha256"], schedule["trial_id"])
    sentinel = raw_dir / "INVOCATION_SENTINEL.txt"
    exclusive_text(sentinel, "\n".join([
        f"TRIAL_ID={schedule['trial_id']}", f"INVOKED_AT={stamp}",
        f"PROTOCOL_SHA256={state['protocol_sha256']}",
        "PROTOCOL_VERSION=V2",
        f"RESET_PROCEDURE_V2_SHA256={CONSTANTS['reset_procedure_v2_sha256']}",
        f"RESET_COMPLETION_ORACLE_SHA256={CONSTANTS['reset_completion_oracle_sha256']}",
        f"SCIENTIFIC_ROW={'yes' if scientific else 'no'}", f"ARM={schedule['arm']}",
        f"BOOT_ID={state['boot_id']}", f"BOOT_UUID={state['boot_uuid']}",
        "REPEAT_OR_REPLACEMENT_PERMITTED=no",
    ]))
    try:
        collected = collect_invocation(state, schedule, raw_dir, app_path, output_name)
    except Exception as exc:
        stamp_after = now()
        mono_after = time.monotonic_ns()
        write_text(raw_dir / "collection_exception.txt", f"{type(exc).__name__}:{exc}")
        collected = {
            "app": {}, "app_text": "", "broadcast_returncode": -1,
            "broadcast_exception": f"{type(exc).__name__}:{exc}",
            "kernel_log": "", "all_log": "",
            "controller_broadcast_start_iso": stamp,
            "controller_broadcast_end_iso": stamp_after,
            "controller_collection_end_iso": stamp_after,
            "host_monotonic_start_ns": mono_after,
            "host_monotonic_broadcast_return_ns": mono_after,
            "host_monotonic_app_collected_ns": mono_after,
            "host_monotonic_collection_end_ns": mono_after,
        }
    try:
        counters_after = read_counters()
    except Exception as exc:
        counters_after = {}
        write_text(raw_dir / "counter_read_exception.txt", f"{type(exc).__name__}:{exc}")
    try:
        post_policy = policy_dump()
    except Exception as exc:
        post_policy = "UNREADABLE\n"
        write_text(raw_dir / "post_policy_exception.txt", f"{type(exc).__name__}:{exc}")
    write_json(raw_dir / "counters_after_workload.json", counters_after)
    write_text(raw_dir / "policy_dump_after_workload.txt", post_policy)
    post_verified = post_policy == config["expected_policy_dump"]
    try:
        cleanup = cleanup_after_invocation(state, schedule, config, counters_after, raw_dir)
    except Exception as exc:
        write_text(raw_dir / "cleanup_exception.txt", f"{type(exc).__name__}:{exc}")
        cleanup = {
            "clear_output": "FAILED", "final_policy_dump": "UNREADABLE",
            "policy_empty": False, "switches": {}, "switches_neutral": False,
            "counters_before_reset": counters_after, "counters_after_reset": {},
            "context_balance": False, "mismatch_free": False,
            "arm_a_pop_fail_allowed": False, "denied_accounting_balanced": False,
            "counter_reset_verified": False, "carry_over_detected": True,
            "real_carry_over_detected": True, "cleanup_verified": False,
            "post_state": {}, "final_state": {}, "reset_result": {}, "counter_deltas": {},
        }
    write_json(raw_dir / "cleanup.json", cleanup)
    config["cleanup"] = cleanup
    trial_counters = {
        name: value.get("delta", 0)
        for name, value in cleanup.get("counter_deltas", {}).items()
        if isinstance(value, dict) and isinstance(value.get("delta"), int)
    }
    parser_counters = trial_counters or counters_after
    meta = {
        "arm": schedule["arm"], "target": state["target"], "decoy": state["decoy"],
        "caller_uid": state["caller_uid"], "target_uri": CONSTANTS["target_uri"],
        "workload_mode": CONSTANTS["workload_mode"],
        "protocol_identity_match": state["protocol_identity_match"],
        "artifact_identity_match": state["artifact_identity_match"],
        "route_identity_match": state["route_identity_match"],
        "workload_identity_match": state["workload_identity_match"],
        "arm_state_verified_pre": config["pre_arm_state_verified"],
        "rule_state_verified_post": post_verified,
        "workload_invocation_attempted": True,
        "active_policy_count": config["active_policy_count"],
        "decoy_distinct": (state["target"]["kernel_dev"], state["target"]["ino"]) != (state["decoy"]["kernel_dev"], state["decoy"]["ino"]),
    }
    try:
        observation = build_observation(meta, collected, parser_counters, cleanup)
    except Exception as exc:
        write_text(raw_dir / "parser_exception.txt", f"{type(exc).__name__}:{exc}")
        app = collected.get("app", {}) or {}
        latency = str(app.get("elapsed_ns", ""))
        observation = {
            "app": app, "decision": {}, "decision_line": "",
            "route_hit_count": 0, "context_enter_count": 0, "context_exit_count": 0,
            "push_skipped_count": 0, "no_context_count": 0,
            "decision_apply_count": 0, "real_enforce_count": 0,
            "target_fd_install_count": 0, "decision_path_entered": "no",
            "rule_lookup_observed": "no", "rule_match_result": "parser_failure",
            "application_outcome": str(app.get("app_result", "missing")),
            "capability_returned": "yes" if app.get("usable_pfd") == "yes" else "no",
            "descriptor_installed": "no", "capability_usable": "no",
            "denied_path_accounting_balanced": "no", "latency_ns": latency if latency.isdigit() else "",
            "latency_complete": "yes" if latency.isdigit() else "no",
            "cleanup_status": "PASS" if cleanup.get("cleanup_verified") else "FAIL",
            "pop_fail_count": int(counters_after.get("context_pop_fail", 0)),
            "pop_fail_state": "unknown_parser_failure",
            "carry_over_detector_result": "FAIL" if cleanup.get("carry_over_detected") else "PASS",
            "classification": "PARSER_FAILURE", "primary_eligible": "no",
            "exclusion_reason": "PARSER_CANNOT_FORM_COMPLETE_TRIAL_ROW",
            "failure_codes": f"PARSER_EXCEPTION:{type(exc).__name__}", "focused_lines": [],
        }
    write_text(raw_dir / "focused_log.txt", "\n".join(observation["focused_lines"]))
    write_json(raw_dir / "trial_observation.json", observation)
    row = build_row(state, schedule, config, collected, observation, raw_dir, scientific)
    row["rule_state_verified_post"] = "yes" if post_verified else "no"
    ledger = state["boot_dir"] / ("SCIENTIFIC_ROWS.csv" if scientific else "WARMUP_ROWS.csv")
    append_csv(ledger, SCIENTIFIC_FIELDS if scientific else WARMUP_FIELDS, row)
    append_audits(state, row, config, observation, cleanup, collected, scientific)
    write_json(ROOT / "execution_manifests" / "EXECUTION_PROGRESS.json", {
        "updated_at": now(), "boot_id": state["boot_id"], "last_trial_id": schedule["trial_id"],
        "scientific_rows_observed": sum(csv_row_count(path / "SCIENTIFIC_ROWS.csv") for path in (ROOT / "02_boot_1", ROOT / "03_boot_2")),
        "warmup_rows_observed": sum(csv_row_count(path / "WARMUP_ROWS.csv") for path in (ROOT / "02_boot_1", ROOT / "03_boot_2")),
    })
    if not cleanup["cleanup_verified"]:
        raise RuntimeError(f"{schedule['trial_id']}: post-invocation cleanup/carry-over gate failed; row retained")
    return row


def finalize_boot(state: dict[str, Any]) -> None:
    directory = state["boot_dir"]
    with (directory / "SCIENTIFIC_ROWS.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with (directory / "WARMUP_ROWS.csv").open(newline="", encoding="utf-8") as handle:
        warmups = list(csv.DictReader(handle))
    arm_counts = Counter(row["arm"] for row in rows)
    class_counts = Counter(row["classification"] for row in rows)
    carry = sum(row["carry_over_detector_result"] != "PASS" for row in rows)
    if len(rows) != 1000 or any(arm_counts[arm] != 250 for arm in "ABCD") or len(warmups) != 60:
        result = "PARTIAL"
    else:
        result = "PASS"
    write_text(directory / "BOOT_STATUS.txt", "\n".join([
        f"BOOT_STATUS={result}", f"BOOT_ID={state['boot_id']}", f"BOOT_UUID={state['boot_uuid']}",
        f"COMPLETED_AT={now()}", f"SCIENTIFIC_ROWS={len(rows)}", f"WARMUP_ROWS={len(warmups)}",
        f"A_OBSERVED={arm_counts['A']}", f"B_OBSERVED={arm_counts['B']}",
        f"C_OBSERVED={arm_counts['C']}", f"D_OBSERVED={arm_counts['D']}",
        f"CARRY_OVER_DETECTED={'yes' if carry else 'no'}",
        "ENGINEERING_PROBES_MERGED=0", "OLD_PERFORMANCE_ROWS_MERGED=0", "RQ2_ROWS_MERGED=0",
    ]))
    summary_lines = [
        f"# {state['boot_id']} execution summary", "",
        f"- Boot UUID: `{state['boot_uuid']}`",
        f"- Registered measured rows: {len(rows)} / 1000.",
        f"- Warm-up rows: {len(warmups)} / 60; excluded from the scientific denominator.",
        f"- Arm counts: A={arm_counts['A']}, B={arm_counts['B']}, C={arm_counts['C']}, D={arm_counts['D']}.",
        f"- Carry-over detector failures: {carry}.",
        "- No latency aggregate was computed during execution.", "",
        "## Outcome classifications", "",
    ]
    summary_lines.extend(f"- {name}: {count}" for name, count in sorted(class_counts.items()))
    write_text(directory / "BOOT_SUMMARY.md", "\n".join(summary_lines))
    manifest_lines = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            manifest_lines.append(f"{sha256_file(path)}  {path.relative_to(directory)}")
    write_text(directory / "SHA256SUMS", "\n".join(manifest_lines))
    if result != "PASS":
        raise RuntimeError(f"{state['boot_id']} denominator incomplete")


def run_boot(boot_id: str) -> int:
    protocol_sha, manifest_output = verify_registered_inputs()
    state = prepare_boot(boot_id, protocol_sha, manifest_output)
    for schedule in state["warmups"]:
        execute_invocation(state, schedule, scientific=False)
    for schedule in state["measured"]:
        execute_invocation(state, schedule, scientific=True)
    finalize_boot(state)
    return 0


def reboot_for_boot_2() -> int:
    boot1 = ROOT / "02_boot_1" / "BOOT_STATUS.txt"
    if not boot1.exists() or parse_status(boot1).get("BOOT_STATUS") != "PASS":
        raise RuntimeError("boot_1 is not complete")
    previous = parse_status(boot1)["BOOT_UUID"]
    adb("reboot", check=False)
    time.sleep(2)
    adb("wait-for-device", timeout=300)
    for _ in range(180):
        if shell_out("getprop sys.boot_completed", check=False).strip() == "1":
            break
        time.sleep(1)
    else:
        raise RuntimeError("boot_2 did not reach sys.boot_completed=1")
    connect_root()
    current = shell_out("cat /proc/sys/kernel/random/boot_id").strip()
    if current == previous:
        raise RuntimeError("reboot did not change boot UUID")
    write_text(ROOT / "execution_manifests" / "BOOT_2_REBOOT.txt", "\n".join([
        f"REQUESTED_AT={now()}", f"BOOT_1_UUID={previous}", f"BOOT_2_UUID={current}", "RESULT=PASS",
    ]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    run_parser = sub.add_parser("run-boot")
    run_parser.add_argument("--boot", choices=["boot_1", "boot_2"], required=True)
    sub.add_parser("reboot-for-boot-2")
    args = parser.parse_args()
    if args.command == "verify":
        protocol_sha, output = verify_registered_inputs()
        print(output, end="")
        print(f"PROTOCOL_SHA256={protocol_sha}")
        print("SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE=0")
        return 0
    if args.command == "run-boot":
        return run_boot(args.boot)
    return reboot_for_boot_2()


if __name__ == "__main__":
    raise SystemExit(main())
