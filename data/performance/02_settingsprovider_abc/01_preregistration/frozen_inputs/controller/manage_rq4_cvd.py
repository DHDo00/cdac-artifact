#!/usr/bin/env python3
"""Start/stop the isolated retained-artifact RQ4 Cuttlefish instance."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPT = Path(__file__).resolve()
FROZEN = SCRIPT.parents[1]
ROOT = SCRIPT.parents[3]
CONSTANTS = json.loads((FROZEN / "schemas" / "rq4_constants.json").read_text(encoding="utf-8"))
RQ2 = Path(CONSTANTS["rq2_root"])
CONFIG = ROOT / "runtime" / "cvd" / "cuttlefish_config.json"
IMAGES = RQ2 / "00_preflight" / "runtime_inputs" / "isolated_images"
RUN_CVD = ROOT / "runtime" / "bin" / "rq4v2_cvd_launcher"
STOP_CVD = Path("aosp16/out/host/linux-x86/bin/cvd_internal_stop")
LOG_DIR = ROOT / "execution_manifests"
SERIAL = str(CONSTANTS["adb_serial"])


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="microseconds")


def environment() -> dict[str, str]:
    env = os.environ.copy()
    env["CUTTLEFISH_CONFIG_FILE"] = str(CONFIG)
    env["CUTTLEFISH_INSTANCE"] = str(CONSTANTS["cvd_instance"])
    return env


def processes() -> tuple[list[str], list[str]]:
    proc = subprocess.run(
        ["ps", "-eo", "pid,args"], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    relevant = [
        line for line in proc.stdout.splitlines()
        if ("/instances/cvd-" in line or "run_cvd --system_image_dir=" in line)
        and "ps -eo pid,args" not in line
    ]
    ours = [line for line in relevant if str(ROOT) in line]
    outside = [line for line in relevant if str(ROOT) not in line]
    return ours, outside


def record(name: str, lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / name).write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8", errors="replace")


def run_logged(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, env=environment(), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout,
    )


def wait_android() -> tuple[bool, str]:
    subprocess.run(["adb", "connect", SERIAL], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    waited = subprocess.run(["adb", "-s", SERIAL, "wait-for-device"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
    if waited.returncode != 0:
        return False, waited.stdout
    for _ in range(180):
        prop = subprocess.run(
            ["adb", "-s", SERIAL, "shell", "getprop", "sys.boot_completed"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15,
        )
        if prop.returncode == 0 and prop.stdout.strip() == "1":
            return True, "sys.boot_completed=1"
        time.sleep(1)
    return False, "sys.boot_completed did not become 1"


def start() -> int:
    if not CONFIG.exists():
        raise RuntimeError(f"runtime config missing: {CONFIG}")
    ours, outside = processes()
    if outside:
        record("CVD_START_BLOCKED_BY_HOST_ISOLATION.txt", [
            f"CHECKED_AT={now()}", "RESULT=BLOCKED",
            "REASON=another user CVD is active", *outside,
        ])
        return 75
    if ours:
        raise RuntimeError("RQ4 CVD already appears to be running")
    attempts: list[str] = [f"START_REQUESTED_AT={now()}", f"CONFIG={CONFIG}", f"IMAGES={IMAGES}"]
    for attempt in (1, 2):
        started = now()
        proc = run_logged([str(RUN_CVD), f"--system_image_dir={IMAGES}"], timeout=600)
        attempts.extend([
            f"ATTEMPT_{attempt}_STARTED_AT={started}",
            f"ATTEMPT_{attempt}_COMPLETED_AT={now()}",
            f"ATTEMPT_{attempt}_RETURN_CODE={proc.returncode}",
            f"ATTEMPT_{attempt}_OUTPUT_BEGIN", proc.stdout,
            f"ATTEMPT_{attempt}_OUTPUT_END",
        ])
        ready, ready_output = wait_android() if proc.returncode == 0 else (False, "run_cvd nonzero")
        attempts.append(f"ATTEMPT_{attempt}_ANDROID_READY={'yes' if ready else 'no'}:{ready_output}")
        if ready:
            attempts.append(f"RESULT=PASS")
            record("CVD_LAUNCH.txt", attempts)
            return 0
        stopped = run_logged([str(STOP_CVD)], timeout=180)
        attempts.extend([
            f"ATTEMPT_{attempt}_RECOVERY_STOP_RETURN_CODE={stopped.returncode}",
            stopped.stdout,
        ])
        time.sleep(2)
    attempts.append("RESULT=FAIL")
    record("CVD_LAUNCH.txt", attempts)
    return 1


def stop() -> int:
    started = now()
    proc = run_logged([str(STOP_CVD)], timeout=240)
    record("CVD_STOP.txt", [
        f"STARTED_AT={started}", f"COMPLETED_AT={now()}",
        f"RETURN_CODE={proc.returncode}", proc.stdout,
    ])
    return proc.returncode


def status() -> int:
    ours, outside = processes()
    print(json.dumps({"rq4_processes": ours, "outside_processes": outside}, indent=2))
    return 0 if ours and not outside else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    if args.action == "start":
        return start()
    if args.action == "stop":
        return stop()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
