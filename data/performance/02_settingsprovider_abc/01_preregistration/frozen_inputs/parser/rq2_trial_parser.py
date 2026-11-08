"""Frozen parser and preregistered S10 target/control oracle."""

from __future__ import annotations

import re
from typing import Any


def parse_kv(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^ \n]+)", line))


def yn(value: bool) -> str:
    return "yes" if value else "no"


def parse_trial(meta: dict[str, Any], collected: dict[str, Any]) -> dict[str, str]:
    schedule = meta["schedule"]
    objects = meta["objects"]
    expected = objects["target"] if schedule["execution_object_role"] == "TARGET_OBJECT" else objects["non_target"]
    active_rule = meta.get("active_rule")
    kernel = str(collected.get("kernel_log", ""))
    all_log = str(collected.get("all_log", ""))
    app = collected.get("app", {}) or {}

    decisions = [
        line for line in kernel.splitlines()
        if "iguard_ctx: decision seq=" in line
        and "service_id=8 op_id=701" in line
    ]
    decision_line = next(
        (line for line in decisions
         if f"obj_ino={expected['ino']}" in line and f"obj_s_dev={expected['kernel_dev']}" in line),
        "",
    )
    decision = parse_kv(decision_line)
    seq = decision.get("seq", "")
    real_lines = [
        line for line in kernel.splitlines()
        if "iguard_ctx: real-enforce" in line
        and "service_id=8 op_id=701" in line
        and (not seq or f"seq={seq}" in line)
    ]
    relation_lines = [
        line for line in (kernel + "\n" + all_log).splitlines()
        if "CDAC_RELATION_DECISION" in line or "relation-deny" in line
    ]
    context_enter = [
        line for line in all_log.splitlines()
        if "event=CDAC_CONTEXT_ENTER" in line and "service_id=8 op_id=701" in line
    ]
    context_exit = [
        line for line in all_log.splitlines()
        if "event=CDAC_CONTEXT_EXIT" in line and "service_id=8 op_id=701" in line
    ]
    caller_pid = decision.get("caller_pid", "")
    expected_fd_lines = [
        line for line in kernel.splitlines()
        if "CDAC_FILE_LINEAGE event=fd_install" in line
        and f"ino={expected['ino']}" in line
        and f"s_dev={expected['kernel_dev']}" in line
        and (not caller_pid or f"pid={caller_pid}" in line)
    ]
    decoy = objects["decoy"]
    decoy_decisions = [
        line for line in decisions
        if f"obj_ino={decoy['ino']}" in line and f"obj_s_dev={decoy['kernel_dev']}" in line
    ]

    rule_match = decision.get("matched") == "1"
    direct_reached = bool(decision_line)
    direct_enforce = bool(real_lines)
    relation_reached = bool(relation_lines)
    app_success = app.get("app_result") == "success"
    app_eacces = app.get("app_result") == "failure" and "EACCES" in app.get("exception_message", "")
    returned = app.get("usable_pfd") == "yes"
    installed = bool(expected_fd_lines)
    usable = returned and app.get("read_ok") == "yes" and app.get("write_ok") == "yes"
    closed = app.get("close_ok") == "yes"
    if direct_enforce and not returned:
        pfd_started = "no"
        acquire_count, release_count = 0, 0
    elif returned:
        pfd_started = "yes"
        acquire_count, release_count = 1, 1 if closed else 0
    else:
        pfd_started = "unknown"
        acquire_count, release_count = -1, -1

    route_match = bool(context_enter) and direct_reached
    caller_match = decision.get("caller_uid") == str(meta["caller_uid"])
    object_match = decision.get("obj_ino") == str(expected["ino"]) and decision.get("obj_s_dev") == expected["kernel_dev"]
    operation_match = decision.get("op_id") == "701" and decision.get("service_id") == "8"
    rule_identity_match = bool(meta.get("rule_identity_match", False))
    rule_state_match = bool(meta.get("rule_state_match_pre", False)) and bool(meta.get("rule_state_match_post", False))
    protocol_match = bool(meta.get("protocol_identity_match", False))
    artifact_match = bool(meta.get("artifact_identity_match", False))
    balanced = acquire_count >= 0 and acquire_count == release_count

    flags: list[str] = []
    condition = schedule["condition"]
    classification = "UNCLASSIFIABLE_TRIAL"
    if meta.get("engineering_error", "NONE") != "NONE":
        classification = "HARNESS_OR_SYSTEM_ERROR"
    elif not protocol_match:
        classification = "PROTOCOL_IDENTITY_MISMATCH"
    elif not artifact_match:
        classification = "ARTIFACT_IDENTITY_MISMATCH"
    elif not route_match:
        classification = "ROUTE_IDENTITY_MISMATCH"
    elif not caller_match:
        classification = "CALLER_IDENTITY_MISMATCH"
    elif not object_match:
        classification = "OBJECT_IDENTITY_MISMATCH"
    elif not operation_match:
        classification = "OPERATION_IDENTITY_MISMATCH"
    elif not rule_identity_match:
        classification = "RULE_IDENTITY_MISMATCH"
    elif not rule_state_match:
        classification = "RULE_STATE_MISMATCH"
    elif condition == "T":
        if not rule_match:
            classification = "RULE_NOT_MATCHED"
        elif not direct_reached:
            classification = "DIRECT_ENFORCE_NOT_REACHED"
        elif not direct_enforce:
            classification = "DIRECT_ENFORCE_NOT_REACHED"
        elif relation_reached:
            classification = "RELATION_PATH_UNEXPECTEDLY_REACHED"
        elif not any("errno=-13" in line for line in real_lines):
            classification = "WRONG_KERNEL_RETURN"
        elif not app_eacces:
            classification = "APP_FAILURE_WITHOUT_CDAC_DENY"
        elif pfd_started != "no":
            classification = "PFD_RETURN_STARTED_BEFORE_DENY"
        elif returned:
            classification = "CAPABILITY_RETURNED"
        elif installed:
            classification = "FD_INSTALLED"
        elif usable:
            classification = "CAPABILITY_USABLE"
        elif not balanced:
            classification = "ACQUIRE_RELEASE_IMBALANCE"
        else:
            classification = "PRE_EXPOSURE_S10_DIRECT_DENY"
    else:
        if rule_match:
            classification = "UNEXPECTED_CONTROL_RULE_MATCH"
        elif direct_enforce or relation_reached:
            classification = "UNEXPECTED_CONTROL_DENY"
        elif not app_success:
            classification = "APP_FAILURE_WITHOUT_CDAC_DENY"
        elif not returned:
            classification = "CONTROL_CAPABILITY_NOT_RETURNED"
        elif not installed:
            classification = "CONTROL_FD_NOT_INSTALLED"
        elif not usable:
            classification = "CONTROL_CAPABILITY_NOT_USABLE"
        elif not closed or not balanced:
            classification = "ACQUIRE_RELEASE_IMBALANCE"
        elif condition == "C2" and decoy_decisions:
            classification = "UNEXPECTED_DECOY_OBJECT_OPEN"
        else:
            classification = f"PRESERVED_SAME_ARTIFACT_OUTCOME_{condition}"

    if not context_exit:
        flags.append("CONTEXT_EXIT_NOT_OBSERVED")
    if len(decisions) != 1:
        flags.append(f"EXPECTED_OBJECT_DECISION_COUNT={len(decisions)}")
    if condition == "C2" and decoy_decisions:
        flags.append("DECOY_OBJECT_DECISION_OBSERVED")
    if active_rule is None and schedule["installed_rule_state"] != "NO_RULE":
        flags.append("ACTIVE_RULE_METADATA_MISSING")

    app_outcome = "SUCCESS" if app_success else "FAILURE_EACCES" if app_eacces else "FAILURE_OTHER" if app else "MISSING"
    return {
        "trial_id": schedule["trial_id"],
        "timestamp_utc_plus_08": meta["invoked_at"],
        "protocol_sha256": meta["protocol_sha256"],
        "design_branch": "S10_4C",
        "boot_uuid": meta["boot_uuid"],
        "block_id": schedule["block_id"],
        "condition": condition,
        "schedule_position": str(schedule["schedule_position"]),
        "caller_package": "com.demo.s10settings",
        "caller_uid": str(meta["caller_uid"]),
        "caller_role": "PRIMARY_CALLER",
        "service_id": "8",
        "op_id": "701",
        "execution_object_role": schedule["execution_object_role"],
        "execution_s_dev": expected["kernel_dev"],
        "execution_ino": str(expected["ino"]),
        "installed_rule_state": schedule["installed_rule_state"],
        "installed_rule_identity": meta.get("installed_rule_identity", "NONE"),
        "installed_rule_caller_uid": str(meta["caller_uid"]) if active_rule else "NONE",
        "installed_rule_s_dev": active_rule["object"]["kernel_dev"] if active_rule else "NONE",
        "installed_rule_ino": str(active_rule["object"]["ino"]) if active_rule else "NONE",
        "expected_outcome": schedule["expected_outcome"],
        "rule_match": yn(rule_match),
        "direct_path_reached": yn(direct_reached),
        "direct_real_enforce_reached": yn(direct_enforce),
        "relation_path_reached": yn(relation_reached),
        "kernel_return": "-EACCES" if any("errno=-13" in line for line in real_lines) else "0" if app_success else "UNKNOWN",
        "app_outcome": app_outcome,
        "pfd_return_started": pfd_started,
        "deny_before_pfd_return": yn(direct_enforce and pfd_started == "no"),
        "capability_returned": yn(returned),
        "fd_installed": yn(installed),
        "capability_usable": yn(usable),
        "acquire_count": str(acquire_count),
        "release_count": str(release_count),
        "acquire_release_balanced": yn(balanced),
        "route_identity_match": yn(route_match),
        "caller_identity_match": yn(caller_match),
        "object_identity_match": yn(object_match),
        "operation_identity_match": yn(operation_match),
        "rule_identity_match": yn(rule_identity_match),
        "rule_state_match": yn(rule_state_match),
        "protocol_identity_match": yn(protocol_match),
        "artifact_identity_match": yn(artifact_match),
        "primary_trial_classification": classification,
        "secondary_flags": ";".join(flags) if flags else "NONE",
        "engineering_error": meta.get("engineering_error", "NONE"),
        "notes": "RAW=" + meta["raw_relative_path"],
    }
