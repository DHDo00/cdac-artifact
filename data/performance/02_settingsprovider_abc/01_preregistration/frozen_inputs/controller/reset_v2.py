#!/usr/bin/env python3
"""Frozen RQ4 V2 reset/carry-over accounting implementation.

This module contains no workload invocation path.  It implements the exact
engineering-closure boundary: immutable pre-state, log watermark, existing
counter reset, two complete stable projections, scoped baseline/delta
accounting, alias preservation, and hard-fail completion semantics.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


SWITCHES = (
    "ablate_disable_ctx",
    "ablate_disable_runtime",
    "ablate_path_tail_only",
    "verbose_audit",
)

RESET_SENSITIVE = (
    "context_push_ok", "context_push_fail", "context_pop_ok", "context_pop_fail",
    "context_lookup_hit", "context_lookup_miss", "relation_decision",
    "relation_complete", "relation_incomplete", "relation_stale",
    "relation_rule_match", "relation_rule_nonmatch", "relation_deny",
    "relation_allow", "file_open_join", "file_open_deny",
    "relation_publish_total", "relation_unpaired", "rule_match_total",
    "frdac_deny_total", "frdac_denied_internal_fd_acquire_total",
    "frdac_denied_internal_fd_release_total",
    "frdac_denied_internal_fd_outstanding",
    "frdac_denied_app_fd_install_total",
)

ALIAS_MAP = {
    "context_enter_total": "context_push_ok",
    "context_exit_total": "context_pop_ok",
    "context_nested_mismatch_total": "context_mismatch_semantic",
    "context_stale_total": "context_stale_semantic",
    "context_borrowed_total": "context_borrowed_semantic",
}

MODULE_CONTROL_PLANE = {
    "file_open_no_context",
    "fd_receive_event_total",
    "fd_receiver_install_attempt_total",
    "fd_receiver_install_success_total",
    "fd_receiver_install_failure_total",
    "frdac_target_fd_transfer_attempt_total",
    "frdac_target_receiver_install_success_total",
    "frdac_target_receiver_install_failure_total",
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def parse_counters(raw: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            values[key.strip()] = int(value.strip())
        except ValueError:
            continue
    return values


def policy_count(raw: str) -> int:
    match = re.search(r"runtime_policy_count=(\d+)", raw)
    return int(match.group(1)) if match else -1


def counter_scope(name: str) -> str:
    if name == "counter_schema_version":
        return "schema"
    if name in ALIAS_MAP:
        return f"alias_of_{ALIAS_MAP[name]}"
    if name in RESET_SENSITIVE:
        return "trial_sensitive"
    if name in MODULE_CONTROL_PLANE:
        return "module_control_plane"
    return "module_or_unclassified"


class ResetV2:
    """Machine-verifiable reset boundary wired to the frozen controller."""

    def __init__(
        self,
        *,
        adb: Callable[..., Any],
        shell: Callable[..., Any],
        shell_out: Callable[..., str],
        policy_clear: Callable[[], tuple[str, str]],
        set_switch: Callable[[str, str], str],
        debugfs: str,
        stability_interval_seconds: float,
        completion_timeout_seconds: float,
        timezone_now: Callable[[], str],
    ) -> None:
        self.adb = adb
        self.shell = shell
        self.shell_out = shell_out
        self.policy_clear = policy_clear
        self.set_switch = set_switch
        self.debugfs = debugfs
        self.stability_interval = stability_interval_seconds
        self.timeout = completion_timeout_seconds
        self.now = timezone_now

    def log_watermark(self) -> dict[str, Any]:
        host_start = time.monotonic_ns()
        proc = self.adb(
            "logcat", "-b", "kernel", "-d", "-v", "threadtime", "-t", "1500",
            check=False,
        )
        host_end = time.monotonic_ns()
        text = proc.stdout
        seqs = [int(value) for value in re.findall(r"audit_seq=(\d+)", text)]
        timestamps = [int(value) for value in re.findall(r"ts_ns=(\d+)", text)]
        return {
            "captured_at": self.now(),
            "returncode": proc.returncode,
            "line_count": len(text.splitlines()),
            "sha256": sha256_text(text),
            "max_audit_seq": max(seqs) if seqs else None,
            "max_kernel_ts_ns": max(timestamps) if timestamps else None,
            "host_monotonic_start_ns": host_start,
            "host_monotonic_end_ns": host_end,
            "workload_marker_count": sum(
                text.count(token)
                for token in (
                    "S10Receiver",
                    "content://settings/system/ringtone_cache",
                    "RQ4V2-",
                )
            ),
        }

    @staticmethod
    def _parse_bundle(raw: str) -> dict[str, str]:
        markers = (
            "BOOT_UUID", "GUEST_REALTIME_NS", "GUEST_UPTIME", "POLICY",
            "SWITCH_ablate_disable_ctx", "SWITCH_ablate_disable_runtime",
            "SWITCH_ablate_path_tail_only", "SWITCH_verbose_audit", "COUNTERS",
        )
        sections: dict[str, list[str]] = {name: [] for name in markers}
        current = ""
        marker_set = {f"__RQ4V2_{name}__": name for name in markers}
        for line in raw.splitlines():
            if line in marker_set:
                current = marker_set[line]
            elif current:
                sections[current].append(line)
        return {name: "\n".join(lines).rstrip("\n") for name, lines in sections.items()}

    def capture_state(self, *, arm_hint: str, boundary: str) -> dict[str, Any]:
        host_start = time.monotonic_ns()
        command = "; ".join([
            "printf '__RQ4V2_BOOT_UUID__\\n'", "cat /proc/sys/kernel/random/boot_id",
            "printf '__RQ4V2_GUEST_REALTIME_NS__\\n'", "date +%s%N",
            "printf '__RQ4V2_GUEST_UPTIME__\\n'", "cat /proc/uptime",
            "printf '__RQ4V2_POLICY__\\n'", f"cat {self.debugfs}/policy_dump",
            "printf '__RQ4V2_SWITCH_ablate_disable_ctx__\\n'", f"cat {self.debugfs}/ablate_disable_ctx",
            "printf '__RQ4V2_SWITCH_ablate_disable_runtime__\\n'", f"cat {self.debugfs}/ablate_disable_runtime",
            "printf '__RQ4V2_SWITCH_ablate_path_tail_only__\\n'", f"cat {self.debugfs}/ablate_path_tail_only",
            "printf '__RQ4V2_SWITCH_verbose_audit__\\n'", f"cat {self.debugfs}/verbose_audit",
            "printf '__RQ4V2_COUNTERS__\\n'", f"cat {self.debugfs}/quiet_counters",
        ])
        bundle = self.shell_out(command, check=False)
        host_end = time.monotonic_ns()
        parsed = self._parse_bundle(bundle)
        counters_raw = parsed["COUNTERS"]
        counters = parse_counters(counters_raw)
        switches = {
            name: parsed[f"SWITCH_{name}"].strip()
            for name in SWITCHES
        }
        watermark = self.log_watermark()
        complete = (
            bool(parsed["BOOT_UUID"].strip())
            and bool(parsed["GUEST_REALTIME_NS"].strip())
            and policy_count(parsed["POLICY"]) >= 0
            and all(switches[name] in {"Y", "N"} for name in SWITCHES)
            and all(name in counters for name in RESET_SENSITIVE)
            and all(name in counters for name in ALIAS_MAP)
            and watermark["returncode"] == 0
        )
        projection = {
            "boot_uuid": parsed["BOOT_UUID"].strip(),
            "policy_count": policy_count(parsed["POLICY"]),
            "policy_sha256": sha256_text(parsed["POLICY"] + "\n"),
            "switches": switches,
            "trial_sensitive_counters": {
                name: counters.get(name) for name in RESET_SENSITIVE
            },
            "context_enter_total": counters.get("context_enter_total"),
            "context_exit_total": counters.get("context_exit_total"),
            "context_nested_mismatch_total": counters.get("context_nested_mismatch_total"),
            "context_stale_total": counters.get("context_stale_total"),
            "descriptor_outstanding": counters.get("frdac_denied_internal_fd_outstanding"),
            "complete": complete,
        }
        return {
            "captured_at": self.now(),
            "boundary": boundary,
            "arm_hint": arm_hint,
            "host_monotonic_start_ns": host_start,
            "host_monotonic_end_ns": host_end,
            "guest_realtime_ns": parsed["GUEST_REALTIME_NS"].strip(),
            "guest_uptime": parsed["GUEST_UPTIME"].strip(),
            "boot_uuid": parsed["BOOT_UUID"].strip(),
            "policy_dump": parsed["POLICY"] + ("\n" if parsed["POLICY"] else ""),
            "policy_count": policy_count(parsed["POLICY"]),
            "switches": switches,
            "counter_raw": counters_raw + ("\n" if counters_raw else ""),
            "counters": counters,
            "counter_scopes": {name: counter_scope(name) for name in counters},
            "alias_map": ALIAS_MAP,
            "log_watermark": watermark,
            "projection": projection,
            "projection_hash": sha256_text(canonical_json(projection)),
            "complete": complete,
            "full_state_hash": sha256_text(canonical_json({
                "boundary": boundary,
                "boot_uuid": parsed["BOOT_UUID"].strip(),
                "policy_dump": parsed["POLICY"],
                "switches": switches,
                "counters": counters,
                "log_watermark": watermark,
            })),
        }

    @staticmethod
    def save_state(directory: Path, label: str, state: dict[str, Any]) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{label}.json").write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (directory / f"{label}_counters.txt").write_text(
            str(state["counter_raw"]), encoding="utf-8"
        )
        (directory / f"{label}_policy.txt").write_text(
            str(state["policy_dump"]), encoding="utf-8"
        )
        (directory / f"{label}_watermark.json").write_text(
            json.dumps(state["log_watermark"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def gate_clean(state: dict[str, Any]) -> bool:
        counters = state["counters"]
        aliases_consistent = (
            counters.get("context_enter_total") == counters.get("context_push_ok")
            and counters.get("context_exit_total") == counters.get("context_pop_ok")
        )
        diagnostic_aliases_clean = all(
            counters.get(name) == 0
            for name in ("context_nested_mismatch_total", "context_stale_total")
        )
        return bool(
            state["complete"]
            and state["policy_count"] == 0
            and all(state["switches"].get(name) == "N" for name in SWITCHES)
            and all(counters.get(name) == 0 for name in RESET_SENSITIVE)
            and aliases_consistent
            and diagnostic_aliases_clean
            and counters.get("frdac_denied_internal_fd_outstanding") == 0
        )

    @staticmethod
    def counter_deltas(
        baseline: dict[str, Any], observed: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        left = baseline["counters"]
        right = observed["counters"]
        rows: dict[str, dict[str, Any]] = {}
        for name in sorted(set(left) | set(right)):
            pre = left.get(name)
            post = right.get(name)
            rows[name] = {
                "counter": name,
                "scope": counter_scope(name),
                "alias_of": ALIAS_MAP.get(name, ""),
                "baseline": pre,
                "observed": post,
                "delta": (post - pre) if isinstance(pre, int) and isinstance(post, int) else None,
                "independent_event": "no" if name in ALIAS_MAP else "yes",
            }
        return rows

    def reset_to_neutral(
        self,
        *,
        directory: Path,
        label: str,
        arm_hint: str,
        pre_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        directory.mkdir(parents=True, exist_ok=True)
        pre = pre_state or self.capture_state(arm_hint=arm_hint, boundary=f"{label}:pre")
        self.save_state(directory, "pre", pre)

        clear_output, clear_dump = self.policy_clear()
        switch_results = {
            name: self.set_switch(name, "N") for name in SWITCHES
        }
        log_clear = self.adb("logcat", "-b", "all", "-c", check=False)
        watermark = self.log_watermark()
        reset = self.shell(
            f"printf reset > {self.debugfs}/quiet_counters", check=False
        )

        poll_records: list[dict[str, Any]] = []
        previous: dict[str, Any] | None = None
        stable_first: dict[str, Any] | None = None
        stable_second: dict[str, Any] | None = None
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            current = self.capture_state(
                arm_hint=arm_hint, boundary=f"{label}:projection_{len(poll_records) + 1}"
            )
            poll_records.append({
                "index": len(poll_records) + 1,
                "captured_at": current["captured_at"],
                "complete": current["complete"],
                "projection_hash": current["projection_hash"],
                "full_state_hash": current["full_state_hash"],
                "gate_clean": self.gate_clean(current),
                "log_watermark": current["log_watermark"],
            })
            if (
                previous is not None
                and previous["complete"]
                and current["complete"]
                and previous["projection_hash"] == current["projection_hash"]
                and self.gate_clean(previous)
                and self.gate_clean(current)
            ):
                stable_first = previous
                stable_second = current
                break
            previous = current
            time.sleep(self.stability_interval)

        if stable_second is None:
            stable_second = previous or self.capture_state(
                arm_hint=arm_hint, boundary=f"{label}:timeout_projection"
            )
        self.save_state(directory, "stable_projection_1", stable_first or stable_second)
        self.save_state(directory, "stable_projection_2", stable_second)
        (directory / "polls.json").write_text(
            json.dumps(poll_records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (directory / "pre_reset_watermark.json").write_text(
            json.dumps(watermark, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        deltas = self.counter_deltas(pre, stable_second)
        (directory / "counter_pre_to_stable_deltas.json").write_text(
            json.dumps(deltas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        post_watermark = stable_second["log_watermark"]
        watermark_closed = bool(
            log_clear.returncode == 0
            and watermark["returncode"] == 0
            and post_watermark["returncode"] == 0
            and post_watermark["host_monotonic_end_ns"] >= watermark["host_monotonic_end_ns"]
            and post_watermark["workload_marker_count"] == 0
        )
        stable_pair = stable_first is not None
        passed = bool(
            reset.returncode == 0
            and policy_count(clear_dump) == 0
            and all(value == "N" for value in switch_results.values())
            and stable_pair
            and self.gate_clean(stable_second)
            and watermark_closed
            and pre["boot_uuid"] == stable_second["boot_uuid"]
        )
        result = {
            "label": label,
            "completed_at": self.now(),
            "pre_state_hash": pre["full_state_hash"],
            "stable_projection_1_hash": (stable_first or stable_second)["projection_hash"],
            "stable_projection_2_hash": stable_second["projection_hash"],
            "baseline_state_hash": stable_second["full_state_hash"],
            "baseline_projection_hash": stable_second["projection_hash"],
            "clear_output": clear_output,
            "clear_policy_count": policy_count(clear_dump),
            "switch_results": switch_results,
            "log_clear_returncode": log_clear.returncode,
            "pre_reset_watermark": watermark,
            "reset_returncode": reset.returncode,
            "reset_output": reset.stdout,
            "poll_count": len(poll_records),
            "stable_projection_pair": stable_pair,
            "complete_projection_pair": bool(
                stable_first and stable_first["complete"] and stable_second["complete"]
            ),
            "gate_clean": self.gate_clean(stable_second),
            "watermark_closed": watermark_closed,
            "completion_oracle": "PASS" if passed else "RESET_FAIL",
            "pass": passed,
            "failure_reason": "" if passed else (
                "reset return, exact neutral state, two complete stable projections, "
                "watermark closure, or boot identity conjunct failed"
            ),
            "baseline_state": stable_second,
            "pre_state": pre,
            "stable_projection_1": stable_first or stable_second,
            "stable_projection_2": stable_second,
        }
        (directory / "reset_result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return result


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")
