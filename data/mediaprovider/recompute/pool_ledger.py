#!/usr/bin/env python3
"""Pool round-39 boot ledgers into the deliverable REQUEST_LEDGER.csv,
EVIDENCE_MAP.csv and BOOT_LEDGER.csv.

REQUEST_LEDGER.csv contains every actual call (formal, prep, restore,
maintenance) with scientific flag. EVIDENCE_MAP.csv maps each request id to its
raw evidence paths and completeness status. BOOT_LEDGER.csv records boot-level
identity and log hashes. Read-only with respect to raw material.
"""
import argparse, csv, hashlib, json, re
from pathlib import Path

LEDGER_COLS = None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="39_mediaprovider_matrix_replication_20261029_230000")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.root)
    outdir = Path(args.out) if args.out else root
    boot_dirs = {b: root / "07_results" / f"boot{b}" for b in (1, 2, 3)}

    all_rows = []
    seen = {}

    # ---- add object-creation prep calls present in raw but not in per-boot ledger ----
    make_cols = ["kind","study","boot","cycle","rule_state","rule_order","exec_order","reqid","condition",
                 "caller_pkg","caller_role","api_entry","method_label","mode","object","uri","marker",
                 "rule_key","rule_dump_sha","expected_verdict","app_result","fd_delivered","bytes_read",
                 "app_sha","marker_present","write_app_sha","backing_sha","context_id","pub_msg5",
                 "server_pid","server_tid","matched","matched_reason","matched_obj","real_enforce","errno",
                 "verdict","enforce_evidence","scientific","attempt","note","app_file","fw_file",
                 "kernel_file","am_file","restore_file","t_start_epoch","t_end_epoch","t_start_uptime","t_end_uptime"]
    for b, bd in sorted(boot_dirs.items()):
        raw = bd / "raw"
        if not raw.exists():
            continue
        for apf in sorted(raw.glob("PRE-B*-MAKE-*_app.txt")):
            import re as _re
            m = _re.match(r"PRE-B(\d)-MAKE-(image\d)_app\.txt", apf.name)
            if not m:
                continue
            reqid = apf.name[:-8]
            base = apf.name[:-8]  # strip _app.txt
            app = apf.read_text() if apf.exists() else ""
            fw = (raw / f"{base}_framework.txt").read_text() if (raw / f"{base}_framework.txt").exists() else ""
            ok = "MAKE_IMAGE ok" in app
            row = {c: "" for c in make_cols}
            row.update(dict(kind="prep_make", study="M", boot=b, cycle=0, rule_state="PRE", rule_order="",
                            exec_order=0, reqid=reqid, condition="prep_make_object",
                            caller_pkg="com.demo.espafdtest", caller_role="A",
                            api_entry="MediaStore insert (object creation)", method_label="insert", mode="w",
                            object=m.group(2)[-1].upper(), uri="", marker="", rule_key="", rule_dump_sha="",
                            expected_verdict="make", app_result="ALLOW" if ok else "FAIL", fd_delivered=0,
                            bytes_read="", app_sha="", marker_present="", write_app_sha="", backing_sha="",
                            context_id="", pub_msg5="", server_pid="", server_tid="", matched="", matched_reason="",
                            matched_obj="", real_enforce="", errno="", verdict="PREP_MAKE", enforce_evidence="NONE",
                            scientific=0, attempt=1, note="", app_file=f"07_results/boot{b}/raw/{base}_app.txt",
                            fw_file=f"07_results/boot{b}/raw/{base}_framework.txt",
                            kernel_file=f"07_results/boot{b}/raw/{base}_kernel.txt",
                            am_file=f"07_results/boot{b}/raw/{base}_am.txt", restore_file="",
                            t_start_epoch="", t_end_epoch="", t_start_uptime="", t_end_uptime=""))
            all_rows.append(row)
            seen[reqid] = seen.get(reqid, 0) + 1
    dupes = sorted(k for k, v in seen.items() if v > 1)

    # ---- REQUEST_LEDGER.csv ----
    for b, bd in sorted(boot_dirs.items()):
        lp = bd / "boot_ledger.csv"
        if not lp.exists():
            continue
        with open(lp) as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row["reqid"]
                seen[key] = seen.get(key, 0) + 1
                # resolve raw file paths relative to round dir
                for col in ("app_file", "fw_file", "kernel_file", "am_file", "restore_file"):
                    if row.get(col):
                        row[col] = f"07_results/boot{b}/raw/{row[col]}"
                row["boot"] = b
                all_rows.append(row)
    dupes = sorted(k for k, v in seen.items() if v > 1)
    with open(outdir / "REQUEST_LEDGER.csv", "w", newline="") as f:
        if all_rows:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
    print(f"request ledger rows={len(all_rows)} duplicate_reqids={dupes}")

    # ---- EVIDENCE_MAP.csv ----
    def line_of(text, pat, start=0):
        import re as _re2
        for i, l in enumerate(text.splitlines()[start:], start + 1):
            if _re2.search(pat, l):
                return i
        return ""
    with open(outdir / "EVIDENCE_MAP.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["request_id", "study", "boot", "kind", "scientific", "app_file", "app_req_line",
                    "app_result_line", "framework_file", "context_enter_line", "publish_line",
                    "decision_line", "enforce_line", "join_line", "kernel_file", "am_file",
                    "rule_dump_file", "rule_dump_line", "rule_add_file", "object_stat_file",
                    "object_stat_line", "backing_sha_file", "backing_sha_line", "restore_file",
                    "evidence_status"])
        for row in all_rows:
            boot = int(row["boot"])
            raw = root / "07_results" / f"boot{boot}" / "raw"
            if row["kind"] != "formal":
                ap = Path(root / row["app_file"]) if row.get("app_file") else None
                fw = Path(root / row["fw_file"]) if row.get("fw_file") else None
                w.writerow([row["reqid"], row.get("study", ""), boot, row["kind"], row["scientific"],
                            row.get("app_file", ""),
                            line_of(ap.read_text(), "REQ reqid=") if ap and ap.exists() else "",
                            line_of(ap.read_text(), "MAKE_IMAGE ok|READ_|WRITE_|RESTORE_|RESULT fail") if ap and ap.exists() else "",
                            row.get("fw_file", ""), "", "", "", "", "", row.get("kernel_file", ""),
                            row.get("am_file", ""), "", "", "", "", "", "", "", "",
                            row.get("restore_file", ""), "PREP"])
                continue
            cycle = int(row["cycle"]); state = row["rule_state"]; obj = row["object"]
            rule_dump = raw / f"rule_b{boot}_C{cycle:02d}_{state}_dump.txt"
            rule_add = raw / f"rule_b{boot}_C{cycle:02d}_{state}_add.txt"
            stat_file = raw / f"{row['reqid']}_backing{obj}.txt"
            sha_file = raw / f"{row['reqid']}_backing{obj}.sha"
            ap = raw / f"{row['reqid']}_app.txt"; fwp = raw / f"{row['reqid']}_framework.txt"
            app_txt = ap.read_text() if ap.exists() else ""
            fw_txt = fwp.read_text() if fwp.exists() else ""
            rule_txt = rule_dump.read_text() if rule_dump.exists() else ""
            reas = row.get("matched_reason", "") or ""
            decision_pat = f"decision .* matched={row.get('matched','')}" if row.get("matched") else "iguard_ctx: decision"
            # locate the rule line inside the dump for this request's rule key
            rk = row.get("rule_key") or ""
            reason = {"MA": "cdac39_ma", "MB": "cdac39_mb", "LW": "cdac39_lw", "LR": "cdac39_lr"}.get(rk, "")
            rule_line = line_of(rule_txt, reason) if reason else ""
            missing = [x for x in (ap, fwp, raw / f"{row['reqid']}_am.txt", raw / f"{row['reqid']}_kernel.txt") if not x.exists()]
            status = "COMPLETE" if not missing else "INCOMPLETE"
            if row["verdict"] == "UNRESOLVED":
                status = "UNRESOLVED_ENFORCEMENT"
            w.writerow([row["reqid"], row["study"], boot, "formal", row["scientific"],
                        f"07_results/boot{boot}/raw/{ap.name}" if ap.exists() else "",
                        line_of(app_txt, "REQ reqid="),
                        line_of(app_txt, "READ_CPC ok|READ_CR ok|WRITE_MP ok|RESULT fail"),
                        f"07_results/boot{boot}/raw/{fwp.name}" if fwp.exists() else "",
                        line_of(fw_txt, "CDAC_CONTEXT_ENTER"),
                        line_of(fw_txt, "CDAC_FRAMEWORK_CONTEXT_PUBLISH"),
                        line_of(fw_txt, decision_pat),
                        line_of(fw_txt, "real-enforce"),
                        line_of(fw_txt, "CDAC_BINDER_VFS_JOIN"),
                        f"07_results/boot{boot}/raw/{row['reqid']}_kernel.txt" if (raw / f"{row['reqid']}_kernel.txt").exists() else "",
                        f"07_results/boot{boot}/raw/{row['reqid']}_am.txt" if (raw / f"{row['reqid']}_am.txt").exists() else "",
                        f"07_results/boot{boot}/raw/{rule_dump.name}" if rule_dump.exists() else "",
                        rule_line,
                        f"07_results/boot{boot}/raw/{rule_add.name}" if rule_add.exists() else "",
                        f"07_results/boot{boot}/raw/{stat_file.name}" if stat_file.exists() else "",
                        "1" if stat_file.exists() else "",
                        f"07_results/boot{boot}/raw/{sha_file.name}" if sha_file.exists() else "",
                        "1" if sha_file.exists() else "",
                        row["restore_file"], status])

    # ---- BOOT_LEDGER.csv ----
    with open(outdir / "BOOT_LEDGER.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["boot", "adapter_serial", "instance", "build_product", "boot_id", "fingerprint",
                    "release", "sdk", "kernel", "selinux", "mediaprovider_version", "uidA", "uidB",
                    "inoX", "inoY", "uriX", "uriY", "backX", "backY", "full_logcat_path",
                    "full_logcat_sha256", "full_dmesg_path", "full_dmesg_sha256", "raw_request_windows"])
        for b, bd in sorted(boot_dirs.items()):
            info = bd / "device_info"
            def read_txt(name):
                p = info / f"{name}.txt"
                return p.read_text().strip() if p.exists() else ""
            obj = {}
            op = bd / "objects.json"
            if op.exists():
                obj = json.loads(op.read_text())
            fc = bd / "full_logcat.txt"; fd = bd / "full_dmesg.txt"
            nraw = len(list((bd / "raw").glob("M-*_app.txt"))) + len(list((bd / "raw").glob("L-*_app.txt"))) if (bd / "raw").exists() else 0
            w.writerow([b, "0.0.0.0:6558", "cvd-39", "C19_media+kernel_openkeychain_dist",
                        read_txt("boot_id"), read_txt("fingerprint"), read_txt("release"), read_txt("sdk"),
                        read_txt("kernel_rel"), read_txt("selinux_mode"), read_txt("mediaprovider_version"),
                        obj.get("uidA", ""), obj.get("uidB", ""), obj.get("inoX", ""), obj.get("inoY", ""),
                        obj.get("uriX", ""), obj.get("uriY", ""), obj.get("backX", ""), obj.get("backY", ""),
                        f"07_results/boot{b}/full_logcat.txt",
                        hashlib.sha256(fc.read_bytes()).hexdigest() if fc.exists() else "",
                        f"07_results/boot{b}/full_dmesg.txt",
                        hashlib.sha256(fd.read_bytes()).hexdigest() if fd.exists() else "",
                        nraw])

if __name__ == "__main__":
    main()
