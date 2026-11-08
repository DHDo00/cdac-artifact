#!/usr/bin/env python3
"""Correctness phase driver (frozen protocol §5-§6). Usage:
driver_correctness.py <runtime> <outdir>"""
import hashlib, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import runtime_lib as R

runtime = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
cfg = json.loads((runtime / "boot_cfg.json").read_text())
payloads = json.loads((R.WS / "03_rulegen/payloads.json").read_text())
CSV = []
INIT_SHA = hashlib.sha256(b"0123456789ABCD").hexdigest()

def parse_a_csv(csv):
    if not csv:
        return {"raw": None}
    parts = csv.split(",")
    return {"raw": csv, "result": parts[3] if len(parts) > 3 else "?",
            "exception": parts[4] if len(parts) > 4 else "",
            "dev": parts[10] if len(parts) > 10 else "",
            "ino": parts[11] if len(parts) > 11 else "",
            "size": parts[13] if len(parts) > 13 else "",
            "uid": parts[16] if len(parts) > 16 else ""}

def file_sha(name):
    p = R.sh(f"sha256sum /data/media/0/espafd_tree/{name}.bin").stdout.strip().split()
    return p[0] if p else ""

def file_size(name):
    p = R.sh(f"stat -c %s /data/media/0/espafd_tree/{name}.bin").stdout.strip()
    return p

def one_request(step, label, pkg, uri, payload, expect, scale, it, qc_pre,
                expect_sha, deny_ino=None):
    assert len(payload.encode()) == 16, (label, payload)
    target = "X" if uri == R.X_URI else "Y"
    pre_sha = file_sha(target)
    rec = {"step": step, "label": label, "scale": scale, "iter": it,
           "pkg": pkg, "expect": expect, "payload": payload,
           "file_sha_before": pre_sha}
    R.sh("logcat -c; logcat -b kernel -c")
    R.write_action(pkg, label, payload, uri)
    csv = R.read_app_csv(pkg, label)
    rec["app"] = parse_a_csv(csv)
    rec["kernel_key"] = R.kernel_log(
        r"real-enforce|deny-now|iguard_ctx: decision", tail=40)
    rec["policy_dump"] = R.policy_dump()
    rec["qc_post"] = R.qc()
    if qc_pre is not None:
        rec["file_open_deny_delta"] = (
            R.qc_field(rec["qc_post"], "file_open_deny") -
            R.qc_field(qc_pre, "file_open_deny"))
    if uri == R.X_URI:
        rec["file_sha_after"] = file_sha("X")
        rec["file_size_after"] = file_size("X")
    else:
        rec["file_sha_after"] = file_sha("Y")
        rec["file_size_after"] = file_size("Y")
    # verdict
    if expect == "deny":
        # LOG_OFF: iguard_vinfo real-enforce line is gated off; enforcement basis =
        # file_open_deny quiet-counter increment (only the real-enforce branch
        # increments it) + rule state + no capability + no side effect.
        parsed = R.parse_dump(rec["policy_dump"])
        rule_ok = False
        for idx, kv in parsed["slots"]:
            if (kv.get("service_id") == "5" and kv.get("op_id") == "401"
                    and kv.get("caller_uid") == str(cfg["A"])
                    and kv.get("operation") == "openAssetFile"
                    and kv.get("ino") == str(cfg["X"])
                    and kv.get("s_dev") == "254:96"
                    and kv.get("decision") == "would-deny"):
                rule_ok = True
        no_side = rec["file_sha_after"] == pre_sha
        no_deliv = rec["app"]["result"].startswith("WRITE_FAIL")
        denydelta = (rec.get("file_open_deny_delta") or 0) >= 1
        ok = rule_ok and no_side and no_deliv and denydelta
        rec["verdict"] = "DENY_PASS" if ok else "DENY_FAIL"
        rec["criteria"] = {"rule_state_subject_object_op": bool(rule_ok),
                           "no_side_effect": bool(no_side),
                           "no_capability": bool(no_deliv),
                           "deny_counter_inc": bool(denydelta),
                           "kernel_real_enforce_line_seen": (
                               "real-enforce" in rec["kernel_key"]),
                           "note": "real-enforce text line is gated off under "
                                   "LOG_OFF; captured separately in diag phase"}
    else:
        ok = rec["app"]["result"].startswith("WRITE_OK") and \
             rec["file_sha_after"] == expect_sha and \
             rec["file_size_after"] == "16" and \
             rec["app"]["ino"] == str(cfg["X"] if uri == R.X_URI else cfg["Y"])
        rec["verdict"] = "ALLOW_PASS" if ok else "ALLOW_FAIL"
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    CSV.append(rec)
    print(f"[{step}] {label}: {rec['verdict']} result={rec['app']['result']} "
          f"sha={rec['file_sha_after'][:12]} deny_delta={rec.get('file_open_deny_delta')}")
    return rec

