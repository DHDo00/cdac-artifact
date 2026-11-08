#!/usr/bin/env python3
"""Frozen RQ4 per-invocation parser and outcome classifier."""

from __future__ import annotations

import re
from typing import Any


def parse_kv(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^ \n]+)", line))


def unique_lines(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            result.append(line)
    return result


def service_lines(text: str, marker: str) -> list[str]:
    return [
        line for line in unique_lines(text)
        if marker in line and "service_id=8" in line and "op_id=701" in line
    ]


def target_lines(text: str, marker: str, target: dict[str, Any]) -> list[str]:
    ino = str(target["ino"])
    kernel_dev = str(target["kernel_dev"])
    result: list[str] = []
    for line in unique_lines(text):
        if marker not in line:
            continue
        if (f"ino={ino}" in line or f"obj_ino={ino}" in line) and (
            f"s_dev={kernel_dev}" in line or f"obj_s_dev={kernel_dev}" in line
        ):
            result.append(line)
    return result


def last_target_decision(kernel_log: str, target: dict[str, Any], caller_uid: int) -> tuple[str, dict[str, str]]:
    matches = []
    for line in unique_lines(kernel_log):
        if "iguard_ctx: decision seq=" not in line:
            continue
        if "service_id=8" not in line or "op_id=701" not in line:
            continue
        if f"caller_uid={caller_uid}" not in line:
            continue
        if f"obj_ino={target['ino']}" not in line or f"obj_s_dev={target['kernel_dev']}" not in line:
            continue
        matches.append(line)
    line = matches[-1] if matches else ""
    return line, parse_kv(line)


def truth(value: bool) -> str:
    return "yes" if value else "no"


def build_observation(
    meta: dict[str, Any],
    collected: dict[str, Any],
    counters_after: dict[str, int],
    cleanup: dict[str, Any],
) -> dict[str, Any]:
    arm = str(meta["arm"])
    target = meta["target"]
    decoy = meta["decoy"]
    app = collected.get("app", {}) or {}
    kernel = str(collected.get("kernel_log", ""))
    all_log = str(collected.get("all_log", ""))
    decision_line, decision = last_target_decision(kernel, target, int(meta["caller_uid"]))
    route_hits = [
        line for line in service_lines(all_log, "event=CDAC_ENDPOINT_RESOLVE")
        if "transaction_code=15" in line
        and "transaction_name=openAssetFile" in line
        and "service_match=yes" in line
        and "resolve_result=hit" in line
    ]
    context_enter = [
        line for line in service_lines(all_log, "event=CDAC_CONTEXT_ENTER")
        if f"caller_uid={meta['caller_uid']}" in line and "operation=openAssetFile" in line
    ]
    context_exit = [
        line for line in service_lines(all_log, "event=CDAC_CONTEXT_EXIT")
        if "operation=openAssetFile" in line
    ]
    push_skipped = [
        line for line in service_lines(kernel + "\n" + all_log, "event=push_skipped")
        if "reason=ablation" in line and f"caller_uid={meta['caller_uid']}" in line
    ]
    no_context = target_lines(kernel + "\n" + all_log, "CDAC_BINDER_NO_CONTEXT", target)
    target_fd = target_lines(kernel, "CDAC_FILE_LINEAGE event=fd_install", target)
    decision_seq = decision.get("seq", "")
    decision_apply = [
        line for line in service_lines(kernel, "iguard_ctx: decision-apply")
        if not decision_seq or f"seq={decision_seq}" in line
    ]
    real_enforce = [
        line for line in service_lines(kernel, "iguard_ctx: real-enforce")
        if not decision_seq or f"seq={decision_seq}" in line
    ]

    latency_text = str(app.get("elapsed_ns", ""))
    latency_ok = latency_text.isdigit() and int(latency_text) >= 0
    app_fields_ok = (
        app.get("uri") == meta["target_uri"]
        and app.get("mode") == meta["workload_mode"]
        and app.get("attempt") == "0"
    )
    route_ok = len(route_hits) >= 1
    context_ok = len(context_enter) >= 1 and len(context_exit) >= 1
    object_ok = (
        app.get("s_dev") == str(target["stat_dev_decimal"])
        and app.get("ino") == str(target["ino"])
    ) if arm in "ABC" else True
    allow_app_ok = (
        app.get("app_result") == "success"
        and app.get("usable_pfd") == "yes"
        and app.get("read_ok") == "yes"
        and app.get("write_ok") == "yes"
        and app.get("close_ok") == "yes"
        and len(target_fd) >= 1
    )
    denial_app_ok = (
        app.get("app_result") == "failure"
        and app.get("usable_pfd") == "no"
        and app.get("read_ok") == "not_attempted"
        and app.get("write_ok") == "not_attempted"
        and app.get("close_ok") == "not_attempted"
        and "EACCES" in str(app.get("exception_message", ""))
        and len(target_fd) == 0
    )
    common_identity_ok = all(bool(meta.get(name)) for name in (
        "protocol_identity_match", "artifact_identity_match", "route_identity_match",
        "workload_identity_match", "arm_state_verified_pre", "rule_state_verified_post",
    ))
    cleanup_ok = bool(cleanup.get("cleanup_verified"))
    carry_over_ok = cleanup.get("carry_over_detected") is False
    failures: list[str] = []
    if not common_identity_ok:
        failures.append("IDENTITY_OR_PRE_ARM_STATE_FAILURE")
    if not meta.get("workload_invocation_attempted"):
        failures.append("WORKLOAD_INVOCATION_NOT_ATTEMPTED")
    if not app_fields_ok:
        failures.append("WORKLOAD_FIELDS_MISMATCH")
    if not latency_ok:
        failures.append("APK_LATENCY_MISSING")
    if not route_ok:
        failures.append("S10_ROUTE_HIT_NOT_OBSERVED")
    if not context_ok:
        failures.append("FRAMEWORK_CONTEXT_BOUNDARY_NOT_OBSERVED")
    if not cleanup_ok:
        failures.append("CLEANUP_FAILURE")
    if not carry_over_ok:
        failures.append("CARRY_OVER_DETECTED")

    decision_path_entered = bool(decision_line)
    lookup_observed = False
    rule_match_result = "not_entered"
    oracle_ok = False
    if arm == "A":
        if meta.get("active_policy_count") != 0:
            failures.append("A_POLICY_NOT_EMPTY")
        if len(push_skipped) < 1 or len(no_context) < 1:
            failures.append("A_REGISTERED_BYPASS_NOT_OBSERVED")
        if decision_path_entered or decision_apply or real_enforce:
            failures.append("A_CDAC_DECISION_PATH_EXECUTED")
        if not allow_app_ok or not object_ok:
            failures.append("A_ALLOW_CAPABILITY_ORACLE_FAILURE")
        oracle_ok = not failures
    elif arm == "B":
        lookup_observed = decision_path_entered
        rule_match_result = "no_rule_match"
        if meta.get("active_policy_count") != 0:
            failures.append("B_POLICY_NOT_EMPTY")
        if not decision_path_entered:
            failures.append("B_DECISION_PATH_NOT_ENTERED")
        if decision.get("matched") != "0" or decision.get("rule_src") != "default":
            failures.append("B_UNEXPECTED_RULE_MATCH")
        if real_enforce or not decision_apply:
            failures.append("B_ALLOW_BRANCH_NOT_OBSERVED")
        if push_skipped:
            failures.append("B_UNEXPECTED_BYPASS")
        if not allow_app_ok or not object_ok:
            failures.append("B_ALLOW_CAPABILITY_ORACLE_FAILURE")
        oracle_ok = not failures
    elif arm == "C":
        lookup_observed = (
            decision_path_entered
            and meta.get("active_policy_count") == 1
            and bool(meta.get("decoy_distinct"))
            and decision.get("matched") == "0"
            and decision.get("rule_src") == "default"
        )
        rule_match_result = "nonmatching_lookup" if lookup_observed else "unverified_nonmatch"
        if meta.get("active_policy_count") != 1 or not meta.get("decoy_distinct"):
            failures.append("C_NONMATCHING_RULE_STATE_INVALID")
        if not decision_path_entered:
            failures.append("C_DECISION_PATH_NOT_ENTERED")
        if not lookup_observed:
            failures.append("C_NONMATCHING_LOOKUP_NOT_OBSERVED")
        if real_enforce or not decision_apply:
            failures.append("C_ALLOW_BRANCH_NOT_OBSERVED")
        if push_skipped:
            failures.append("C_UNEXPECTED_BYPASS")
        if not allow_app_ok or not object_ok:
            failures.append("C_ALLOW_CAPABILITY_ORACLE_FAILURE")
        oracle_ok = not failures
    elif arm == "D":
        lookup_observed = decision_path_entered
        rule_match_result = "matched" if decision.get("matched") == "1" else "not_matched"
        acquire = int(counters_after.get("frdac_denied_internal_fd_acquire_total", 0))
        release = int(counters_after.get("frdac_denied_internal_fd_release_total", 0))
        outstanding = int(counters_after.get("frdac_denied_internal_fd_outstanding", 0))
        balanced = acquire == release and outstanding == 0
        if meta.get("active_policy_count") != 1:
            failures.append("D_TARGET_RULE_STATE_INVALID")
        if not decision_path_entered:
            failures.append("D_DECISION_PATH_NOT_ENTERED")
        if decision.get("matched") != "1" or decision.get("rule_src") != "runtime":
            failures.append("D_REVIEWED_RULE_EXACT_MATCH_NOT_OBSERVED")
        if not any("errno=-13" in line and "verdict=deny-now" in line for line in real_enforce):
            failures.append("D_DIRECT_EACCES_ENFORCEMENT_NOT_OBSERVED")
        if not denial_app_ok:
            failures.append("D_APPLICATION_DENIAL_ORACLE_FAILURE")
        if not balanced or int(counters_after.get("frdac_denied_app_fd_install_total", 0)) != 0:
            failures.append("D_DENIED_PATH_ACCOUNTING_UNBALANCED")
        oracle_ok = not failures
    else:
        failures.append("UNKNOWN_ARM")

    if oracle_ok and arm in "ABC":
        classification = "VALID_ALLOW_PATH_SAMPLE"
    elif oracle_ok and arm == "D":
        classification = "VALID_ABSOLUTE_DENIAL_LATENCY_SAMPLE"
    elif not meta.get("workload_invocation_attempted"):
        classification = "WORKLOAD_INVOCATION_FAILURE"
    elif not latency_ok:
        classification = "TIMESTAMP_FAILURE"
    elif not common_identity_ok:
        classification = "IDENTITY_OR_WRONG_ARM_FAILURE"
    elif not cleanup_ok or not carry_over_ok:
        classification = "STATE_CLEANUP_OR_CARRY_OVER_FAILURE"
    else:
        classification = "OUTCOME_ORACLE_FAILURE"
    primary_eligible = oracle_ok and latency_ok
    exclusion_reason = "NONE" if primary_eligible else "NOT_PRIMARY_OUTCOME_STRATUM:" + ";".join(failures)
    pop_fail = int(counters_after.get("context_pop_fail", 0))
    if arm == "A" and pop_fail > 0:
        pop_state = "expected_arm_a_diagnostic_reset_after_trial"
    elif pop_fail == 0:
        pop_state = "zero"
    else:
        pop_state = "unexpected_nonzero"

    focused = unique_lines("\n".join(
        route_hits + context_enter + context_exit + push_skipped + no_context
        + ([decision_line] if decision_line else []) + decision_apply + real_enforce + target_fd
    ))
    return {
        "app": app,
        "decision": decision,
        "decision_line": decision_line,
        "route_hit_count": len(route_hits),
        "context_enter_count": len(context_enter),
        "context_exit_count": len(context_exit),
        "push_skipped_count": len(push_skipped),
        "no_context_count": len(no_context),
        "decision_apply_count": len(decision_apply),
        "real_enforce_count": len(real_enforce),
        "target_fd_install_count": len(target_fd),
        "decision_path_entered": truth(decision_path_entered),
        "rule_lookup_observed": truth(lookup_observed),
        "rule_match_result": rule_match_result,
        "application_outcome": str(app.get("app_result", "missing")),
        "capability_returned": "yes" if app.get("usable_pfd") == "yes" else "no",
        "descriptor_installed": truth(len(target_fd) >= 1),
        "capability_usable": "yes" if allow_app_ok else "no",
        "denied_path_accounting_balanced": truth(
            int(counters_after.get("frdac_denied_internal_fd_acquire_total", 0))
            == int(counters_after.get("frdac_denied_internal_fd_release_total", 0))
            and int(counters_after.get("frdac_denied_internal_fd_outstanding", 0)) == 0
        ),
        "latency_ns": latency_text if latency_ok else "",
        "latency_complete": truth(latency_ok),
        "cleanup_status": "PASS" if cleanup_ok else "FAIL",
        "pop_fail_count": pop_fail,
        "pop_fail_state": pop_state,
        "carry_over_detector_result": "PASS" if carry_over_ok else "FAIL",
        "classification": classification,
        "primary_eligible": truth(primary_eligible),
        "exclusion_reason": exclusion_reason,
        "failure_codes": ";".join(failures) if failures else "NONE",
        "focused_lines": focused,
    }
