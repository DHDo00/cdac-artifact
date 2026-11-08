#!/usr/bin/env python3
"""Round-26 serial health block (before concurrency): 3x per request."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import runtime_lib as R
runtime = Path(sys.argv[1]); out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
cfg = json.loads((runtime/"boot_cfg.json").read_text())
X = R.uri_for("X"); Y = R.uri_for("Y")
rule = ("add service_id=5 op_id=401 caller_uid={A} operation=openAssetFile "
        "ino={X} s_dev={D} i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 "
        "decision=deny reason=rcs26_tgt_A_X").format(A=cfg["A"], X=cfg["Xino"], D=cfg["DEVRAW"])
rows=[]
def row(label, verdict, res, ex, dd, seq):
    rows.append({"label":label,"verdict":verdict,"result":res,"ex":ex,"deny_d":dd,"seq":seq})
    print(f"[health] {label}: {verdict} res={res} ex={ex} deny_d={dd} seq={seq}")
def serial_write(label, pkg, uri, payload, offset, expect):
    R.clear_logs(); qc0=R.qc()
    pre = R.file_state(["X" if uri==X else "Y"])
    R.write_action(pkg, label, payload, uri, mode="w", offset=offset)
    time.sleep(2.5)
    csv = R.last_csv(pkg, label)
    qc1=R.qc(); qd=R.qc_delta(qc0,qc1,["file_open_deny"])
    post = R.file_state(["X" if uri==X else "Y"])
    fw = R.framework_log(); kern = R.kernel_log()
    (out/f"{label}_app.txt").write_text((csv or "NO_ROW")+"\n")
    (out/f"{label}_fw.txt").write_text(fw+"\n")
    (out/f"{label}_kernel.txt").write_text(kern+"\n")
    parts=(csv or "").split(",")
    res=parts[3] if len(parts)>3 else "?"
    ex=parts[4] if len(parts)>4 else ""
    dd=qd.get("file_open_deny")
    if expect=="DENY":
        ok=(res.startswith("WRITE_FAIL") and pre==post and (dd or 0)>=1 and "real-enforce" in kern)
        v="DENY_PASS" if ok else "DENY_FAIL"
    else:
        target="X" if uri==X else "Y"
        marker=payload
        ok=(res=="WRITE_OK" and R.read_marker(f"/data/media/0/espafd_tree/{R.FILES[target]}", offset)==R.sha_hex(marker))
        v="ALLOW_PASS" if ok else "ALLOW_FAIL"
    row(label,v,res,ex,dd,None)
    return v
R.clear_policy()
# H0: no rule, 4 requests, capability usable
serial_write("r26_h0_AX", R.A_PKG, X, R.p16("H0_AX"), 0, "ALLOW")
serial_write("r26_h0_AY", R.A_PKG, Y, R.p16("H0_AY"), 0, "ALLOW")
serial_write("r26_h0_BX", R.B_PKG, X, R.p16("H0_BX"), 4096, "ALLOW")
serial_write("r26_h0_BY", R.B_PKG, Y, R.p16("H0_BY"), 4096, "ALLOW")
# repeat x3 total? protocol serial health 3x: rerun the same block twice more with fresh labels
for rep in (2,3):
    serial_write(f"r26_h0_AX_r{rep}", R.A_PKG, X, R.p16(f"H0_AX_r{rep}"), 0, "ALLOW")
    serial_write(f"r26_h0_AY_r{rep}", R.A_PKG, Y, R.p16(f"H0_AY_r{rep}"), 0, "ALLOW")
    serial_write(f"r26_h0_BX_r{rep}", R.B_PKG, X, R.p16(f"H0_BX_r{rep}"), 4096, "ALLOW")
    serial_write(f"r26_h0_BY_r{rep}", R.B_PKG, Y, R.p16(f"H0_BY_r{rep}"), 4096, "ALLOW")
# H1: install rule, A->X deny, others allow
inst=R.install_single_rule(rule, out, "r26_health_rule")
print("[health] rule verified:", inst["verified"], inst["count_actual"])
for rep in (1,2,3):
    serial_write(f"r26_h1_AX_{rep}", R.A_PKG, X, R.p16(f"H1_AX_{rep}"), 0, "DENY")
    serial_write(f"r26_h1_AY_{rep}", R.A_PKG, Y, R.p16(f"H1_AY_{rep}"), 0, "ALLOW")
    serial_write(f"r26_h1_BX_{rep}", R.B_PKG, X, R.p16(f"H1_BX_{rep}"), 4096, "ALLOW")
    serial_write(f"r26_h1_BY_{rep}", R.B_PKG, Y, R.p16(f"H1_BY_{rep}"), 4096, "ALLOW")
# H2: clear, A->X recover
R.clear_policy()
for rep in (1,2,3):
    serial_write(f"r26_h2_AX_{rep}", R.A_PKG, X, R.p16(f"H2_AX_{rep}"), 0, "ALLOW")
(out/"health_results.jsonl").write_text("\n".join(json.dumps(r) for r in rows)+"\n")
with open(out/"health_results.csv","w") as f:
    f.write("label,verdict,result,ex,deny_d,seq\n")
    for r in rows:
        f.write(f"{r['label']},{r['verdict']},{r['result']},{r['ex']},{r['deny_d']},{r['seq']}\n")
print("HEALTH_DONE", sum(1 for r in rows if r["verdict"].endswith("PASS")), "PASS /", len(rows))
