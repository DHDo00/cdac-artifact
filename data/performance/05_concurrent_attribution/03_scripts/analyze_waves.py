#!/usr/bin/env python3
"""Round-26 wave analysis: seq->request mapping, overlap, per-request verdicts."""
import csv, datetime, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import runtime_lib as R

out = Path(sys.argv[1]); boot = sys.argv[2]
boot_no = "1" if boot == "b1" else "2"
cfgfile = (Path("26_concurrent_attribution_20261027/04_runtime")
           / f"boot{boot_no}" / "boot_cfg.json")
cfg = json.loads(cfgfile.read_text())
X_INO = cfg["Xino"]; Y_INO = cfg["stats"]["Y"]["ino"]; A = cfg["A"]; B = cfg["B"]
REQ_DEF = {
    "AX": dict(caller=A, obj_ino=X_INO, expect="DENY"),
    "AY": dict(caller=A, obj_ino=Y_INO, expect="ALLOW"),
    "BX": dict(caller=B, obj_ino=X_INO, expect="ALLOW"),
    "BY": dict(caller=B, obj_ino=Y_INO, expect="ALLOW"),
}

def anchor_epoch(rec):
    out = rec.get("clock_anchor", "")
    lines = out.splitlines()
    if not lines:
        return None, None
    try:
        epoch = float(lines[0])
    except Exception:
        return None, None
    return epoch, lines[1].strip() if len(lines) > 1 else None

def parse_ts(line, epoch_anchor=None, local_anchor=None):
    m = re.match(r'^\s*(\d{10}\.\d{3})\s', line)
    if m:
        return float(m.group(1))
    m = re.match(r'^\s*(\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}\.\d{3})\s', line)
    if m and epoch_anchor is not None and local_anchor:
        try:
            now = datetime.datetime.now()
            dt = datetime.datetime.strptime(f"{now.year}-{m.group(1)} {m.group(2)}",
                                            "%Y-%m-%d %H:%M:%S.%f")
            a = datetime.datetime.strptime(local_anchor, "%Y-%m-%d %H:%M:%S")
            return epoch_anchor + (dt - a).total_seconds()
        except Exception:
            return None
    return None

def parse_fw(text):
    enters, exits, pubs = [], [], []
    for l in text.splitlines():
        ts = parse_ts(l)
        if "event=CDAC_CONTEXT_ENTER" in l:
            enters.append(dict(ts=ts, line=l,
                ctx=re.search(r'context_id=(\d+)', l),
                stid=re.search(r'server_tid=(\d+)', l),
                spid=re.search(r'server_pid=(\d+)', l),
                uid=re.search(r'caller_uid=(\d+)', l),
                pid=re.search(r'caller_pid=(\d+)', l)))
        elif "event=CDAC_CONTEXT_EXIT" in l:
            exits.append(dict(ts=ts, line=l,
                ctx=re.search(r'context_id=(\d+)', l),
                depth=re.search(r'remaining_depth=(\d+)', l),
                exc=re.search(r'exceptional=(\S+)', l)))
        elif "event=CDAC_FRAMEWORK_CONTEXT_PUBLISH" in l:
            pubs.append(dict(ts=ts, line=l,
                ctx=re.search(r'context_id=(\d+)', l),
                mt=re.search(r'msg_type=(\d+)', l),
                res=re.search(r'result=(\S+)', l)))
    return enters, exits, pubs

