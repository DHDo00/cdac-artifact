#!/usr/bin/env python3
"""Per-boot health block (protocol §5). Usage: driver_health.py <runtime> <outdir>"""
import hashlib, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import runtime_lib as R
runtime=Path(sys.argv[1]); out=Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
cfg=json.loads((runtime/"boot_cfg.json").read_text())
CSV=[]
def fa(name): return R.sh(f"sha256sum /data/media/0/espafd_tree/{name}.bin").stdout.strip().split()[0]
def req(step,label,pkg,uri,payload,expect,qc_pre=None,esha=None):
    assert len(payload)==16,(label,payload)
    target="X" if uri==R.X_URI else "Y"
    pre=fa(target)
    R.sh("logcat -c; logcat -b kernel -c")
    R.write_action(pkg,label,payload,uri)
    c=R.read_app_csv(pkg,label)
    parts=(c or "").split(",")
    res=parts[3] if len(parts)>3 else "?"
    after=fa(target)
    qc=R.qc()
    delta=(R.qc_field(qc,"file_open_deny")-R.qc_field(qc_pre,"file_open_deny")) if qc_pre else None
    if expect=="deny":
        dump=R.policy_dump(); p=R.parse_dump(dump)
        rule=any(kv.get("caller_uid")==str(cfg["A"]) and kv.get("ino")==str(cfg["X"]) and kv.get("s_dev")=="254:96" and kv.get("decision")=="would-deny" for _,kv in p["slots"])
        ok=rule and res.startswith("WRITE_FAIL") and after==pre and (delta or 0)>=1
        v="DENY_PASS" if ok else "DENY_FAIL"
    else:
        ok=res.startswith("WRITE_OK") and after==esha
        v="ALLOW_PASS" if ok else "ALLOW_FAIL"
    CSV.append({"step":step,"label":label,"verdict":v,"result":res,"deny_delta":delta})
    print(f"[{step}] {label}: {v} result={res} deny_delta={delta}")
    return v
R.clear_policy()
req("H0","rcs21_b2_H0_A_X",R.A_PKG,R.X_URI,"B2H0ALLOWPPPPPPP","allow",esha=hashlib.sha256(b"B2H0ALLOWPPPPPPP").hexdigest())
R.restore_x("rcs21_b2_H1_restore"); time.sleep(1)
R.sh("logcat -c; logcat -b kernel -c")
R.timed_run("rcs21_b2_H1","H1",1,1,"rcs21_b2_H1.csv"); time.sleep(3)
h1=R.pull_timing_csv("rcs21_b2_H1.csv"); (out/"b2_health_H1.csv").write_text(h1)
print("[H1] rows:", h1.count("\n")-1 if h1 else 0)
R.install_config(1,cfg,out,"rcs21_b2_H2")
qc=R.qc()
req("H2","rcs21_b2_H2_A_X",R.A_PKG,R.X_URI,"B2H2DENYPPPPPPPP","deny",qc_pre=qc)
req("H3a","rcs21_b2_H3_A_Y",R.A_PKG,R.Y_URI,"B2H3AYPPPPPPPPPP","allow",esha=hashlib.sha256(b"B2H3AYPPPPPPPPPP").hexdigest())
req("H3b","rcs21_b2_H3_B_X",R.B_PKG,R.X_URI,"B2H3BXPPPPPPPPPP","allow",esha=hashlib.sha256(b"B2H3BXPPPPPPPPPP").hexdigest())
R.clear_policy()
req("H3c","rcs21_b2_H3c_A_X",R.A_PKG,R.X_URI,"B2H3RXPPPPPPPPPP","allow",esha=hashlib.sha256(b"B2H3RXPPPPPPPPPP").hexdigest())
(out/"b2_health_results.json").write_text(json.dumps(CSV,indent=1))
print("HEALTH_DONE")
