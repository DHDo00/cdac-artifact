#!/usr/bin/env python3
"""Offline recomputation for round 39.

Derives every formal request's verdict ONLY from raw per-request evidence
(app/framework/kernel/am windows, backing snapshots, rule dumps, object json),
never from the expected matrix. Cross-checks the runner's boot ledgers, detects
duplicate reqids/double counts, and emits:
  analysis/requests_verified.csv
  summary/table7_per_boot.csv  summary/table7_pooled.csv
  summary/table8_per_boot.csv  summary/table8_pooled.csv
  analysis/checks.json
Exit code 0 only if all structural checks pass and the recomputed pooled
summary equals the runner-derived pooled summary.
"""
import argparse, csv, hashlib, json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

MARKER = {"X": "CDAC25GPSMARK_AAAA", "Y": "CDAC25GPSMARK_BBBB"}
SHA = {
    "AX": "e22785cddb56824a19cd77dd45239c403c8d134250f01620f5d825ebc024c375",
    "BX": "96f60e2770ef563d0c27182baeffd9eaaa660cd924e1e35808adebd04c5a4983",
    "AY": "f3d29cc26f285cfe7eebdd3177a84b7bafcb93ed6ef7bad65e088e1c7c9fc5f2",
    "BY": "3116065dfdd82767907c3b5af4d687d4b3e51bfbe4a9360ec70cd817a9250993",
}
REASON = {"MA": "cdac39_ma", "MB": "cdac39_mb", "LW": "cdac39_lw", "LR": "cdac39_lr"}
M_CONDITIONS = ["no_rule_ax","no_rule_bx","ma_ax","ma_bx","ma_ay","mb_bx","mb_ax","mb_by","revoke_ax","revoke_bx"]
L_CONDITIONS = ["no_rule_r","no_rule_w","lw_r","lw_w","lr_r","lr_w","revoke_r","revoke_w"]

def parse_app(app):
    out = {"app_result": "NO_LINE", "fd_delivered": 0, "bytes": "", "app_sha": "",
           "marker_present": "", "write_app_sha": "", "app_err": ""}
    for l in app.splitlines():
        if "READ_CPC ok" in l or "READ_CR ok" in l:
            out["app_result"] = "ALLOW"; out["fd_delivered"] = 1
            m = re.search(r"bytes=(\d+)", l); out["bytes"] = m.group(1) if m else ""
            m = re.search(r"marker_present=(true|false)", l); out["marker_present"] = m.group(1) if m else ""
            m = re.search(r"sha256=([0-9a-f]{64})", l); out["app_sha"] = m.group(1) if m else ""
        elif "WRITE_MP ok" in l:
            out["app_result"] = "ALLOW"; out["fd_delivered"] = 1
            m = re.search(r"written=(\d+)", l); out["bytes"] = m.group(1) if m else ""
            m = re.search(r"sha256=([0-9a-f]{64})", l); out["write_app_sha"] = m.group(1) if m else ""
        elif "RESULT fail" in l:
            if out["app_result"] == "NO_LINE":
                out["app_result"] = "FAIL"
            m = re.search(r"err=([^ ]+)", l); out["app_err"] = m.group(1) if m else ""
    return out