def parse_kern(text, epoch_anchor, local_anchor):
    ev = dict(push=[], pop=[], decision=[], enforce=[], join=[], mismatch=[])
    for l in text.splitlines():
        ts = parse_ts(l, epoch_anchor, local_anchor)
        if "CDAC_BINDER_PUSH" in l:
            m = re.search(r'seq=(\d+)', l)
            ev["push"].append(dict(ts=ts, line=l, seq=int(m.group(1)) if m else None,
                rtid=re.search(r'reporter_tid=(\d+)', l),
                uid=re.search(r'caller_uid=(\d+)', l),
                tsns=re.search(r'ts_ns=(\d+)', l)))
        elif "CDAC_BINDER_POP" in l:
            m = re.search(r'seq=(\d+)', l)
            ev["pop"].append(dict(ts=ts, line=l, seq=int(m.group(1)) if m else None,
                rtid=re.search(r'reporter_tid=(\d+)', l),
                depth=re.search(r'remaining_depth=(\d+)', l)))
        elif "real-enforce" in l:
            m = re.search(r'seq=(\d+)', l)
            ev["enforce"].append(dict(ts=ts, line=l, seq=int(m.group(1)) if m else None,
                uid=re.search(r'caller_uid=(\d+)', l),
                errno=re.search(r'errno=(-\d+)', l)))
        elif "decision" in l and "decision-apply" not in l:
            m = re.search(r'seq=(\d+)', l)
            ev["decision"].append(dict(ts=ts, line=l, seq=int(m.group(1)) if m else None,
                uid=re.search(r'caller_uid=(\d+)', l),
                matched=re.search(r'matched=(\d+)', l),
                action=re.search(r'action=(\S+)', l),
                reason=re.search(r'reason=(\S+)', l),
                oino=re.search(r'obj_ino=(\d+)', l),
                osdev=re.search(r'obj_s_dev=(\S+)', l),
                path=re.search(r'path_tail=(\S+)', l)))
        elif "CDAC_BINDER_VFS_JOIN" in l:
            m = re.search(r'seq=(\d+)', l)
            ev["join"].append(dict(ts=ts, line=l, seq=int(m.group(1)) if m else None,
                uid=re.search(r'caller_uid=(\d+)', l),
                ino=re.search(r'ino=(\d+)', l),
                sdev=re.search(r's_dev=(\S+)', l),
                flags=re.search(r'f_flags=(\S+)', l),
                jr=re.search(r'join_result=(\S+)', l),
                sr=re.search(r'stack_result=(\S+)', l)))
        elif "CDAC_BINDER_STACK_MISMATCH" in l:
            ev["mismatch"].append(dict(ts=ts, line=l))
    return ev

def get(grp):
    return grp.group(1) if grp else None

