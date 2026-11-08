#!/usr/bin/env python3
"""Wait for settled boot; set LOG_OFF config; capture boot identity."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import runtime_lib as R

runtime = Path(sys.argv[1])
R.adb("connect", R.SERIAL, timeout=30)
R.sh('setprop persist.debug.cdac.logging_mode quiet')
for i in range(80):
    bc = R.sh("getprop sys.boot_completed").stdout.strip()
    up = R.sh("cat /proc/uptime").stdout.strip().split()[0]
    try:
        upi = int(float(up))
    except Exception:
        upi = 0
    if bc == "1" and upi >= 180:
        R.sh("mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true; "
             "echo 0 > /sys/kernel/debug/iguard/verbose_audit")
        R.sh("am force-stop com.android.externalstorage")
        time.sleep(2)
        va = R.sh("cat /sys/kernel/debug/iguard/verbose_audit").stdout.strip()
        lm = R.sh("getprop persist.debug.cdac.logging_mode").stdout.strip()
        abr = R.sh("cat /sys/kernel/debug/iguard/ablate_disable_runtime").stdout.strip()
        abc = R.sh("cat /sys/kernel/debug/iguard/ablate_disable_ctx").stdout.strip()
        info = {"boot_completed": bc, "uptime_s": upi, "verbose_audit": va,
                "logging_mode": lm, "ablate_disable_runtime": abr,
                "ablate_disable_ctx": abc}
        (runtime / "boot_prep.json").write_text(json.dumps(info, indent=1))
        print(json.dumps(info, indent=1))
        sys.exit(0)
    time.sleep(5)
print("boot_prep timeout"); sys.exit(1)