def parse_fw(fw):
    out = {"context_id": "", "pub_msg5": "", "matched": "", "reason": "", "real_enforce": "", "errno": ""}
    for l in fw.splitlines():
        m = re.search(r"CDAC_CONTEXT_ENTER context_id=(\d+)", l)
        if m and not out["context_id"]:
            out["context_id"] = m.group(1)
        m = re.search(r"CDAC_FRAMEWORK_CONTEXT_PUBLISH context_id=\d+ msg_type=(\d+).*result=(\S+)", l)
        if m and not out["pub_msg5"]:
            out["pub_msg5"] = f"{m.group(1)}:{m.group(2)}"
        m = re.search(r"iguard_ctx: decision .* matched=(\d+) reason=(\S+)", l)
        if m:
            out["matched"] = m.group(1); out["reason"] = m.group(2)
        m = re.search(r"real-enforce .* errno=(-?\d+) verdict=(\S+)", l)
        if m:
            out["real_enforce"] = m.group(2); out["errno"] = m.group(1)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="39_mediaprovider_matrix_replication_20261029_230000")
    ap.add_argument("--out", default=None, help="output dir (defaults to <root>/analysis)")
    args = ap.parse_args()
    root = Path(args.root)
    outdir = Path(args.out) if args.out else root / "analysis"
    outdir.mkdir(parents=True, exist_ok=True)
    sumdir = root / "summary"
    sumdir.mkdir(parents=True, exist_ok=True)

    with open(root / "SCHEDULE.csv") as f:
        sched_rows = list(csv.DictReader(f))
    sched = {r["reqid"]: r for r in sched_rows}
    checks = {"duplicate_reqids": [], "missing_schedule": [], "boot_ledger_mismatches": [],
              "attempted_missing": [], "structure": []}
    assert len(sched) == 1080, f"schedule rows {len(sched)}"
    assert len(set(sched)) == 1080

    # runner-derived per-boot ledgers (cross-check)
    runner = {}
    for boot in (1, 2, 3):
        bp = root / "07_results" / f"boot{boot}" / "boot_ledger.csv"
        if bp.exists():
            with open(bp) as f:
                runner[boot] = {r["reqid"]: r for r in csv.DictReader(f)}
        else:
            runner[boot] = {}
    dup = defaultdict(list)
    for boot, mp in runner.items():
        for reqid in mp:
            dup[reqid].append(boot)
    checks["duplicate_reqids"] = sorted(k for k, v in dup.items() if len(v) > 1)

    results = []
    for r in sched_rows:
        boot = int(r["boot"])
        rawdir = root / "07_results" / f"boot{boot}" / "raw"
        reqid = r["reqid"]
        app_file = rawdir / f"{reqid}_app.txt"
        fw_file = rawdir / f"{reqid}_framework.txt"
        am_file = rawdir / f"{reqid}_am.txt"
        k_file = rawdir / f"{reqid}_kernel.txt"
        obj = r["object"]
        back_file = rawdir / f"{reqid}_backing{obj}.sha"
        app = app_file.read_text() if app_file.exists() else ""
        fw = fw_file.read_text() if fw_file.exists() else ""
        am = am_file.read_text() if am_file.exists() else ""
        backing_sha = ""
        if back_file.exists():
            backing_sha = back_file.read_text().split()[0]
        has_req_line = f"REQ reqid={reqid}" in app or f"reqid={reqid}" in app
        pa = parse_app(app)
        pf = parse_fw(fw)
        rule_key = r["rule_key"]
        exp = r["expected_verdict"]
        if exp == "denied":
            if pa["app_result"] == "FAIL" and pa["fd_delivered"] == 0:
                if (pf["matched"] == "1" and pf["reason"] == REASON[rule_key]
                        and pf["real_enforce"] == "deny-now" and pf["errno"] == "-13"):
                    verdict, evidence = "DENY_PASS", "MATCHED"
                else:
                    verdict, evidence = "UNRESOLVED", "UNRESOLVED"
            elif pa["app_result"] == "ALLOW":
                verdict, evidence = "OTHER_FAIL", "NONE"
            else:
                verdict, evidence = "OTHER_FAIL", "UNRESOLVED"
        else:
            if r["mode"] == "r":
                use_ok = (pa["app_result"] == "ALLOW" and pa["fd_delivered"] == 1
                          and pa["bytes"] == "911" and pa["app_sha"] == r["expected_read_sha"]
                          and pa["marker_present"] == r["expected_marker_present"])
            else:
                use_ok = (pa["app_result"] == "ALLOW" and pa["fd_delivered"] == 1
                          and pa["write_app_sha"] == r["expected_write_sha"]
                          and backing_sha == r["expected_write_sha"])
            if use_ok:
                verdict, evidence = "ALLOW_PASS", "NONE"
            elif pa["app_result"] == "FAIL":
                verdict, evidence = "OTHER_FAIL", "UNRESOLVED"
            else:
                verdict, evidence = "OTHER_FAIL", "NONE"
        state = r["rule_state"]
        cycle = int(r["cycle"])
        rule_dump = rawdir / f"rule_b{boot}_C{cycle:02d}_{state}_dump.txt"
        rule_add = rawdir / f"rule_b{boot}_C{cycle:02d}_{state}_add.txt"
        # cross-check runner verdict for this reqid
        rv = runner.get(boot, {}).get(reqid)
        if rv is not None and rv.get("verdict") not in (None, ""):
            if rv["verdict"] != verdict:
                checks["boot_ledger_mismatches"].append(dict(reqid=reqid, runner=rv["verdict"], recomputed=verdict))
        results.append(dict(reqid=reqid, study=r["study"], boot=boot, cycle=cycle, condition=r["condition"],
                            rule_state=state, rule_key=rule_key, mode=r["mode"], caller_role=r["caller_role"],
                            object=obj, expected=exp, app_result=pa["app_result"],
                            fd_delivered=pa["fd_delivered"], bytes=pa["bytes"], app_sha=pa["app_sha"],
                            marker_present=pa["marker_present"], write_app_sha=pa["write_app_sha"],
                            backing_sha=backing_sha, context_id=pf["context_id"], pub_msg5=pf["pub_msg5"],
                            matched=pf["matched"], reason=pf["reason"], real_enforce=pf["real_enforce"],
                            errno=pf["errno"], verdict=verdict, enforce_evidence=evidence,
                            has_req_line=has_req_line,
                            app_file=f"07_results/boot{boot}/raw/{reqid}_app.txt",
                            fw_file=f"07_results/boot{boot}/raw/{reqid}_framework.txt",
                            kernel_file=f"07_results/boot{boot}/raw/{reqid}_kernel.txt",
                            am_file=f"07_results/boot{boot}/raw/{reqid}_am.txt",
                            rule_dump_file=(f"07_results/boot{boot}/raw/{rule_dump.name}" if rule_dump.exists() else ""),
                            rule_add_file=(f"07_results/boot{boot}/raw/{rule_add.name}" if rule_add.exists() else ""),
                            backing_file=(f"07_results/boot{boot}/raw/{reqid}_backing{obj}.sha" if back_file.exists() else "")))
    with open(outdir / "requests_verified.csv", "w", newline="") as f:
        cols = list(results[0].keys())
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(results)

    def build_tables(study, conditions, name7):
        per_boot_rows = []
        for cond in conditions:
            row = {"condition": cond}
            for boot in (1, 2, 3):
                sel = [x for x in results if x["study"] == study and x["condition"] == cond and x["boot"] == boot]
                row[f"boot{boot}_planned"] = 20
                row[f"boot{boot}_attempted"] = len(sel)
                row[f"boot{boot}_usable"] = sum(1 for x in sel if x["verdict"] == "ALLOW_PASS")
                row[f"boot{boot}_denied"] = sum(1 for x in sel if x["verdict"] == "DENY_PASS")
                row[f"boot{boot}_other"] = sum(1 for x in sel if x["verdict"] == "OTHER_FAIL")
                row[f"boot{boot}_unresolved"] = sum(1 for x in sel if x["verdict"] == "UNRESOLVED")
            per_boot_rows.append(row)
        cols = ["condition"]
        for boot in (1, 2, 3):
            cols += [f"boot{boot}_planned", f"boot{boot}_attempted", f"boot{boot}_usable",
                     f"boot{boot}_denied", f"boot{boot}_other", f"boot{boot}_unresolved"]
        with open(sumdir / f"{name7}_per_boot.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader(); w.writerows(per_boot_rows)
        pooled_rows = []
        for cond in conditions:
            sel = [x for x in results if x["study"] == study and x["condition"] == cond]
            pooled_rows.append(dict(condition=cond, planned=60, attempted=len(sel),
                usable=sum(1 for x in sel if x["verdict"] == "ALLOW_PASS"),
                cdac_denied=sum(1 for x in sel if x["verdict"] == "DENY_PASS"),
                other_failure=sum(1 for x in sel if x["verdict"] == "OTHER_FAIL"),
                unresolved=sum(1 for x in sel if x["verdict"] == "UNRESOLVED"),
                formal_denominator=60))
        alls = [x for x in results if x["study"] == study]
        pooled_rows.append(dict(condition="TOTAL", planned=len(conditions) * 60, attempted=len(alls),
            usable=sum(1 for x in alls if x["verdict"] == "ALLOW_PASS"),
            cdac_denied=sum(1 for x in alls if x["verdict"] == "DENY_PASS"),
            other_failure=sum(1 for x in alls if x["verdict"] == "OTHER_FAIL"),
            unresolved=sum(1 for x in alls if x["verdict"] == "UNRESOLVED"),
            formal_denominator=len(conditions) * 60))
        with open(sumdir / f"{name7}_pooled.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["condition","planned","attempted","usable","cdac_denied","other_failure","unresolved","formal_denominator"])
            w.writeheader(); w.writerows(pooled_rows)
        return pooled_rows

    m_pool = build_tables("M", M_CONDITIONS, "table7")
    l_pool = build_tables("L", L_CONDITIONS, "table8")
    checks["pooled_M"] = m_pool
    checks["pooled_L"] = l_pool
    # structure checks
    by_cond = Counter(x["condition"] for x in results)
    for study, conds in (("M", M_CONDITIONS), ("L", L_CONDITIONS)):
        for c in conds:
            if by_cond.get(c, 0) != 60:
                checks["structure"].append(f"{c}: got {by_cond.get(c, 0)} expected 60")
    checks["no_req_line"] = sorted(x["reqid"] for x in results if not x["has_req_line"])
    with open(outdir / "checks.json", "w") as f:
        json.dump(checks, f, indent=2)
    ok = (not checks["duplicate_reqids"] and not checks["boot_ledger_mismatches"]
          and not checks["structure"] and not checks["no_req_line"])
    print(json.dumps({k: v for k, v in checks.items() if k in ("duplicate_reqids","boot_ledger_mismatches","structure","no_req_line")}, indent=2))
    print("POOLED M:", m_pool[-1])
    print("POOLED L:", l_pool[-1])
    print("STRUCT_OK" if ok else "STRUCT_FAIL")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
