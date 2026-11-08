#!/usr/bin/env python3
"""Frozen controller for the prospectively registered S10_4C matrix.

The controller never changes the schedule or repeats an invoked trial ID.  A
sentinel is created before every invocation and every invoked outcome is
appended to a durable per-boot ledger, including harness/system errors.
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
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SCRIPT = Path(__file__).resolve()
FROZEN = SCRIPT.parents[1]
ROOT = SCRIPT.parents[3]
PREREG = ROOT / "01_preregistration"
EXECUTION = ROOT / "02_execution"
sys.path.insert(0, str(FROZEN / "workload"))
sys.path.insert(0, str(FROZEN / "parser"))
from s10_workload import invoke_and_collect  # noqa: E402
from trial_parser import parse_trial  # noqa: E402


CONSTANTS = json.loads((FROZEN / "schemas" / "constants.json").read_text(encoding="utf-8"))
SERIAL = CONSTANTS["serial"]
SCHEDULE = PREREG / "RANDOMIZED_EXECUTION_SCHEDULE.csv"
MANIFEST = PREREG / "SHA256SUMS"
FREEZE_STATUS = PREREG / "PROTOCOL_FREEZE_STATUS.txt"
SENDER = FROZEN / "sender" / "iguardctl_test"
CALLER_APK = FROZEN / "caller_artifacts" / "s10-settings.apk"
POLICY_TOOL_GUEST = "/data/local/tmp/iguardctl_test"
LEDGER_FIELDS = [
    "trial_id", "timestamp_utc_plus_08", "protocol_sha256", "design_branch",
    "boot_uuid", "block_id", "condition", "schedule_position",
    "caller_package", "caller_uid", "caller_role", "service_id", "op_id",
    "execution_object_role", "execution_s_dev", "execution_ino",
    "installed_rule_state", "installed_rule_identity",
    "installed_rule_caller_uid", "installed_rule_s_dev", "installed_rule_ino",
    "expected_outcome", "rule_match", "direct_path_reached",
    "direct_real_enforce_reached", "relation_path_reached", "kernel_return",
    "app_outcome", "pfd_return_started", "deny_before_pfd_return",
    "capability_returned", "fd_installed", "capability_usable",
    "acquire_count", "release_count", "acquire_release_balanced",
    "route_identity_match", "caller_identity_match", "object_identity_match",
    "operation_identity_match", "rule_identity_match", "rule_state_match",
    "protocol_identity_match", "artifact_identity_match",
    "primary_trial_classification", "secondary_flags", "engineering_error",
    "notes",
]


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


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


def run(args: list[str], timeout: int = 120, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        cwd=cwd,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {args!r}\n{proc.stdout}")
    return proc


def adb(*args: str, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["adb", "-s", SERIAL, *args], timeout=timeout, check=check)


def shell(command: str, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb("shell", command, timeout=timeout, check=check)


def parse_status(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def verify_registered_inputs() -> tuple[str, str]:
    if not MANIFEST.exists() or not FREEZE_STATUS.exists():
        raise RuntimeError("protocol manifest or freeze status missing")
    check = run(["sha256sum", "-c", str(MANIFEST.relative_to(ROOT))], timeout=900, cwd=ROOT)
    status = parse_status(FREEZE_STATUS)
    if status.get("DESIGN_BRANCH") != "S10_4C":
        raise RuntimeError("frozen design branch is not S10_4C")
    if status.get("PROTOCOL_FROZEN") != "yes":
        raise RuntimeError("protocol not frozen")
    protocol_sha = sha256_file(PREREG / "RQ2_PROTOCOL_V3.md")
    if protocol_sha != status.get("PROTOCOL_SHA256"):
        raise RuntimeError("protocol SHA-256 differs from freeze status")
    schedule_sha = sha256_file(SCHEDULE)
    if schedule_sha != status.get("SCHEDULE_SHA256"):
        raise RuntimeError("schedule SHA-256 differs from freeze status")
    if status.get("SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE") != "0":
        raise RuntimeError("nonzero trials before protocol freeze")
    return protocol_sha, check.stdout


def connect_root() -> None:
    run(["adb", "connect", SERIAL], timeout=30, check=False)
    adb("wait-for-device", timeout=120)
    adb("root", timeout=30, check=False)
    time.sleep(1)
    run(["adb", "connect", SERIAL], timeout=30, check=False)
    adb("wait-for-device", timeout=120)


def policy_dump() -> str:
    return shell("cat /sys/kernel/debug/iguard/policy_dump").stdout


def policy_clear() -> tuple[str, str]:
    clear = shell(f"{POLICY_TOOL_GUEST} clear", check=False).stdout
    dump = policy_dump()
    return clear, dump


def runtime_policy_count(value: str) -> int:
    match = re.search(r"runtime_policy_count=(\d+)", value)
    return int(match.group(1)) if match else -1


def stat_path(path: str) -> dict[str, Any]:
    output = shell(f"stat -c '%n,%d,%i,%s' {path}").stdout.strip()
    parts = output.split(",")
    if len(parts) != 4:
        raise RuntimeError(f"unexpected stat output for {path}: {output!r}")
    dev_decimal = int(parts[1])
    major, minor = os.major(dev_decimal), os.minor(dev_decimal)
    return {
        "path": parts[0],
        "stat_dev_decimal": dev_decimal,
        "kernel_dev": f"{major}:{minor}",
        "raw_dev_t": (major << 20) + minor,
        "ino": int(parts[2]),
        "size": int(parts[3]),
    }


def guest_sha(path: str) -> str:
    output = shell(f"sha256sum {path}").stdout.strip()
    match = re.match(r"([0-9a-f]{64})\s+", output)
    if not match:
        raise RuntimeError(f"cannot parse guest hash for {path}: {output!r}")
    return match.group(1)


def package_uid(package_dump: str) -> int:
    match = re.search(r"(?:appId|userId)=(\d+)", package_dump)
    if not match:
        raise RuntimeError("caller UID missing from package dump")
    return int(match.group(1))


def package_apk_path() -> str:
    output = shell(f"pm path {CONSTANTS['caller_package']}").stdout.strip()
    match = re.search(r"package:(\S+base\.apk)", output)
    if not match:
        raise RuntimeError(f"installed caller APK path missing: {output!r}")
    return match.group(1)


def module_path_and_hash() -> tuple[str, str]:
    candidates = [
        "/vendor_dlkm/lib/modules/kernel/drivers/misc/iguard_ctl.ko",
        "/vendor/lib/modules/iguard_ctl.ko",
        "/system_dlkm/lib/modules/iguard_ctl.ko",
    ]
    for path in candidates:
        proc = shell(f"sha256sum {path}", check=False)
        match = re.match(r"([0-9a-f]{64})\s+", proc.stdout.strip())
        if proc.returncode == 0 and match:
            return path, match.group(1)
    raise RuntimeError("active iguard_ctl.ko not readable from registered paths")


def tsv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def schedule_rows(boot_label: str) -> list[dict[str, str]]:
    with SCHEDULE.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["boot_label"] == boot_label]
    if len(rows) != 80:
        raise RuntimeError(f"{boot_label} has {len(rows)} schedule rows instead of 80")
    expected_positions = list(range(1 if boot_label == "boot_01" else 81, 81 if boot_label == "boot_01" else 161))
    actual_positions = [int(row["schedule_position"]) for row in rows]
    if actual_positions != expected_positions:
        raise RuntimeError(f"{boot_label} schedule positions changed")
    return rows


def write_boot_hashes(boot_dir: Path, paths: list[Path]) -> None:
    lines = [f"{sha256_file(path)}  {path.name}" for path in sorted(paths, key=lambda item: item.name)]
    write_text(boot_dir / "BOOT_SHA256SUMS", "\n".join(lines))
    check = run(["sha256sum", "-c", "BOOT_SHA256SUMS"], cwd=boot_dir)
    write_text(boot_dir / "BOOT_SHA256SUMS.verification.txt", check.stdout)


def prepare_boot(boot_label: str, protocol_sha: str, manifest_output: str) -> dict[str, Any]:
    boot_dir = EXECUTION / boot_label
    if (boot_dir / "BOOT_EXECUTION_COMPLETE.txt").exists():
        raise RuntimeError(f"{boot_label} already completed; refusing repeat")
    connect_root()
    boot_uuid = shell("cat /proc/sys/kernel/random/boot_id").stdout.strip()
    if boot_label == "boot_02":
        previous = parse_status(EXECUTION / "boot_01" / "BOOT_IDENTITY.txt")
        if boot_uuid == previous.get("BOOT_UUID"):
            raise RuntimeError("boot_02 UUID equals boot_01 UUID")

    fingerprint = shell("getprop ro.build.fingerprint").stdout.strip()
    kernel = shell("uname -r").stdout.strip()
    selinux = shell("getenforce").stdout.strip()
    framework_hash = guest_sha("/system/framework/framework.jar")
    settings_hash = guest_sha("/system/priv-app/SettingsProvider/SettingsProvider.apk")
    module_path, module_hash = module_path_and_hash()
    artifact_checks = {
        "fingerprint": fingerprint == CONSTANTS["expected_fingerprint"],
        "kernel": kernel == CONSTANTS["expected_kernel_release"],
        "selinux": selinux == CONSTANTS["expected_selinux"],
        "framework.jar": framework_hash == CONSTANTS["expected_framework_jar_sha256"],
        "SettingsProvider.apk": settings_hash == CONSTANTS["expected_settings_provider_apk_sha256"],
        "iguard_ctl.ko": module_hash == CONSTANTS["expected_kernel_module_sha256"],
    }
    if not all(artifact_checks.values()):
        raise RuntimeError(f"artifact identity mismatch: {artifact_checks}")

    caller_dump = shell(f"dumpsys package {CONSTANTS['caller_package']}").stdout
    uid = package_uid(caller_dump)
    installed_apk = package_apk_path()
    installed_apk_hash = guest_sha(installed_apk)
    appop_set = shell(f"cmd appops set {CONSTANTS['caller_package']} WRITE_SETTINGS allow", check=False).stdout
    appop = shell(f"cmd appops get {CONSTANTS['caller_package']} WRITE_SETTINGS", check=False).stdout.strip()
    target_sdk_match = bool(re.search(r"targetSdk=36\b", caller_dump))
    caller_ok = (
        uid == CONSTANTS["caller_uid"]
        and installed_apk_hash == CONSTANTS["caller_apk_sha256"]
        and target_sdk_match
        and "allow" in appop
        and sha256_file(CALLER_APK) == CONSTANTS["caller_apk_sha256"]
    )
    if not caller_ok:
        raise RuntimeError("primary caller identity or authorization contract mismatch")

    push = adb("push", str(SENDER), POLICY_TOOL_GUEST)
    chmod = shell(f"chmod 0755 {POLICY_TOOL_GUEST}")
    sender_guest_hash = guest_sha(POLICY_TOOL_GUEST)
    if sender_guest_hash != CONSTANTS["sender_sha256"] or sha256_file(SENDER) != CONSTANTS["sender_sha256"]:
        raise RuntimeError("policy-add-v2 sender identity mismatch")
    shell("mount | grep -q ' /sys/kernel/debug ' || mount -t debugfs none /sys/kernel/debug", check=False)
    initial_dump = policy_dump()
    if initial_dump.strip() != "runtime_policy_count=0":
        raise RuntimeError("rule table is not initially empty")

    full_logcat = adb("logcat", "-d", "-v", "threadtime", check=False).stdout
    endpoint_lines = [
        line for line in full_logcat.splitlines()
        if "event=CDAC_ENDPOINT_REGISTER" in line
        and "service_id=8" in line
        and "op_id=701" in line
        and CONSTANTS["endpoint_provider_class"] in line
        and "result=ok" in line
    ]
    if not endpoint_lines:
        raise RuntimeError("authoritative S10 endpoint registration not observed on this boot")

    target = stat_path(CONSTANTS["target_path"])
    non_target = stat_path(CONSTANTS["non_target_path"])
    if target["kernel_dev"] == non_target["kernel_dev"] and target["ino"] == non_target["ino"]:
        raise RuntimeError("target and non-target/decoy identities are not distinct")
    objects = {"target": target, "non_target": non_target, "decoy": dict(non_target)}

    rows = schedule_rows(boot_label)
    boot_schedule = boot_dir / "BOOT_SCHEDULE.tsv"
    tsv(boot_schedule, list(rows[0]), rows)
    identity = boot_dir / "BOOT_IDENTITY.txt"
    write_text(
        identity,
        "\n".join([
            f"BOOT_UUID={boot_uuid}",
            f"BOOT_LABEL={boot_label}",
            f"BOOT_CAPTURED_AT={now()}",
            "TIMEZONE=Asia/Shanghai",
            "DESIGN_BRANCH=S10_4C",
            f"PROTOCOL_SHA256={protocol_sha}",
        ]),
    )
    artifact_path = boot_dir / "BOOT_ARTIFACT_IDENTITY.tsv"
    tsv(
        artifact_path,
        ["artifact", "expected", "observed", "verified", "source"],
        [
            {"artifact": "fingerprint", "expected": CONSTANTS["expected_fingerprint"], "observed": fingerprint, "verified": "yes", "source": "getprop ro.build.fingerprint"},
            {"artifact": "kernel", "expected": CONSTANTS["expected_kernel_release"], "observed": kernel, "verified": "yes", "source": "uname -r"},
            {"artifact": "SELinux", "expected": CONSTANTS["expected_selinux"], "observed": selinux, "verified": "yes", "source": "getenforce"},
            {"artifact": "framework.jar", "expected": CONSTANTS["expected_framework_jar_sha256"], "observed": framework_hash, "verified": "yes", "source": "/system/framework/framework.jar"},
            {"artifact": "SettingsProvider.apk", "expected": CONSTANTS["expected_settings_provider_apk_sha256"], "observed": settings_hash, "verified": "yes", "source": "/system/priv-app/SettingsProvider/SettingsProvider.apk"},
            {"artifact": "iguard_ctl.ko", "expected": CONSTANTS["expected_kernel_module_sha256"], "observed": module_hash, "verified": "yes", "source": module_path},
            {"artifact": "policy-add-v2 sender", "expected": CONSTANTS["sender_sha256"], "observed": sender_guest_hash, "verified": "yes", "source": POLICY_TOOL_GUEST},
        ],
    )
    caller_path = boot_dir / "BOOT_CALLER_IDENTITY.tsv"
    tsv(
        caller_path,
        ["field", "expected", "observed", "verified", "evidence"],
        [
            {"field": "package", "expected": CONSTANTS["caller_package"], "observed": CONSTANTS["caller_package"], "verified": "yes", "evidence": "dumpsys package"},
            {"field": "UID", "expected": CONSTANTS["caller_uid"], "observed": uid, "verified": "yes", "evidence": "dumpsys package"},
            {"field": "APK SHA-256", "expected": CONSTANTS["caller_apk_sha256"], "observed": installed_apk_hash, "verified": "yes", "evidence": installed_apk},
            {"field": "certificate SHA-256", "expected": CONSTANTS["caller_cert_sha256"], "observed": CONSTANTS["caller_cert_sha256"], "verified": "yes_by_frozen_APK_identity", "evidence": "frozen APK hash and caller contract"},
            {"field": "target SDK", "expected": 36, "observed": 36 if target_sdk_match else "mismatch", "verified": "yes", "evidence": "dumpsys package"},
            {"field": "WRITE_SETTINGS AppOp", "expected": "allow", "observed": appop.replace("\n", ";"), "verified": "yes", "evidence": "cmd appops get"},
        ],
    )
    object_path = boot_dir / "BOOT_OBJECT_IDENTITY_MANIFEST.tsv"
    object_rows = []
    for role, item in (("TARGET_OBJECT", target), ("NON_TARGET_OBJECT", non_target), ("DECOY_OBJECT", non_target)):
        object_rows.append({
            "role": role,
            "path": item["path"],
            "kernel_s_dev": item["kernel_dev"],
            "raw_dev_t": item["raw_dev_t"],
            "ino": item["ino"],
            "size": item["size"],
            "role_alias": "NON_TARGET_DECOY" if role != "TARGET_OBJECT" else "NONE",
            "frozen_before_scientific_block": "yes",
        })
    tsv(object_path, list(object_rows[0]), object_rows)
    object_manifest_sha = sha256_file(object_path)

    protocol_path = boot_dir / "BOOT_PROTOCOL_VERIFICATION.txt"
    write_text(
        protocol_path,
        "\n".join([
            f"BOOT_UUID={boot_uuid}",
            "BOOT_PROTOCOL_SHA256_VERIFIED=yes",
            "BOOT_REGISTERED_INPUTS_VERIFIED=yes",
            "BOOT_ARTIFACT_IDENTITY_VERIFIED=yes",
            "BOOT_CALLER_IDENTITY_VERIFIED=yes",
            "BOOT_OBJECT_IDENTITY_FROZEN=yes",
            f"BOOT_OBJECT_MANIFEST_SHA256={object_manifest_sha}",
            f"BOOT_SCHEDULE_SHA256={sha256_file(boot_schedule)}",
            "DESIGN_BRANCH=S10_4C",
            "INITIAL_RULE_TABLE_EMPTY=yes",
            "S10_ENDPOINT_PRESENT=yes",
            "S10_ENDPOINT_REGISTERED=yes",
            "S10_ENDPOINT_ENABLED=yes",
            "SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE=0",
        ]),
    )
    write_text(boot_dir / "REGISTERED_INPUT_VERIFICATION.txt", manifest_output)
    write_text(boot_dir / "INITIAL_POLICY_DUMP.txt", initial_dump)
    write_text(boot_dir / "ENDPOINT_REGISTRATION.txt", "\n".join(endpoint_lines))
    write_text(boot_dir / "CALLER_PACKAGE_DUMP.txt", caller_dump)
    write_text(boot_dir / "CALLER_APPOP_SET.txt", appop_set)
    write_text(boot_dir / "SENDER_PUSH.txt", push.stdout + chmod.stdout)
    write_text(EXECUTION / "logs" / f"{boot_label}_precheck_logcat.txt", full_logcat)
    preexecution_paths = [identity, artifact_path, caller_path, object_path, protocol_path, boot_schedule]
    write_boot_hashes(boot_dir, preexecution_paths)
    return {
        "boot_uuid": boot_uuid,
        "boot_dir": boot_dir,
        "objects": objects,
        "caller_uid": uid,
        "protocol_sha256": protocol_sha,
        "artifact_identity_match": True,
        "protocol_identity_match": True,
        "rows": rows,
    }


def canonical_rule(boot_label: str, block_id: str, state: str, uid: int, obj: dict[str, Any]) -> dict[str, Any]:
    suffix = "target" if state == "TARGET_RULE" else "decoy"
    return {
        "schema": "policy-add-v2",
        "service_id": 8,
        "op_id": 701,
        "caller_uid": uid,
        "decision": "deny",
        "reason": f"v3_science_{boot_label}_{block_id}_{suffix}",
        "f_flags_mask": "0x3",
        "f_flags_value": "0x2",
        "f_mode_mask": "0x0",
        "f_mode_value": "0x0",
        "required_relation_type": 0,
        "required_relation_stage": 0,
        "object": obj,
    }


def expected_policy_dump(rule: dict[str, Any]) -> str:
    obj = rule["object"]
    return (
        "runtime_policy_count=1\n"
        f"[0] service_id=8 op_id=701 caller_uid={rule['caller_uid']} service=- operation=- path_tail=- "
        f"ino={obj['ino']} s_dev={obj['kernel_dev']} i_mode=00 f_flags_mask=0x3 f_flags_value=0x2 "
        "f_mode_mask=0x0 f_mode_value=0x0 required_relation_type=0 required_relation_stage=0 "
        f"decision=would-deny reason={rule['reason']} specificity=6\n"
    )


def configure_block(state: dict[str, Any], block_id: str, rule_state: str) -> tuple[dict[str, Any] | None, str, str]:
    block_dir = state["boot_dir"] / "blocks" / block_id
    block_dir.mkdir(parents=True, exist_ok=True)
    clear_output, empty_dump = policy_clear()
    write_text(block_dir / "policy_clear.txt", clear_output)
    write_text(block_dir / "policy_dump_after_clear.txt", empty_dump)
    if empty_dump.strip() != "runtime_policy_count=0":
        raise RuntimeError(f"{block_id}: rule table did not clear")
    rule = None
    expected_dump = "runtime_policy_count=0\n"
    if rule_state != "NO_RULE":
        obj = state["objects"]["target"] if rule_state == "TARGET_RULE" else state["objects"]["decoy"]
        rule = canonical_rule(state["boot_dir"].name, block_id, rule_state, state["caller_uid"], obj)
        command = (
            f"{POLICY_TOOL_GUEST} add service_id=8 op_id=701 caller_uid={state['caller_uid']} "
            f"decision=deny reason={rule['reason']} f_flags_mask=0x3 f_flags_value=0x2 "
            f"ino={obj['ino']} s_dev={obj['raw_dev_t']}"
        )
        add = shell(command, check=False)
        write_text(block_dir / "rule_add.txt", f"COMMAND={command}\nRETURN_CODE={add.returncode}\n{add.stdout}")
        if add.returncode != 0 or "schema=v2" not in add.stdout:
            raise RuntimeError(f"{block_id}: policy-add-v2 failed")
        expected_dump = expected_policy_dump(rule)
    observed_dump = policy_dump()
    write_text(block_dir / "policy_dump_active.txt", observed_dump)
    if observed_dump != expected_dump:
        raise RuntimeError(f"{block_id}: exact rule dump mismatch")
    rule_identity = sha256_text(json.dumps(rule, sort_keys=True, separators=(",", ":"))) if rule else "NONE"
    manifest = {
        "block_id": block_id,
        "boot_uuid": state["boot_uuid"],
        "configured_at": now(),
        "design_branch": "S10_4C",
        "protocol_sha256": state["protocol_sha256"],
        "rule_state": rule_state,
        "rule_count": runtime_policy_count(observed_dump),
        "rule_identity": rule_identity,
        "rule": rule,
        "exact_dump_verified": True,
    }
    write_json(block_dir / "BLOCK_MANIFEST.json", manifest)
    write_text(block_dir / "BLOCK_MANIFEST.sha256", f"{sha256_file(block_dir / 'BLOCK_MANIFEST.json')}  BLOCK_MANIFEST.json")
    return rule, rule_identity, expected_dump


def append_ledger(path: Path, row: dict[str, str]) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def first_execution_timestamp(protocol_sha: str) -> str:
    path = EXECUTION / "manifests" / "FIRST_SCIENTIFIC_EXECUTION.txt"
    if path.exists():
        return parse_status(path)["FIRST_SCIENTIFIC_EXECUTION_AT"]
    frozen = parse_status(FREEZE_STATUS)["PROTOCOL_FROZEN_AT"]
    stamp = now()
    if datetime.fromisoformat(stamp) <= datetime.fromisoformat(frozen):
        raise RuntimeError("scientific execution timestamp does not follow protocol freeze")
    with path.open("x", encoding="utf-8") as handle:
        handle.write(
            f"FIRST_SCIENTIFIC_EXECUTION_AT={stamp}\n"
            f"PROTOCOL_FROZEN_AT={frozen}\n"
            f"PROTOCOL_SHA256={protocol_sha}\n"
            "SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE=0\n"
            "DESIGN_BRANCH=S10_4C\n"
        )
    return stamp


def remaining_attrition(state: dict[str, Any], rows: list[dict[str, str]], reason: str) -> None:
    path = EXECUTION / "attrition" / f"{state['boot_dir'].name}_not_executed.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        fields = ["trial_id", "schedule_position", "boot_label", "block_id", "condition", "status", "reason"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "trial_id": row["trial_id"],
                "schedule_position": row["schedule_position"],
                "boot_label": row["boot_label"],
                "block_id": row["block_id"],
                "condition": row["condition"],
                "status": "NOT_EXECUTED_ENGINEERING_FAILURE",
                "reason": reason,
            })


def run_boot(boot_label: str) -> int:
    protocol_sha, manifest_output = verify_registered_inputs()
    state = prepare_boot(boot_label, protocol_sha, manifest_output)
    ledger = state["boot_dir"] / "BOOT_TRIAL_LEDGER.csv"
    rows = state["rows"]
    completed_ids: set[str] = set()
    if ledger.exists():
        with ledger.open(newline="", encoding="utf-8") as handle:
            completed_ids = {row["trial_id"] for row in csv.DictReader(handle)}
    if completed_ids:
        raise RuntimeError(f"{boot_label} already has invoked trial rows; refusing repeat")

    blocks: list[tuple[str, list[dict[str, str]]]] = []
    for block_id in dict.fromkeys(row["block_id"] for row in rows):
        blocks.append((block_id, [row for row in rows if row["block_id"] == block_id]))
    invoked = 0
    last_timestamp = "NONE"
    for block_index, (block_id, block_rows) in enumerate(blocks):
        rule_state = block_rows[0]["installed_rule_state"]
        try:
            active_rule, rule_identity, expected_dump = configure_block(state, block_id, rule_state)
        except Exception as exc:
            remaining = [item for _, pending in blocks[block_index:] for item in pending]
            remaining_attrition(state, remaining, f"BLOCK_CONFIGURATION_FAILURE:{exc}")
            raise

        for row_index, schedule in enumerate(block_rows):
            trial_id = schedule["trial_id"]
            raw_dir = EXECUTION / "raw" / trial_id
            parsed_path = EXECUTION / "parsed" / f"{trial_id}.json"
            sentinel = raw_dir / "INVOCATION_SENTINEL.txt"
            if sentinel.exists() or parsed_path.exists():
                raise RuntimeError(f"{trial_id}: prior invocation evidence exists; refusing repeat")
            raw_dir.mkdir(parents=True, exist_ok=False)
            pre_dump = policy_dump()
            write_text(raw_dir / "policy_dump_before.txt", pre_dump)
            if pre_dump != expected_dump:
                remaining = block_rows[row_index:] + [item for _, pending in blocks[block_index + 1:] for item in pending]
                remaining_attrition(state, remaining, f"PRE_INVOCATION_RULE_STATE_FAILURE:{trial_id}")
                raise RuntimeError(f"{trial_id}: block rule state changed before invocation")

            invoked_at = now()
            if not (EXECUTION / "manifests" / "FIRST_SCIENTIFIC_EXECUTION.txt").exists():
                invoked_at = first_execution_timestamp(protocol_sha)
            raw_relative = str(raw_dir.relative_to(ROOT))
            sentinel.write_text(
                "\n".join([
                    f"TRIAL_ID={trial_id}",
                    f"INVOKED_AT={invoked_at}",
                    f"SCHEDULE_POSITION={schedule['schedule_position']}",
                    f"PROTOCOL_SHA256={protocol_sha}",
                    "DESIGN_BRANCH=S10_4C",
                    "CLASSIFICATION=SCIENTIFIC_S10_REGISTERED_EXECUTION",
                ]) + "\n",
                encoding="utf-8",
            )
            engineering_error = "NONE"
            collected: dict[str, Any]
            try:
                uri = CONSTANTS["target_uri"] if schedule["execution_object_role"] == "TARGET_OBJECT" else CONSTANTS["non_target_uri"]
                collected = invoke_and_collect(adb, raw_dir, trial_id, schedule["condition"], uri)
            except Exception as exc:
                engineering_error = f"{type(exc).__name__}:{exc}"
                write_text(raw_dir / "workload_exception.txt", engineering_error)
                collected = {"app": {}, "kernel_log": "", "all_log": "", "broadcast_returncode": -1}

            post_dump_proc = shell("cat /sys/kernel/debug/iguard/policy_dump", check=False)
            post_dump = post_dump_proc.stdout
            write_text(raw_dir / "policy_dump_after.txt", post_dump)
            post_match = post_dump_proc.returncode == 0 and post_dump == expected_dump
            focus_markers = (
                "CDAC_ENDPOINT_RESOLVE", "CDAC_CONTEXT_ENTER", "CDAC_CONTEXT_EXIT",
                "iguard_ctx: decision seq=", "iguard_ctx: decision-apply",
                "iguard_ctx: enforce-plan", "iguard_ctx: real-enforce",
                "CDAC_RELATION_DECISION", "CDAC_FILE_LINEAGE event=fd_install",
            )
            focused = [
                line for line in (str(collected.get("kernel_log", "")) + "\n" + str(collected.get("all_log", ""))).splitlines()
                if any(marker in line for marker in focus_markers)
            ]
            write_text(raw_dir / "focused_log.txt", "\n".join(focused))
            meta = {
                "schedule": schedule,
                "objects": state["objects"],
                "active_rule": active_rule,
                "installed_rule_identity": rule_identity,
                "rule_identity_match": True,
                "rule_state_match_pre": True,
                "rule_state_match_post": post_match,
                "protocol_identity_match": state["protocol_identity_match"],
                "artifact_identity_match": state["artifact_identity_match"],
                "protocol_sha256": protocol_sha,
                "boot_uuid": state["boot_uuid"],
                "caller_uid": state["caller_uid"],
                "invoked_at": invoked_at,
                "raw_relative_path": raw_relative,
                "engineering_error": engineering_error,
            }
            write_json(raw_dir / "trial_metadata.json", meta)
            parsed = parse_trial(meta, collected)
            write_json(parsed_path, parsed)
            append_ledger(ledger, parsed)
            invoked += 1
            last_timestamp = invoked_at
            write_json(
                EXECUTION / "manifests" / "EXECUTION_PROGRESS.json",
                {
                    "last_trial_id": trial_id,
                    "last_scientific_execution_at": invoked_at,
                    "scientific_trials": len(list((EXECUTION / "raw").glob("*/INVOCATION_SENTINEL.txt"))),
                    "registered_denominator_observed": len(list((EXECUTION / "parsed").glob("V3-S10-*.json"))),
                },
            )
            if not post_match:
                remaining = block_rows[row_index + 1:] + [item for _, pending in blocks[block_index + 1:] for item in pending]
                remaining_attrition(state, remaining, f"POST_INVOCATION_RULE_STATE_FAILURE:{trial_id}")
                raise RuntimeError(f"{trial_id}: block rule state changed after invocation; outcome retained")

    clear_output, final_dump = policy_clear()
    write_text(state["boot_dir"] / "FINAL_POLICY_CLEAR.txt", clear_output)
    write_text(state["boot_dir"] / "FINAL_POLICY_DUMP.txt", final_dump)
    if final_dump.strip() != "runtime_policy_count=0":
        raise RuntimeError(f"{boot_label}: final rule clear failed after all invocations")
    write_text(
        state["boot_dir"] / "BOOT_EXECUTION_COMPLETE.txt",
        "\n".join([
            f"BOOT_LABEL={boot_label}",
            f"BOOT_UUID={state['boot_uuid']}",
            f"COMPLETED_AT={now()}",
            f"LAST_SCIENTIFIC_EXECUTION_AT={last_timestamp}",
            f"SCIENTIFIC_TRIALS={invoked}",
            "REGISTERED_ROWS_FOR_BOOT=80",
            "ALL_INVOKED_OUTCOMES_RETAINED=yes",
            "FINAL_RULE_TABLE_EMPTY=yes",
        ]),
    )
    return 0


def reboot_for_boot_02() -> int:
    if not (EXECUTION / "boot_01" / "BOOT_EXECUTION_COMPLETE.txt").exists():
        raise RuntimeError("boot_01 is not complete")
    previous = parse_status(EXECUTION / "boot_01" / "BOOT_IDENTITY.txt")["BOOT_UUID"]
    adb("reboot", check=False)
    time.sleep(2)
    adb("wait-for-device", timeout=240)
    for _ in range(120):
        complete = shell("getprop sys.boot_completed", check=False).stdout.strip()
        if complete == "1":
            break
        time.sleep(1)
    else:
        raise RuntimeError("boot_02 did not reach sys.boot_completed=1")
    current = shell("cat /proc/sys/kernel/random/boot_id").stdout.strip()
    if current == previous:
        raise RuntimeError("replacement reboot did not change boot UUID")
    write_text(
        EXECUTION / "manifests" / "BOOT_02_REBOOT.txt",
        f"REQUESTED_AT={now()}\nBOOT_01_UUID={previous}\nBOOT_02_UUID={current}\nRESULT=PASS",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    run_parser = sub.add_parser("run-boot")
    run_parser.add_argument("--boot", required=True, choices=["boot_01", "boot_02"])
    sub.add_parser("reboot-for-boot-02")
    args = parser.parse_args()
    if args.command == "verify":
        protocol_sha, output = verify_registered_inputs()
        print(output, end="")
        print(f"PROTOCOL_SHA256={protocol_sha}")
        print("DESIGN_BRANCH=S10_4C")
        print("SCIENTIFIC_TRIALS_BEFORE_PROTOCOL_FREEZE=0")
        return 0
    if args.command == "run-boot":
        return run_boot(args.boot)
    return reboot_for_boot_02()


if __name__ == "__main__":
    raise SystemExit(main())
