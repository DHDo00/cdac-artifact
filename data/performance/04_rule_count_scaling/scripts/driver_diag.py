#!/usr/bin/env python3
"""LOG_ON diagnostic (separate, §9): capture kernel decision_ns per scale.
Usage: driver_diag.py <runtime> <outdir>"""
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import runtime_lib as R

runtime = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
cfg = json.loads((runtime / "boot_cfg.json").read_text())

R.sh("echo 1 > /sys/kernel/debug/iguard/verbose_audit")
R.sh("cat /sys/kernel/debug/iguard/verbose_audit")  # record via shell below
va = R.sh("cat /sys/kernel/debug/iguard/verbose_audit").stdout.strip()
summary = {}
for N in [0, 1, 8, 32, 128]:
    R.clear_policy()
    if N > 0:
        for kind, cmd in R.rules_mod.rules_for_scale(N, cfg):
            R.add_rule(cmd)
    dump = R.policy_dump()
    (out / f"diag_N{N}_policy_dump.txt").write_text(dump)
    R.restore_x(f"diag_N{N}_restore")
    time.sleep(1)
    R.sh("logcat -c; logcat -b kernel -c")
    R.timed_run(f"diag_N{N}", f"N{N}", 1, 3, f"diag_N{N}.csv")
    time.sleep(3)
    csv_raw = R.pull_timing_csv(f"diag_N{N}.csv")
    (out / f"diag_N{N}.csv").write_text(csv_raw if csv_raw else "")
    kern = R.sh("logcat -b kernel -d").stdout
    (out / f"diag_N{N}_kernel.txt").write_text(kern)
    dec = [int(m) for m in re.findall(
        r"iguard_ctx: perf .*? decision_ns=(\d+)", kern)]
    add_costs = [int(m) for m in re.findall(
        r"perf policy_op=add cost_ns=(\d+)", kern)]
    clear_costs = [int(m) for m in re.findall(
        r"perf policy_op=clear cost_ns=(\d+)", kern)]
    summary[N] = {"decision_ns": dec, "add_cost_ns": add_costs,
                  "clear_cost_ns": clear_costs}
    print(f"diag N{N}: decision_ns={dec} add_costs={add_costs[:3]}…")
# LOG_ON real-enforce text capture for A->X deny at N=1 and N=128 (§9)
deny_lines = {}
for N in [1, 128]:
    R.clear_policy()
    for kind, cmd in R.rules_mod.rules_for_scale(N, cfg):
        R.add_rule(cmd)
    R.sh("logcat -c; logcat -b kernel -c")
    R.write_action(R.A_PKG, f"diag_deny_N{N}", "DG" + f"{N:03d}" + "P" * 11, R.X_URI)
    time.sleep(1)
    k = R.sh("logcat -b kernel -d").stdout
    deny_lines[N] = [ln for ln in k.splitlines() if "real-enforce" in ln]
    (out / f"diag_deny_N{N}_kernel.txt").write_text(k)
    print(f"diag deny N{N}: {deny_lines[N]}")
R.clear_policy()
(out / "diag_summary.json").write_text(json.dumps(summary, indent=1))
R.sh("echo 0 > /sys/kernel/debug/iguard/verbose_audit")
R.clear_policy()
(out / "DIAG_DONE.txt").write_text(
    f"done={time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
print("DIAG_DONE verbose_audit_before=", va)