def analyze_wave(rec):
    wave = rec["wave"]
    epoch_anchor, local_anchor = anchor_epoch(rec)
    enters, exits, pubs = parse_fw(rec.get("fw", ""))
    kev = parse_kern(rec.get("kern", ""), epoch_anchor, local_anchor)
    ctxs = sorted({get(e["ctx"]) for e in enters if e["ctx"]}, key=lambda x: int(x or 0))
    reqs = {}
    for ctx in ctxs:
        seq = int(ctx)
        fwe = next((e for e in enters if get(e["ctx"]) == ctx), None)
        fwx = next((e for e in exits if get(e["ctx"]) == ctx), None)
        fwp5 = [p for p in pubs if get(p["ctx"]) == ctx and get(p["mt"]) == "5"]
        fwp6 = [p for p in pubs if get(p["ctx"]) == ctx and get(p["mt"]) == "6"]
        psh = next((p for p in kev["push"] if p["seq"] == seq), None)
        pop = next((p for p in kev["pop"] if p["seq"] == seq), None)
        decs = [d for d in kev["decision"] if d["seq"] == seq]
        enf = [d for d in kev["enforce"] if d["seq"] == seq]
        jns = [j for j in kev["join"] if j["seq"] == seq]
        caller = get(fwe["uid"]) if fwe else None
        oino = None
        if decs:
            oino = get(decs[-1]["oino"])
        elif jns:
            oino = get(jns[-1]["ino"])
        key = None
        for k, d in REQ_DEF.items():
            if caller == str(d["caller"]) and oino == str(d["obj_ino"]):
                key = k
                break
        reqs[seq] = dict(ctx=ctx, key=key, caller=caller,
            fw_enter_ts=fwe["ts"] if fwe else None,
            fw_exit_ts=fwx["ts"] if fwx else None,
            exit_depth=get(fwx["depth"]) if fwx else None,
            exit_exc=get(fwx["exc"]) if fwx else None,
            pub5=[p["ts"] for p in fwp5], pub6=[p["ts"] for p in fwp6],
            server_tid=get(fwe["stid"]) if fwe else None,
            server_pid=get(fwe["spid"]) if fwe else None,
            caller_pid=get(fwe["pid"]) if fwe else None,
            kernel_push_ts=psh["ts"] if psh else None,
            kernel_pop_ts=pop["ts"] if pop else None,
            reporter_tid=get(psh["rtid"]) if psh else None,
            push_tsns=get(psh["tsns"]) if psh else None,
            pop_depth=get(pop["depth"]) if pop else None,
            decisions=[dict(ts=d["ts"], matched=get(d["matched"]), action=get(d["action"]),
                            reason=get(d["reason"]), oino=get(d["oino"]), osdev=get(d["osdev"]),
                            path=get(d["path"])) for d in decs],
            enforce=[dict(ts=d["ts"], errno=get(d["errno"])) for d in enf],
            joins=[dict(ts=j["ts"], ino=get(j["ino"]), sdev=get(j["sdev"]),
                        flags=get(j["flags"]), jr=get(j["jr"]), sr=get(j["sr"])) for j in jns])
    # map labels
    by_seq = {}
    for seq, r in reqs.items():
        if r["key"]:
            by_seq.setdefault(r["key"], []).append(seq)
    for key, seqs in by_seq.items():
        if len(seqs) == 1:
            reqs[seqs[0]]["label"] = f"r26_{boot}_w{wave:02d}_{key}"
    # overlap pairs
    pairs = []
    seqs = sorted(reqs.keys())
    for i in range(len(seqs)):
        for j in range(i + 1, len(seqs)):
            a, b = reqs[seqs[i]], reqs[seqs[j]]
            if a["server_tid"] == b["server_tid"] and a["server_tid"] is not None:
                continue
            pts_a = [x["ts"] for x in (a["decisions"] + a["enforce"] + a["joins"]) if x.get("ts") is not None]
            pts_b = [x["ts"] for x in (b["decisions"] + b["enforce"] + b["joins"]) if x.get("ts") is not None]
            overlap = []
            if a["kernel_push_ts"] is not None and a["kernel_pop_ts"] is not None:
                overlap += [("a_decision_in_b_interval", x)
                            for x in pts_a
                            if b["kernel_push_ts"] is not None and b["kernel_pop_ts"] is not None
                            and b["kernel_push_ts"] <= x <= b["kernel_pop_ts"]]
                overlap += [("b_decision_in_a_interval", x)
                            for x in pts_b
                            if b["kernel_push_ts"] is not None and b["kernel_pop_ts"] is not None
                            and a["kernel_push_ts"] <= x <= a["kernel_pop_ts"]]
            if overlap:
                pairs.append(dict(seq_a=seqs[i], seq_b=seqs[j],
                    key_a=reqs[seqs[i]].get("key"), key_b=reqs[seqs[j]].get("key"),
                    tid_a=a["server_tid"], tid_b=b["server_tid"],
                    evidence=overlap))
    return dict(wave=wave, reqs=reqs, pairs=pairs,
                stack_mismatch=len(kev["mismatch"]),
                app_rows=rec.get("app_rows", {}),
                markers=rec.get("markers", {}), qc=rec.get("qc", ""))

def build_csv(rows):
    import io
    keys = ["boot","wave","label","key","verdict","app_result","ex","n","caller",
            "server_tid","reporter_tid","obj_join","decision","enforce",
            "fw_enter","fw_exit","k_push","k_pop","exit_depth","pop_depth"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()

def build_overlap(per):
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["boot","wave","seq_a","seq_b","key_a","key_b","tid_a","tid_b","evidence"])
    for p in per:
        for pr in p["pairs"]:
            w.writerow([boot, p["wave"], pr["seq_a"], pr["seq_b"], pr["key_a"],
                        pr["key_b"], pr["tid_a"], pr["tid_b"],
                        json.dumps(pr["evidence"], default=str)])
    return buf.getvalue()

