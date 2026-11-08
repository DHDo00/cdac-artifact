"""Frozen S10 workload invocation and application-output parser."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Callable


APP_FIELDS = [
    "phase", "scenario", "attempt", "uri", "mode", "app_result",
    "usable_pfd", "read_ok", "write_ok", "close_ok", "s_dev", "ino",
    "size", "elapsed_ns", "exception_class", "exception_message",
]


def parse_app_csv(text: str) -> dict[str, str]:
    rows = [row for row in csv.reader(text.splitlines()) if row]
    if not rows:
        return {}
    row = rows[-1]
    while len(row) < len(APP_FIELDS):
        row.append("")
    return dict(zip(APP_FIELDS, row))


def invoke_and_collect(
    adb: Callable[..., object],
    raw_dir: Path,
    trial_id: str,
    condition: str,
    uri: str,
) -> dict[str, object]:
    """Invoke exactly once; caller must create the invocation sentinel first."""
    output_name = f"{trial_id}.csv"
    app_path = f"/sdcard/Android/data/com.demo.s10settings/files/{output_name}"
    cleanup = adb("shell", f"rm -f {app_path}", check=False)
    (raw_dir / "app_output_cleanup.txt").write_text(cleanup.stdout, encoding="utf-8", errors="replace")
    adb("logcat", "-b", "all", "-c", check=False)
    broadcast = adb(
        "shell", "am", "broadcast",
        "-a", "com.demo.s10settings.RUN",
        "-n", "com.demo.s10settings/.S10Receiver",
        "--es", "phase", trial_id,
        "--es", "scenario", f"V3-{condition}",
        "--es", "uri", uri,
        "--es", "mode", "rw",
        "--ei", "attempts", "1",
        "--es", "out", output_name,
        timeout=90,
        check=False,
    )
    (raw_dir / "broadcast.txt").write_text(broadcast.stdout, encoding="utf-8", errors="replace")

    app_text = ""
    for _ in range(80):
        attempt = adb("shell", f"cat {app_path}", timeout=15, check=False)
        if attempt.returncode == 0 and attempt.stdout.strip():
            app_text = attempt.stdout
            break
        time.sleep(0.25)
    (raw_dir / "app.csv").write_text(app_text, encoding="utf-8", errors="replace")
    time.sleep(0.25)
    kernel = adb("logcat", "-b", "kernel", "-d", "-v", "threadtime", check=False)
    all_log = adb("logcat", "-d", "-v", "threadtime", check=False)
    (raw_dir / "kernel_logcat.txt").write_text(kernel.stdout, encoding="utf-8", errors="replace")
    (raw_dir / "all_logcat.txt").write_text(all_log.stdout, encoding="utf-8", errors="replace")
    return {
        "app": parse_app_csv(app_text),
        "app_text": app_text,
        "app_path": app_path,
        "broadcast_returncode": broadcast.returncode,
        "broadcast_output": broadcast.stdout.strip(),
        "kernel_log": kernel.stdout,
        "all_log": all_log.stdout,
    }
