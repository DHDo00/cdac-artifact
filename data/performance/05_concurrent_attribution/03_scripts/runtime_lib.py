#!/usr/bin/env python3
"""Round-26 runtime helpers (cvd-26, ADB 0.0.0.0:6545). Observability: audit+verbose."""
import hashlib, json, re, subprocess, sys, time
from pathlib import Path

ADB = "adb"
SERIAL = "0.0.0.0:6545"
POLICY = "/data/local/tmp/iguardctl_test"
A_PKG = "com.demo.espafdtest"
B_PKG = "com.demo.espafdtestb"
TREE = "content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree"
WS = Path("26_concurrent_attribution_20261027")
RELEASE_ACTION = "com.demo.cdac26.RELEASE"

FILES = {"X": "ccx.bin", "Y": "ccy.bin"}

def uri_for(name):
    return TREE + "/document/primary%3Aespafd_tree%2F" + FILES[name]

def p16(label):
    return (label + "0123456789ABCDEF")[:16].encode()

def sha_hex(b):
    return hashlib.sha256(b).hexdigest()

def adb(*a, timeout=180):
    return subprocess.run([ADB, "-s", SERIAL] + list(a),
                          capture_output=True, text=True, timeout=timeout)

def sh(c, timeout=180):
    return adb("shell", c, timeout=timeout)

def guest(pkg, path, timeout=60):
    return sh(f"run-as {pkg} cat files/{path}", timeout=timeout)

def last_csv(pkg, label, timeout=60):
    r = guest(pkg, label + ".csv", timeout=timeout)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    lines = [l for l in r.stdout.strip().splitlines()
             if l.strip() and l.split(",", 1)[0] == label]
    return lines[-1].strip() if lines else None

def clear_logs():
    sh("logcat -c", timeout=60)

def framework_log(tail=600):
    p = sh("logcat -d -v epoch 2>/dev/null", timeout=60).stdout
    lines = [l for l in p.splitlines()
             if re.search(r"CDAC_ENDPOINT_RESOLVE|CDAC_CONTEXT_ENTER|CDAC_CONTEXT_EXIT|"
                          r"CDAC_FRAMEWORK_CONTEXT_PUBLISH|CDAC_BINDER_ENTRY|CDAC_BINDER_EXIT|"
                          r"CDAC_BINDER_EXCEPTION_EXIT|CDAC_CONTEXT_STACK_MISMATCH|"
                          r"CDAC_FRAMEWORK_COUNTER_DUMP", l)]
    return "\n".join(lines[-tail:])

def kernel_log(tail=4000, epoch=True):
    flag = " -v epoch" if epoch else ""
    p = sh(f"logcat -b kernel -d{flag} 2>/dev/null", timeout=60).stdout
    if not p.strip():
        p = sh("dmesg 2>/dev/null", timeout=60).stdout
    lines = p.splitlines()
    out = [l for l in lines
           if re.search(r"service_id=5|CDAC_BINDER_STACK_MISMATCH|CDAC_CTL_REJECT", l)]
    return "\n".join(out[-tail:])

def qc():
    return sh("cat /sys/kernel/debug/iguard/quiet_counters", timeout=60).stdout

def qc_field(text, field):
    for line in text.splitlines():
        if line.startswith(field + "="):
            try:
                return int(line.split("=", 1)[1])
            except Exception:
                return None
    return None

def qc_delta(pre_text, post_text, fields):
    out = {}
    for f in fields:
        a = qc_field(pre_text, f)
        b = qc_field(post_text, f)
        out[f] = None if (a is None or b is None) else (b - a)
    return out

def policy_dump(timeout=60):
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

def clear_policy(timeout=60):
    p = sh(f"{POLICY} clear", timeout=timeout)
    dump = policy_dump()
    parsed = parse_dump(dump)
    return {"stdout": p.stdout.strip(), "rc": p.returncode,
            "count_after": parsed["count"], "dump": dump, "parsed": parsed}

def add_rule(cmd, timeout=60):
    return sh(f"{POLICY} {cmd}", timeout=timeout)

def install_single_rule(cmd, outdir, label):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    clear = clear_policy()
    adds = []
    p = add_rule(cmd)
    adds.append({"cmd": cmd, "rc": p.returncode, "stdout": p.stdout.strip(),
                 "stderr": p.stderr.strip()})
    dump = policy_dump()
    parsed = parse_dump(dump)
    rec = {"label": label, "clear": clear, "adds": adds,
           "count_actual": parsed["count"], "n_slots_actual": parsed["n_slots"],
           "slots": parsed["slots"]}
    rec["verified"] = (parsed["count"] == 1 and parsed["n_slots"] == 1
                       and all(a["rc"] == 0 for a in adds))
    (outdir / f"{label}_policy_dump.txt").write_text(dump)
    (outdir / f"{label}_install.json").write_text(json.dumps(rec, indent=1))
    return rec

