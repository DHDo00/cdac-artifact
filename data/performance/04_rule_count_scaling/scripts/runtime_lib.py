#!/usr/bin/env python3
"""Round-21 runtime helpers (frozen usage; adb serial 0.0.0.0:6540, cvd-21)."""
import json, os, subprocess, sys, time, hashlib
from pathlib import Path

ADB = "adb"
SERIAL = "0.0.0.0:6540"
POLICY = "/data/local/tmp/iguardctl_test"
A_PKG = "com.demo.espafdtest"
B_PKG = "com.demo.espafdtestb"
T_PKG = "com.demo.esptiming"
TREE = "content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree"
X_URI = TREE + "/document/primary%3Aespafd_tree%2FX.bin"
Y_URI = TREE + "/document/primary%3Aespafd_tree%2FY.bin"
WS = Path("21_rule_count_scaling_20261026")

sys.path.insert(0, str(WS / "03_rulegen"))
import rules as rules_mod  # noqa: E402


def adb(*a, timeout=120):
    p = subprocess.run([ADB, "-s", SERIAL] + list(a), capture_output=True,
                       text=True, timeout=timeout)
    return p


def sh(c, timeout=120):
    return adb("shell", c, timeout=timeout)


def guest(pkg, path, timeout=30):
    return sh(f"run-as {pkg} cat files/{path}", timeout=timeout)


def policy_dump(timeout=30):
    return sh("cat /sys/kernel/debug/iguard/policy_dump", timeout=timeout).stdout


def parse_dump(text):
    count = None
    slots = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("runtime_policy_count="):
            count = int(line.split("=", 1)[1])
        elif line.startswith("[") and "]" in line:
            idx = int(line[1:line.index("]")])
            kv = {}
            for tok in line[line.index("]") + 1:].strip().split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    kv[k] = v
            slots.append((idx, kv))
    return {"count": count, "slots": slots, "n_slots": len(slots)}


def clear_policy(timeout=30):
    p = sh(f"{POLICY} clear", timeout=timeout)
    dump = policy_dump()
    parsed = parse_dump(dump)
    return {"stdout": p.stdout, "rc": p.returncode,
            "count_after": parsed["count"], "dump": dump}


def add_rule(cmd, timeout=30):
    return sh(f"{POLICY} {cmd}", timeout=timeout)


def install_config(N, cfg, outdir, label, verify_only=True):
    """clear + install config_N; read back and verify actual active count == N."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    clear = clear_policy()
    adds = []
    for kind, cmd in rules_mod.rules_for_scale(N, cfg):
        p = add_rule(cmd)
        adds.append({"kind": kind, "cmd": cmd, "rc": p.returncode,
                     "stdout": p.stdout.strip(), "stderr": p.stderr.strip()})
    dump = policy_dump()
    parsed = parse_dump(dump)
    rec = {"label": label, "N_requested": N, "clear": clear,
           "adds": adds, "count_actual": parsed["count"],
           "n_slots_actual": parsed["n_slots"], "slots": parsed["slots"]}
    rec["verified"] = (parsed["count"] == N and parsed["n_slots"] == N
                       and all(a["rc"] == 0 for a in adds))
    (outdir / f"{label}_policy_dump.txt").write_text(dump)
    (outdir / f"{label}_install.json").write_text(json.dumps(rec, indent=1))
    return rec


def discover_boot_cfg(runtime_dir):
    """Collect UIDs, inos, dev, identity. Frozen structure, runtime values."""
    pkglist = sh("cmd package list packages -U").stdout
    def uid_of(pkg):
        for line in pkglist.splitlines():
            if line.startswith(f"package:{pkg} uid:"):
                return int(line.split("uid:")[1].strip())
        return None
    A = uid_of(A_PKG); B = uid_of(B_PKG); T = uid_of(T_PKG)
    xstat = sh("stat -c '%i %d %s' /data/media/0/espafd_tree/X.bin").stdout.strip().split()
    ystat = sh("stat -c '%i %d %s' /data/media/0/espafd_tree/Y.bin").stdout.strip().split()
    Xino, Xdev, Xsz = int(xstat[0]), int(xstat[1]), int(xstat[2])
    Yino = int(ystat[0])
    devraw = rules_mod.s_dev_raw(Xdev)
    fp = sh("getprop ro.build.fingerprint").stdout.strip()
    kern = sh("uname -r").stdout.strip()
    selinux = sh("getenforce").stdout.strip()
    iguard = sh("test -c /dev/iguard_ctl && echo yes || echo no").stdout.strip()
    cfg = {"A": A, "B": B, "T": T, "X": Xino, "Y": Yino, "Xdev": Xdev,
           "Xsize": Xsz, "DEVRAW": devraw, "fingerprint": fp, "kernel": kern,
           "selinux": selinux, "iguard_ctl": iguard,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (Path(runtime_dir) / "boot_cfg.json").write_text(json.dumps(cfg, indent=1))
    return cfg


def file_state(files=("X", "Y"), outdir=None, tag="state"):
    """stat size/dev/ino + sha256 for each fixture file, host-side collection."""
    rows = {}
    for name in files:
        p = sh(f"stat -c '%n %s %d %i' /data/media/0/espafd_tree/{name}.bin "
               f"&& sha256sum /data/media/0/espafd_tree/{name}.bin")
        rows[name] = p.stdout.strip()
    if outdir:
        Path(outdir).mkdir(parents=True, exist_ok=True)
        (Path(outdir) / f"file_state_{tag}.txt").write_text(
            json.dumps(rows, indent=1) + "\n")
    return rows


def qc():
    return sh("cat /sys/kernel/debug/iguard/quiet_counters").stdout


def qc_field(text, field):
    for line in text.splitlines():
        if line.startswith(field + "="):
            return int(line.split("=", 1)[1])
    return None


def loadavg():
    with open("/proc/loadavg") as f:
        return f.read().strip()


def am_start(pkg, extras, uri, timeout=120):
    cmd = ["shell", "am", "start", "-W", "-n", f"{pkg}/.MainActivity"]
    for k, v in extras.items():
        if isinstance(v, bool):
            cmd += ["--ez", k, "true" if v else "false"]
        elif isinstance(v, int):
            cmd += ["--ei", k, str(v)]
        else:
            cmd += ["--es", k, str(v)]
    cmd += ["-d", uri]
    return adb(*cmd, timeout=timeout)


def write_action(pkg, label, payload, uri, mode="w"):
    return am_start(pkg, {"action": "write", "label": label,
                          "content": payload, "mode": mode}, uri)


def read_app_csv(pkg, label, retries=60, interval=0.5):
    for _ in range(retries):
        r = guest(pkg, label + ".csv")
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[-1]
        time.sleep(interval)
    return None


def timed_run(label, state, warmup, record, outname):
    """timing-app restore not included; caller does that. Returns am output."""
    return am_start(T_PKG, {"action": "timed", "mode": "w", "state": state,
                            "label": label, "content": "0123456789ABCD",
                            "warmup": warmup, "record": record, "out": outname},
                    X_URI)


def restore_x(label):
    return am_start(T_PKG, {"action": "restore", "mode": "w", "label": label,
                            "content": "0123456789ABCD"}, X_URI)


def pull_timing_csv(outname):
    return adb("shell",
               f"cat /sdcard/Android/data/{T_PKG}/files/timing/{outname}").stdout


def kernel_log(marker_grep=None, tail=400):
    if marker_grep:
        return sh(f"logcat -b kernel -d | grep -E '{marker_grep}' | tail -{tail}").stdout
    return sh(f"logcat -b kernel -d | tail -{tail}").stdout
