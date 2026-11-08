#!/usr/bin/env python3
"""Round-26 setup: install concurrency APKs, grants, create ccx/ccy (empty)."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import runtime_lib as R
WS = R.WS
runtime = Path(sys.argv[1])
out = runtime / "setup"
out.mkdir(parents=True, exist_ok=True)
log = {}
def run(label, fn):
    t0 = time.time()
    try:
        r = fn()
        log[label] = {"ok": True, "sec": round(time.time()-t0,1), "detail": str(r)[:400]}
        print(f"[setup] {label}: OK {time.time()-t0:.1f}s")
        return r
    except Exception as e:
        log[label] = {"ok": False, "sec": round(time.time()-t0,1), "detail": repr(e)[:400]}
        print(f"[setup] {label}: FAIL {repr(e)[:200]}")
        return None
R.adb("connect", R.SERIAL, timeout=30)
run("install_A", lambda: R.adb("install", "-r", str(WS/"01_fixtures/app_a/build/espafdtest-signed.apk"), timeout=180))
run("install_B", lambda: R.adb("install", "-r", str(WS/"01_fixtures/app_b/build/espafdtest-signed.apk"), timeout=180))
run("push_tool", lambda: R.adb("push", str(WS/"01_fixtures/iguardctl_test"), R.POLICY, timeout=120))
run("chmod_tool", lambda: R.sh(f"chmod 755 {R.POLICY}"))
S = WS/"03_scripts"
def has_grant(pkg):
    g = R.guest(pkg, "grants.txt").stdout
    return ("primary%3Aespafd_tree" in g or "primary:espafd_tree" in g)
if not has_grant(R.A_PKG):
    run("grant_A_create", lambda: subprocess.run(
        ["bash", str(S/"saf_grant_create.sh"), R.A_PKG, R.A_PKG+"/.MainActivity", "espafd_tree"],
        capture_output=True, text=True, timeout=180).stdout)
    time.sleep(2)
if not has_grant(R.B_PKG):
    run("grant_B_existing", lambda: subprocess.run(
        ["bash", str(S/"saf_grant_existing.sh"), R.B_PKG, R.B_PKG+"/.MainActivity", "espafd_tree"],
        capture_output=True, text=True, timeout=180).stdout)
    time.sleep(2)
log["grants"] = {"A": R.guest(R.A_PKG, "grants.txt").stdout, "B": R.guest(R.B_PKG, "grants.txt").stdout}
assert has_grant(R.A_PKG) and has_grant(R.B_PKG), "grants missing"
# own files: empty content ("-") ; distinct offsets used later (A offset 0, B offset 4096)
run("create_ccx", lambda: R.create_action(R.A_PKG, "r26_ccx", "ccx.bin", b"-"))
time.sleep(2)
run("create_ccy", lambda: R.create_action(R.A_PKG, "r26_ccy", "ccy.bin", b"-"))
time.sleep(2)
st = R.file_state(["X", "Y"], outdir=out, tag="post_create")
missing = [k for k,v in st.items() if "MISSING" in v]
assert not missing, f"missing {missing}"
cfg = R.discover_boot_cfg(runtime)
log["boot_cfg"] = cfg
(runtime/"setup_log.json").write_text(json.dumps(log, indent=1))
print(json.dumps(cfg, indent=1))
print("SETUP_COMPLETE")