def dump_progress():
    (out / "correctness_results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in CSV) + "\n")
    (out / "correctness_results.csv").write_text(
        "step,label,scale,iter,pkg,expect,verdict,result,exception,uid,ino,"
        "file_sha_after,file_size_after,deny_delta\n" + "\n".join(
            f"{r['step']},{r['label']},{r.get('scale')},{r.get('iter')},"
            f"{r['pkg']},{r['expect']},{r['verdict']},{r['app']['result']},"
            f"{r['app']['exception']},{r['app']['uid']},{r['app']['ino']},"
            f"{r.get('file_sha_after')},{r.get('file_size_after')},"
            f"{r.get('file_open_deny_delta')}" for r in CSV) + "\n")

def clear_and_verify():
    c = R.clear_policy()
    if c["count_after"] != 0:
        print("WARN clear count != 0:", c["count_after"])
    return c

# ---- health block (§5) ----
R.clear_policy()
qc0 = R.qc()
one_request("H0", "rcs21_health_H0_A_X", R.A_PKG, R.X_URI, "H0ALLOWPPPPPPPPP",
            "allow", "health", 0, qc0, hashlib.sha256(b"H0ALLOWPPPPPPPPP").hexdigest())
R.clear_policy()
R.restore_x("rcs21_health_H1_restore")
time.sleep(1)
R.sh("logcat -c; logcat -b kernel -c")
R.timed_run("rcs21_health_H1", "H1", 1, 1, "rcs21_health_H1.csv")
time.sleep(3)
h1 = R.pull_timing_csv("rcs21_health_H1.csv")
(out / "health_H1_timing.csv").write_text(h1)
print("[H1] timing rows:", h1.count("\n") - 1 if h1 else 0)
inst = R.install_config(1, cfg, out, "rcs21_health_H2")
qc_pre2 = R.qc()
one_request("H2", "rcs21_health_H2_A_X", R.A_PKG, R.X_URI, "H2DENYPPPPPPPPPP",
            "deny", "health", 0, qc_pre2, hashlib.sha256(b"H2DENYPPPPPPPPPP").hexdigest())
one_request("H3a", "rcs21_health_H3_A_Y", R.A_PKG, R.Y_URI, "H3AYPPPPPPPPPPPP",
            "allow", "health", 0, None, hashlib.sha256(b"H3AYPPPPPPPPPPPP").hexdigest())
one_request("H3b", "rcs21_health_H3_B_X", R.B_PKG, R.X_URI, "H3BXPPPPPPPPPPPP",
            "allow", "health", 0, None, hashlib.sha256(b"H3BXPPPPPPPPPPPP").hexdigest())
clear_and_verify()
one_request("H3c", "rcs21_health_H3c_A_X_restore", R.A_PKG, R.X_URI,
            "H3RXPPPPPPPPPPPP", "allow", "health", 0, None,
            hashlib.sha256(b"H3RXPPPPPPPPPPPP").hexdigest())
dump_progress()

# ---- scales (§6) ----
for N in [1, 8, 32, 128]:
    for it in range(1, 4):
        R.clear_policy()
        inst = R.install_config(N, cfg, out, f"rcs21_corr_N{N}_it{it}")
        if not inst["verified"]:
            print(f"[N{N} it{it}] config NOT verified (count={inst['count_actual']})")
        qc_pre = R.qc()
        d = payloads[f"deny_A_X_{N}_{it}"]
        a = payloads[f"allow_A_Y_{N}_{it}"]
        b = payloads[f"allow_B_X_{N}_{it}"]
        r = payloads[f"restore_A_X_{N}_{it}"]
        one_request("T1", f"rcs21_N{N}_it{it}_T1_A_X", R.A_PKG, R.X_URI, d["payload"],
                    "deny", N, it, qc_pre, d["sha256"])
        one_request("T2", f"rcs21_N{N}_it{it}_T2_A_Y", R.A_PKG, R.Y_URI, a["payload"],
                    "allow", N, it, None, a["sha256"])
        one_request("T3", f"rcs21_N{N}_it{it}_T3_B_X", R.B_PKG, R.X_URI, b["payload"],
                    "allow", N, it, None, b["sha256"])
        clear_and_verify()
        one_request("T4", f"rcs21_N{N}_it{it}_T4_A_X_restore", R.A_PKG, R.X_URI,
                    r["payload"], "allow", N, it, None, r["sha256"])
        dump_progress()

# ---- position check (§6, N=128 target last, 3 denies) ----
R.clear_policy()
for kind, cmd in R.rules_mod.rules_for_scale(128, cfg)[1:]:   # fillers only
    R.add_rule(cmd)
R.add_rule(R.rules_mod.target_cmd(cfg))
dump = R.policy_dump()
inst128 = R.parse_dump(dump)
(out / "rcs21_pos_N128_target_last_policy_dump.txt").write_text(dump)
print("[pos128] count=", inst128["count"], "n_slots=", inst128["n_slots"])
for it in range(1, 4):
    qc_pre = R.qc()
    payload = "PZ128PPPPPPPPPPP"
    one_request("POS", f"rcs21_pos_N128_it{it}_A_X", R.A_PKG, R.X_URI,
                payload, "deny", 128, it, qc_pre,
                hashlib.sha256(payload.encode()).hexdigest())
    dump_progress()
clear_and_verify()
(out / "CORRECTNESS_DONE.txt").write_text(
    f"done={time.strftime('%Y-%m-%dT%H:%M:%S%z')} rows={len(CSV)}\n")
print("CORRECTNESS_DONE rows=", len(CSV))
