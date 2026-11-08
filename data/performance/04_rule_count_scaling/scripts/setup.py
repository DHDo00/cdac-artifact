#!/usr/bin/env python3
"""Setup one fresh boot: install APKs+tool, grants, create X/Y, discover cfg."""
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
        log[label] = {"ok": True, "sec": round(time.time() - t0, 1), "detail": str(r)[:400]}
        print(f"[setup] {label}: OK {time.time()-t0:.1f}s")
        return r
    except Exception as e:
        log[label] = {"ok": False, "sec": round(time.time() - t0, 1), "detail": repr(e)[:400]}
        print(f"[setup] {label}: FAIL {repr(e)[:200]}")
        return None

R.adb("connect", R.SERIAL, timeout=30)
# installs
run("install_timing", lambda: R.adb("install", "-r",
    str(WS.parent / "cdac_esp_endpoint_validation_20261022/10_controls_matched_builds_timing_20261023/03_timing_app/build/esp-timing-signed.apk"), timeout=180))
run("install_A", lambda: R.adb("install", "-r",
    str(WS.parent / "cdac_esp_endpoint_validation_20261022/07_side_effect_order/fixtures/app_diag/build/espafdtest-signed.apk"), timeout=180))
run("install_B", lambda: R.adb("install", "-r",
    str(WS.parent / "cdac_esp_endpoint_validation_20261022/01_fixtures/app_b/build/espafdtest-signed.apk"), timeout=180))
run("push_tool", lambda: R.adb("push",
    str(WS.parent / "cdac_esp_afd_wrapper_runtime_validation_20261022/01_device_preflight/iguardctl_test"),
    R.POLICY, timeout=120))
run("chmod_tool", lambda: R.sh(f"chmod 755 {R.POLICY}"))

# grants (UI automation; reuse round-11 scripts)
S = WS / "scripts"
run("grant_timing_create", lambda: subprocess.run(
    ["bash", str(S / "saf_grant_create.sh"), R.T_PKG, R.T_PKG + "/.MainActivity",
     "espafd_tree"], capture_output=True, text=True, timeout=120).stdout)
time.sleep(2)
run("grant_A_existing", lambda: subprocess.run(
    ["bash", str(S / "saf_grant_existing.sh"), R.A_PKG, R.A_PKG + "/.MainActivity",
     "espafd_tree"], capture_output=True, text=True, timeout=180).stdout)
time.sleep(2)
run("grant_B_existing", lambda: subprocess.run(
    ["bash", str(S / "saf_grant_existing.sh"), R.B_PKG, R.B_PKG + "/.MainActivity",
     "espafd_tree"], capture_output=True, text=True, timeout=180).stdout)
time.sleep(2)

def grants(pkg):
    return R.guest(pkg, "grants.txt").stdout
log["grants"] = {"timing": grants(R.T_PKG), "A": grants(R.A_PKG),
                 "B": grants(R.B_PKG)}
print("[setup] grants:", json.dumps(log["grants"], indent=1)[:800])

# create X, Y via A
run("create_X", lambda: R.am_start(R.A_PKG, {"action": "create",
    "tree_uri": R.TREE, "name": "X.bin", "content": "0123456789ABCD",
    "label": "fix_X"}, R.TREE, timeout=180))
time.sleep(2)
run("create_Y", lambda: R.am_start(R.A_PKG, {"action": "create",
    "tree_uri": R.TREE, "name": "Y.bin", "content": "0123456789ABCD",
    "label": "fix_Y"}, R.TREE, timeout=180))
time.sleep(2)
st = R.file_state(files=("X", "Y"), outdir=out, tag="post_create")
log["file_state_post_create"] = st

cfg = R.discover_boot_cfg(runtime)
log["boot_cfg"] = cfg
(runtime / "setup_log.json").write_text(json.dumps(log, indent=1))
print(json.dumps(cfg, indent=1))
print("SETUP_COMPLETE")