def discover_boot_cfg(runtime_dir):
    pkglist = sh("cmd package list packages -U").stdout
    def uid_of(pkg):
        for line in pkglist.splitlines():
            if line.startswith(f"package:{pkg} uid:"):
                return int(line.split("uid:")[1].strip())
        return None
    A = uid_of(A_PKG); B = uid_of(B_PKG)
    stats = {}
    for key, name in FILES.items():
        try:
            st = sh(f"stat -c '%i %d %s' /data/media/0/espafd_tree/{name}").stdout.strip().split()
            stats[key] = {"ino": int(st[0]), "dev": int(st[1]), "size": int(st[2])}
        except Exception:
            stats[key] = {"ino": None, "dev": None, "size": None}
    xstat = stats["X"]
    devraw = ((xstat["dev"] >> 8) << 20) + (xstat["dev"] & 255)
    cfg = {"A": A, "B": B, "stats": stats, "Xino": xstat["ino"],
           "Xdev": xstat["dev"], "DEVRAW": devraw,
           "fingerprint": sh("getprop ro.build.fingerprint").stdout.strip(),
           "kernel": sh("uname -r").stdout.strip(),
           "selinux": sh("getenforce").stdout.strip(),
           "iguard_ctl": sh("test -c /dev/iguard_ctl && echo yes || echo no").stdout.strip(),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (Path(runtime_dir) / "boot_cfg.json").write_text(json.dumps(cfg, indent=1))
    return cfg

def file_state(names, outdir=None, tag="state"):
    rows = {}
    for name in names:
        n = FILES[name]
        p = sh(f"stat -c '%s %d %i %y' /data/media/0/espafd_tree/{n} 2>/dev/null && "
               f"sha256sum /data/media/0/espafd_tree/{n} 2>/dev/null || echo MISSING")
        rows[name] = p.stdout.strip()
    if outdir:
        Path(outdir).mkdir(parents=True, exist_ok=True)
        (Path(outdir) / f"file_state_{tag}.txt").write_text(
            json.dumps(rows, indent=1) + "\n")
    return rows

def esp_pid():
    p = sh("ps -A -o PID,NAME | grep com.android.externalstorage | head -1").stdout.strip()
    return p.split()[0] if p else None

def provider_fd_grep(pid, pattern="espafd_tree"):
    return sh(f"ls -l /proc/{pid}/fd 2>/dev/null | grep '{pattern}' || echo NONE").stdout.strip()

def read_marker(path, offset, length=16):
    p = sh(f"dd if={path} bs=1 skip={offset} count={length} 2>/dev/null | sha256sum").stdout.strip()
    return p.split()[0] if p else ""

def am_start(pkg, extras, uri=None, timeout=180):
    cmd = ["shell", "am", "start", "-W", "-n", f"{pkg}/.MainActivity"]
    for k, v in extras.items():
        if isinstance(v, bool):
            cmd += ["--ez", k, "true" if v else "false"]
        elif isinstance(v, int):
            cmd += ["--ei", k, str(v)]
        elif isinstance(v, str) and re.fullmatch(r"-?\d+", v):
            cmd += ["--el", k, v]
        else:
            cmd += ["--es", k, str(v)]
    if uri:
        cmd += ["-d", uri]
    return adb(*cmd, timeout=timeout)

def create_action(pkg, label, name, content_bytes, tree_uri=TREE):
    return am_start(pkg, {"action": "create", "label": label, "name": name,
                          "content": content_bytes.decode(),
                          "tree_uri": tree_uri})

def write_action(pkg, label, payload_bytes, uri, mode="w", offset=0):
    return am_start(pkg, {"action": "write", "label": label,
                          "content": payload_bytes.decode(), "mode": mode,
                          "offset": str(offset)}, uri)

def wave_action(pkg, label, uri, payload_bytes, offset, wave):
    return am_start(pkg, {"action": "wave", "label": label, "wave": wave,
                          "content": payload_bytes.decode(), "mode": "w",
                          "offset": str(offset)}, uri)

def read_action(pkg, label, uri):
    return am_start(pkg, {"action": "read", "label": label}, uri)

def delete_action(pkg, label, uri):
    return am_start(pkg, {"action": "delete", "label": label}, uri)

def loadavg():
    with open("/proc/loadavg") as f:
        return f.read().strip()
