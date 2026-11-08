#!/usr/bin/env python3
"""Performance sampling driver (frozen protocol §7-§8). Usage:
driver_perf.py <boot_label> <runtime> <schedule.csv> <outdir>"""
import csv, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import runtime_lib as R

boot = sys.argv[1]
runtime = Path(sys.argv[2])
sched_path = Path(sys.argv[3])
out = Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
cfg = json.loads((runtime / "boot_cfg.json").read_text())

rows = list(csv.DictReader(open(sched_path)))
blocks = {}
for r in rows:
    b = int(r["block"])
    blocks.setdefault(b, {})[int(r["position"])] = int(r["scale"])
ledger = []

for b in sorted(blocks):
    load1 = float(R.loadavg().split()[0])
    disturbed = load1 >= 8.0
    bmeta = {"boot": boot, "block": b, "loadavg1": load1,
             "disturbed": disturbed, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    R.clear_policy()
    for pos in sorted(blocks[b]):
        N = blocks[b][pos]
        cfgdir = out / f"boot{boot}_b{b:02d}_N{N}"
        inst = R.install_config(N, cfg, cfgdir, f"boot{boot}_b{b:02d}_N{N}")
        m = {"boot": boot, "block": b, "position": pos, "scale": N,
             "loadavg1": load1, "disturbed": disturbed,
             "config_verified": inst["verified"],
             "count_actual": inst["count_actual"],
             "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        outname = f"boot{boot}_b{b:02d}_N{N}.csv"
        R.restore_x(f"boot{boot}_b{b:02d}_N{N}_restore")
        time.sleep(1)
        R.sh("logcat -c; logcat -b kernel -c")
        R.timed_run(f"boot{boot}_b{b:02d}_N{N}", f"N{N}", 5, 5, outname)
        time.sleep(4)
        raw = R.pull_timing_csv(outname)
        (out / outname).write_text(raw if raw else "")
        m["csv_rows"] = raw.count("\n") - 1 if raw else 0
        m["qc_post"] = R.qc()
        m["file_state"] = R.file_state(files=("X",), outdir=cfgdir,
                                       tag="post_sample")
        m["policy_dump_post"] = R.policy_dump()
        (cfgdir / "meta.json").write_text(json.dumps(m, indent=1))
        ledger.append(m)
        print(f"[boot{boot} b{b:02d} p{pos} N{N}] verified={inst['verified']} "
              f"rows={m['csv_rows']} load1={load1:.2f} dist={disturbed}")
    # end of block: clear + verify 0
    clr = R.clear_policy()
    bmeta["clear_count_after"] = clr["count_after"]
    (out / f"boot{boot}_b{b:02d}_blockmeta.json").write_text(
        json.dumps(bmeta, indent=1))
    # persist ledger after every block
    (out / "perf_ledger.jsonl").write_text(
        "\n".join(json.dumps(m) for m in ledger) + "\n")

(out / "PERF_DONE.txt").write_text(
    f"done={time.strftime('%Y-%m-%dT%H:%M:%S%z')} blocks={len(blocks)} rows={len(ledger)}\n")
print("PERF_DONE blocks=", len(blocks), "configs=", len(ledger))