rows = []
summary = []
raw_recs = [json.loads(l) for l in (out / "waves_raw.jsonl").read_text().splitlines() if l.strip()]
per_wave_results = []
for rec in raw_recs:
    wdir = out / f"w{rec['wave']:02d}"
    rec = dict(rec)
    rec["fw"] = (wdir / "fw.txt").read_text() if (wdir / "fw.txt").exists() else ""
    rec["kern"] = (wdir / "kern.txt").read_text() if (wdir / "kern.txt").exists() else ""
    a = analyze_wave(rec)
    app = rec.get("app_rows", {})
    markers = rec.get("markers", {})
    per = {"wave": rec["wave"], "ok": rec.get("ok"), "reqs": {}, "pairs": a["pairs"],
           "stack_mismatch": a["stack_mismatch"]}
    confirmed = False
    for seq, r in a["reqs"].items():
        key = r.get("key"); label = r.get("label")
        if not label:
            continue
        approw = app.get(label, "")
        parts = (approw or "").split(",")
        res = parts[3] if len(parts) > 3 else "?"
        ex = parts[4] if len(parts) > 4 else ""
        n = parts[14] if len(parts) > 14 else ""
        expect = REQ_DEF[key]["expect"]
        if expect == "DENY":
            ok = (res.startswith("WAVE_FAIL")
                  and any(d["matched"] == "1" and d["reason"] == "rcs26_tgt_A_X"
                          for d in r["decisions"])
                  and any(e["errno"] == "-13" for e in r["enforce"]))
            verdict = "DENY_PASS" if ok else "DENY_FAIL"
        else:
            d = REQ_DEF[key]
            marker_ok = markers.get(key) == R.sha_hex(R.p16(label)) if label else False
            ok = (res == "WAVE_OK" and n == "16" and marker_ok
                  and r["caller"] == str(REQ_DEF[key]["caller"])
                  and any(j["ino"] == str(REQ_DEF[key]["obj_ino"])
                          and j["jr"] == "joined" for j in r["joins"]))
            verdict = "ALLOW_PASS" if ok else "ALLOW_FAIL"
        row = dict(boot=boot, wave=rec["wave"], label=label, key=key, verdict=verdict,
                   app_result=res, ex=ex, n=n, caller=r["caller"], server_tid=r["server_tid"],
                   reporter_tid=r["reporter_tid"], obj_join=[j["ino"] for j in r["joins"]],
                   decision=[dict(m=d["matched"], a=d["action"], o=d["oino"], r=d["reason"]) for d in r["decisions"]],
                   enforce=[e["errno"] for e in r["enforce"]],
                   fw_enter=r["fw_enter_ts"], fw_exit=r["fw_exit_ts"],
                   k_push=r["kernel_push_ts"], k_pop=r["kernel_pop_ts"],
                   exit_depth=r["exit_depth"], pop_depth=r["pop_depth"])
        per["reqs"][label] = row
        rows.append(row)
    if a["pairs"]:
        confirmed = True
    per["confirmed_overlap"] = confirmed
    per_wave_results.append(per)
    summary.append(dict(wave=rec["wave"], ok=rec.get("ok"),
                        confirmed_overlap=confirmed,
                        n_pairs=len(a["pairs"]), n_ctx=len(a["reqs"]),
                        stack_mismatch=a["stack_mismatch"]))
(out / "waves_analyzed.jsonl").write_text(
    "\n".join(json.dumps(p, default=str) for p in per_wave_results) + "\n")
(out / "PER_REQUEST_LEDGER.csv").write_text(build_csv(rows))
(out / "OVERLAP_TABLE.csv").write_text(build_overlap(per_wave_results))
(out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
print(json.dumps(summary, indent=1, default=str))
