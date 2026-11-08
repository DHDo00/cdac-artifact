#!/usr/bin/env python3
"""Round-26 concurrency waves. Usage: driver_waves.py <runtime> <outdir> <boot> <mode> <waves>"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import runtime_lib as R

runtime = Path(sys.argv[1]); out = Path(sys.argv[2]); boot = sys.argv[3]
mode = sys.argv[4]; waves = int(sys.argv[5])
out.mkdir(parents=True, exist_ok=True)
cfg = json.loads((runtime / "boot_cfg.json").read_text())
X = R.uri_for("X"); Y = R.uri_for("Y")
X_INO = cfg["Xino"]; Y_INO = cfg["stats"]["Y"]["ino"]
REQ_DEF = {
    "AX": dict(pkg=R.A_PKG, uri=X, obj="X", offset=0, expect="DENY"),
    "AY": dict(pkg=R.A_PKG, uri=Y, obj="Y", offset=0, expect="ALLOW"),
    "BX": dict(pkg=R.B_PKG, uri=X, obj="X", offset=4096, expect="ALLOW"),
    "BY": dict(pkg=R.B_PKG, uri=Y, obj="Y", offset=4096, expect="ALLOW"),
}
QC = ["context_push_ok", "context_push_fail", "context_pop_ok", "context_pop_fail",
      "file_open_deny", "file_open_join", "file_open_no_context"]

def wave_ready(labels):
    missing = []
    for pkg, lab in labels:
        g = R.guest(pkg, lab + ".ready", timeout=20).stdout.strip()
        if not g:
            missing.append((pkg, lab))
    return not missing, missing

def wave_done(labels):
    done, missing = [], []
    for pkg, lab in labels:
        row = R.last_csv(pkg, lab, timeout=20)
        if row:
            done.append((pkg, lab, row))
        else:
            missing.append((pkg, lab))
    return (not missing), done, missing

def run_wave(w, allow_retry=True):
    prefix = f"r26_{boot}_w{w:02d}"
    R.clear_logs()
    labels = []
    for key in ("AX", "AY", "BX", "BY"):
        d = REQ_DEF[key]
        lab = f"{prefix}_{key}"
        labels.append((d["pkg"], lab, key))
        R.wave_action(d["pkg"], lab, d["uri"], R.p16(lab), d["offset"], f"w{w:02d}")
    # wait ready
    ready_ok = False
    for _ in range(40):
        ready_ok, miss = wave_ready([(p, l) for p, l, k in labels])
        if ready_ok:
            break
        time.sleep(0.25)
    if not ready_ok:
        return {"wave": w, "ok": False, "reason": "not_ready", "missing": miss,
                "attempt": 1}
    t0 = time.time()
    R.sh(f"am broadcast -a com.demo.cdac26.RELEASE --es wave w{w:02d}", timeout=30)
    done_ok = False
    done = []
    miss = []
    for _ in range(60):
        done_ok, done, miss = wave_done([(p, l) for p, l, k in labels])
        if done_ok:
            break
        time.sleep(0.25)
    elapsed = time.time() - t0
    qc = R.qc()
    fw = R.framework_log(tail=1200)
    kern = R.kernel_log(tail=6000)
    app_rows = {lab: row for pkg, lab, row in done}
    markers = {}
    for key in ("AY", "BX", "BY"):
        d = REQ_DEF[key]
        path = f"/data/media/0/espafd_tree/{R.FILES[d['obj']]}"
        markers[key] = R.read_marker(path, d["offset"])
    anchor_out = R.sh("date +%s.%N; date +%Y-%m-%d\\ %H:%M:%S").stdout.strip()
    rec = {"wave": w, "boot": boot, "mode": mode, "ok": done_ok,
           "clock_anchor": anchor_out,
           "reason": "" if done_ok else "timeout", "missing": miss,
           "ready_ok": ready_ok, "elapsed_s": round(elapsed, 2),
           "app_rows": app_rows, "markers": markers, "loadavg": R.loadavg(),
           "qc": qc, "fw": fw, "kern": kern,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    od = out / f"w{w:02d}"
    od.mkdir(parents=True, exist_ok=True)
    (od / "fw.txt").write_text(fw + "\n")
    (od / "kern.txt").write_text(kern + "\n")
    (od / "app_rows.json").write_text(json.dumps(app_rows, indent=1))
    (od / "qc.txt").write_text(qc)
    (od / "meta.json").write_text(json.dumps(
        {k: v for k, v in rec.items() if k not in ("fw", "kern")}, indent=1))
    return rec

def main():
    rows = []
    for w in range(1, waves + 1):
        rec = run_wave(w)
        if not rec["ok"]:
            print(f"[wave] w{w:02d} FAIL {rec['reason']} missing={rec['missing']}")
            # bounded single retry for infra only
            if rec["reason"] == "not_ready" or rec["reason"] == "timeout":
                time.sleep(2)
                rec2 = run_wave(w, allow_retry=False)
                if not rec2["ok"]:
                    print(f"[wave] w{w:02d} RETRY FAIL {rec2['reason']}")
                    rec2["first_attempt"] = {"reason": rec["reason"],
                                             "missing": rec["missing"]}
                    rec = rec2
                else:
                    rec["retry_note"] = "retry_after_not_ready_or_timeout"
                    rec = rec2
        rows.append({k: v for k, v in rec.items() if k not in ("fw", "kern")})
        print(f"[wave] w{w:02d} ok={rec.get('ok')} elapsed={rec.get('elapsed_s')} "
              f"loadavg={rec.get('loadavg')}")
    (out / "waves_raw.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    print("WAVES_DONE", len(rows))

if __name__ == "__main__":
    main()
