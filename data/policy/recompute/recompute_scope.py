#!/usr/bin/env python3
"""CDAC policy accounting - scope binding recompute (2026-11-02).

Reads:
  ref_correction/originals + ref_correction/recompute/rounds.json  (corrected parse set)
  inputs_extra/a15_port, a15_corrected, a17_port                    (paper-scope ports)
  recompute/scope_overrides.json, recompute/paper_binding.csv
Emits to outputs/accounting/:
  RAW_POLICY_RECORDS.csv, LOGICAL_CONFIGURATIONS.csv, ROLE_VIEW.csv,
  INSTANCE_LEDGER.csv, DEPLOYMENT_LEDGER.csv, COUNT_CONTRIBUTIONS.csv,
  COUNT_CHANGE_DECOMPOSITION.csv, SCOPE_MANIFEST.csv, stats.json
Semantics preserved from the 091724 correction round:
  device exact (maj:min) != wildcard 0:0 (no prefix test)
  operation authoritative dump only; add-echo missing -> UNKNOWN (never defaults)
  unknown fields stay UNKNOWN; merged configs UNION sources/purposes/scope
  role class derived from the purpose SET (order independent)
Stdlib only.
"""
import csv, hashlib, json, os, re
from collections import defaultdict, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = os.path.join(ROOT, "ref_correction", "originals")
EXTRA = os.path.join(ROOT, "inputs_extra")
OUT = os.path.join(ROOT, "outputs", "accounting")
os.makedirs(OUT, exist_ok=True)

CFG = json.load(open(os.path.join(ROOT, "ref_correction", "recompute", "rounds.json")))
META = CFG["meta"]
ROUNDS = [dict(r) for r in CFG["rounds"]]
OVERRIDES = json.load(open(os.path.join(ROOT, "recompute", "scope_overrides.json")))

# ---- paper-scope port rounds (read-only reuse of existing evidence) ----
PORT_ROUNDS = [
 {"id":"A15-r14a","scope_class":"IN_PAPER","route":"6/501","endpoint":"MediaProvider","mechanism":"C",
  "purposes":["target-deny"],"filter":{"reason":["a15cdac_r14a"]},
  "subject_map":{"10115":"A","10116":"B"},
  "sources":[{"rel":"a15_port/b1_rule_add.txt","kind":"add","boot":"a15-hist-boot1"},
             {"rel":"a15_port/b1_rule_dump.txt","kind":"dump","boot":"a15-hist-boot1"}]},
 {"id":"A15-rev","scope_class":"IN_PAPER","route":"6/501","endpoint":"MediaProvider","mechanism":"C",
  "purposes":["subject-reversal"],"filter":{"reason":["a15cdac_rev"]},
  "subject_map":{"10115":"A","10116":"B"},
  "sources":[{"rel":"a15_port/b2_rule_add.txt","kind":"add","boot":"a15-hist-boot1"},
             {"rel":"a15_port/b2_rule_dump.txt","kind":"dump","boot":"a15-hist-boot1"}]},
 {"id":"A15c-r14a","scope_class":"IN_PAPER","route":"6/501","endpoint":"MediaProvider","mechanism":"C",
  "purposes":["target-deny"],"filter":{"reason":["a15cdac_r14a"]},
  "subject_map":{"10115":"A","10116":"B"},
  "sources":[{"rel":"a15_corrected/b1_rule_add.txt","kind":"add","boot":"a15-corr-boot1"},
             {"rel":"a15_corrected/b1_rule_dump.txt","kind":"dump","boot":"a15-corr-boot1"}]},
 {"id":"A15c-rev","scope_class":"IN_PAPER","route":"6/501","endpoint":"MediaProvider","mechanism":"C",
  "purposes":["subject-reversal"],"filter":{"reason":["a15cdac_rev"]},
  "subject_map":{"10115":"A","10116":"B"},
  "sources":[{"rel":"a15_corrected/b2_rule_add.txt","kind":"add","boot":"a15-corr-boot1"},
             {"rel":"a15_corrected/b2_rule_dump.txt","kind":"dump","boot":"a15-corr-boot1"}]},
 {"id":"A17-r14a","scope_class":"IN_PAPER","route":"6/501","endpoint":"MediaProvider","mechanism":"C",
  "purposes":["target-deny"],"filter":{"reason":["cdac35_r14a"]},
  "subject_map":{"10122":"A","10123":"B"},
  "sources":[{"rel":"a17_port/b1_rule_add.txt","kind":"add","boot":"a17-boot1"},
             {"rel":"a17_port/b1_rule_dump.txt","kind":"dump","boot":"a17-boot1"}]},
 {"id":"A17-rev","scope_class":"IN_PAPER","route":"6/501","endpoint":"MediaProvider","mechanism":"C",
  "purposes":["subject-reversal"],"filter":{"reason":["cdac35_rev"]},
  "subject_map":{"10122":"A","10123":"B"},
  "sources":[{"rel":"a17_port/b2_rule_add.txt","kind":"add","boot":"a17-boot1"},
             {"rel":"a17_port/b2_rule_dump.txt","kind":"dump","boot":"a17-boot1"}]},
]

for rd in ROUNDS:
    rd["scope_class_prev"] = rd["scope_class"]
    rd["scope_class"] = OVERRIDES.get(rd["id"], rd["scope_class"])
for rd in PORT_ROUNDS:
    rd["scope_class_prev"] = "NEW_PAPER_SCOPE_PORT"
    ROUNDS.append(rd)

TARGET_PURPOSES = set(META["target_purposes"])
CONTROL_PURPOSES = set(META["control_purposes"])
SPECIAL_PURPOSES = set(META["special_purposes"])

REASON_OBJECT = {
    "mech_C_X":"X","mech_C_D2":"D2","esp_regress":"X","rcs21_tgt_A_X":"X",
    "rcs24_tgt_A_X":"X","rcs24_lc_A_X0":"X0","rcs24_lc_A_X1":"X1",
    "rcs26_tgt_A_X":"X","r30_obj_A_O":"X(alias O)","r30_objname_A_W":"W(name)",
    "r30_objname_A_O":"O(name)","r41_tgt_A_X":"X",
    "media16_X":"X.mp4","ct_D2":"D2","cdac25_diag_BX":"X","cdac27_pA":"X",
    "cdac35_r14a":"X","cdac35_rev":"X","cdac36_op":"X","cdac38_proxy":"X(proxy)",
    "cdac39_ma":"X","cdac39_mb":"X","cdac39_lr":"X","cdac39_lw":"X",
    "cdac40_scope":"X","a15cdac_r14a":"X","a15cdac_rev":"X",
    "formal_s3_b15_rule_on":"X(S10 route)","formal_s3_b12_rule_on":"X(S10 route)",
    "batch2_route_scoped_expected_deny":"X",
    "batch3a_session_A_dp_target_write_once_deny":"X",
}

def sdev_display(v):
    v = (v or "").strip()
    if ":" in v:
        return v
    try:
        n = int(v)
    except ValueError:
        return "UNKNOWN(" + (v or "?") + ")"
    if n == 0:
        return "0:0"
    return "%d:%d" % (n >> 20, n & 255)

def device_class(v):
    if v == "0:0":
        return "wildcard"
    if v.startswith("UNKNOWN"):
        return "unknown"
    return "exact:" + v

def parse_kv(txt):
    d = {}
    for tok in txt.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            d[k] = v
    return d

def parse_add(line):
    if not line.startswith("policy_add ok:"):
        return None
    return parse_kv(line[len("policy_add ok:"):])

def parse_dump_slot(line):
    m = re.match(r"^\[\d+\]\s+(.*)$", line)
    return parse_kv(m.group(1)) if m else None

def parse_clear(line):
    return line.startswith("policy_clear ok")

def purpose_class(purposes):
    ps = set(purposes)
    if ps & SPECIAL_PURPOSES:
        return sorted(ps & SPECIAL_PURPOSES)[0]
    has_target = bool(ps & TARGET_PURPOSES)
    has_control = bool(ps & CONTROL_PURPOSES)
    if has_target and has_control:
        return "MIXED_target+control"
    if has_target:
        return "CDAC_target_deny"
    if has_control:
        return "CDAC_other_control"
    return "unclassified"

def decision_class(raw):
    if raw in ("audit",):
        return "audit"
    if raw in ("would-deny", "deny", "2"):
        return "deny"
    if raw in ("", None):
        return "none"
    return "UNKNOWN(" + str(raw) + ")"

def resolve(rd, rel):
    p = os.path.join(EXTRA, rel) if rd.get("_extra") else os.path.join(ORIG, rel)
    return p

def main():
    for rd in ROUNDS:
        rd["_extra"] = False
    for rd in PORT_ROUNDS:
        rd["_extra"] = True

    parsed_files = {}
    file_events = defaultdict(lambda: {"adds": 0, "clears": 0})
    for rd in ROUNDS:
        for s in rd.get("sources", []):
            rel = s["rel"]
            p = resolve(rd, rel)
            if not os.path.exists(p):
                continue
            if rel in parsed_files:
                continue
            data = open(p, "rb").read()
            sha = hashlib.sha256(data).hexdigest()
            parsed_files[rel] = {"sha": sha, "size": len(data), "lines": [],
                                 "events": {"adds": 0, "clears": 0}, "src": p}
            for ln, raw in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
                a = parse_add(raw)
                d = parse_dump_slot(raw)
                if a is not None:
                    parsed_files[rel]["lines"].append((ln, "add", a, raw))
                    parsed_files[rel]["events"]["adds"] += 1
                elif d is not None:
                    parsed_files[rel]["lines"].append((ln, "dump", d, raw))
                elif parse_clear(raw):
                    parsed_files[rel]["events"]["clears"] += 1

    def collect(rd):
        out = []
        for s in rd.get("sources", []):
            rel = s["rel"]
            if rel not in parsed_files:
                continue
            boot = s.get("boot", "single")
            for ln, kind, fields, rawline in parsed_files[rel]["lines"]:
                rec = dict(fields)
                rec.update(_kind=kind, _rel=rel, _ln=ln, _boot=boot,
                           _sha=parsed_files[rel]["sha"], _raw=rawline,
                           _round=rd["id"], _scope=rd["scope_class"],
                           _scope_prev=rd["scope_class_prev"],
                           _purpose=rd["purposes"])
                out.append(rec)
        dump_ops = defaultdict(list)
        for rec in out:
            if rec["_kind"] == "dump":
                key = (rec.get("reason", ""), rec.get("caller_uid", ""))
                op = rec.get("operation")
                if op not in ("", "-", None):
                    dump_ops[key].append(op)
        dump_rel = defaultdict(list)
        for rec in out:
            if rec["_kind"] == "dump":
                dump_rel[(rec.get("reason",""), rec.get("caller_uid",""))].append(
                    (rec.get("required_relation_type",""), rec.get("required_relation_stage","")))
        for rec in out:
            if rec["_kind"] == "add" and rec.get("operation", "") in ("", "-", None):
                key = (rec.get("reason", ""), rec.get("caller_uid", ""))
                ops = dump_ops.get(key, [])
                if len(set(ops)) == 1:
                    rec["operation"] = ops[0]
                    rec["_op_evidence"] = "dump-inherited"
                else:
                    rec["operation"] = "UNKNOWN(no-op-in-add-echo)"
                    rec["_op_evidence"] = "absent-in-add; no-unique-dump-inheritance"
            elif rec["_kind"] == "dump":
                rec["_op_evidence"] = "authoritative-dump"
            if rec["_kind"] == "add" and not rec.get("required_relation_type",""):
                key = (rec.get("reason",""), rec.get("caller_uid",""))
                rels = dump_rel.get(key, [])
                uniq = set(rels)
                if len(uniq) == 1 and list(uniq)[0][0] != "":
                    rec["required_relation_type"], rec["required_relation_stage"] = list(uniq)[0]
                    rec["_rel_evidence"] = "dump-inherited"
                else:
                    rec["_rel_evidence"] = "UNKNOWN(absent-in-add; no-unique-dump)"
            elif rec["_kind"] == "dump":
                rec["_rel_evidence"] = "authoritative-dump"
        return out

    records = []
    for rd in ROUNDS:
        for rec in collect(rd):
            f = rd.get("filter") or {}
            if f.get("reason") and rec.get("reason", "") not in f["reason"]:
                continue
            if f.get("reason_prefix") and not any(rec.get("reason", "").startswith(p) for p in f["reason_prefix"]):
                continue
            if f.get("flags_value") and rec.get("f_flags_value", "") not in f["flags_value"]:
                continue
            if f.get("operation") and rec.get("operation", "") not in f["operation"]:
                continue
            subj_map = {**META["subject_defaults"], **rd.get("subject_map", {})}
            uid = rec.get("caller_uid", "")
            subj = subj_map.get(uid, ("uid:" + uid) if uid else "UNKNOWN(no-uid)")
            if f.get("subject") and subj not in f["subject"]:
                continue
            reason = rec.get("reason", "")
            if reason.startswith("rcs21_fill_"):
                obj = "filler-obj"
            else:
                obj = REASON_OBJECT.get(reason, "UNKNOWN(reason:" + reason + ")" if reason else "UNKNOWN(no-reason)")
            if rd["id"] == "R24-lc0":
                obj = "X0"
            elif rd["id"] == "R24-lc1":
                obj = "X1"
            elif rd["id"] == "R30-name-W":
                obj = "W(name)"
            elif rd["id"] == "R30-name-O":
                obj = "O(name)"
            op = rec.get("operation")
            if op in ("", "-", None):
                op = "UNKNOWN(no-op-in-source)"
            fmm = rec.get("f_flags_mask", "")
            fmv = rec.get("f_flags_value", "")
            fdm = rec.get("f_mode_mask", "")
            fdv = rec.get("f_mode_value", "")
            relt = rec.get("required_relation_type", "")
            rels = rec.get("required_relation_stage", "")
            sdev = sdev_display(rec.get("s_dev", ""))
            dcls = decision_class(rec.get("decision", ""))
            path = rec.get("path_tail", "-")
            path_class = "none" if path in ("", "-") else ("path:" + path)
            rec.update(_subject=subj, _object=obj, _op=op, _fmm=fmm, _fmv=fmv,
                       _fdm=fdm, _fdv=fdv, _relt=relt, _rels=rels, _sdev=sdev,
                       _dcls=dcls, _path=path_class)
            records.append(rec)

    # raw field key (un-normalized provenance)
    for rec in records:
        raw = "|".join([
            rec.get("schema", "v2"), rec.get("service_id", "?"), rec.get("op_id", "?"),
            rec.get("caller_uid", "?"), rec.get("operation", "-"), rec.get("path_tail", "-"),
            rec.get("ino", "?"), rec.get("s_dev", "?"), rec.get("f_flags_mask", ""),
            rec.get("f_flags_value", ""), rec.get("f_mode_mask", ""), rec.get("f_mode_value", ""),
            rec.get("required_relation_type", ""), rec.get("required_relation_stage", ""),
            rec.get("decision", ""), rec.get("reason", "")])
        rec["raw_field_key"] = raw

    for rec in records:
        key = "|".join([
            rec.get("schema", "v2"),
            rec.get("service_id", "?"), rec.get("op_id", "?"),
            rec["_subject"], rec["_object"], rec["_op"],
            device_class(rec["_sdev"]), rec["_path"],
            "fF:" + rec["_fmm"] + "/" + rec["_fmv"], "fM:" + rec["_fdm"] + "/" + rec["_fdv"],
            "rel:" + rec["_relt"] + "/" + rec["_rels"], rec["_dcls"]])
        rec["role_normalized_key"] = key

    # RAW_POLICY_RECORDS.csv
    cols = ["round_id","scope_class","scope_class_prev","kind","boot","file_rel","line","sha256",
            "service_id","op_id","caller_uid","operation","op_evidence","path_tail",
            "ino","s_dev_raw","s_dev_disp","device_class","f_flags_mask","f_flags_value",
            "f_mode_mask","f_mode_value","required_relation_type","required_relation_stage",
            "decision","decision_class","reason","subject_role","object_role",
            "raw_field_key","role_normalized_key"]
    with open(os.path.join(OUT, "RAW_POLICY_RECORDS.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for rec in records:
            w.writerow({
                "round_id": rec["_round"], "scope_class": rec["_scope"], "scope_class_prev": rec["_scope_prev"],
                "kind": rec["_kind"], "boot": rec["_boot"], "file_rel": rec["_rel"], "line": rec["_ln"],
                "sha256": rec["_sha"], "service_id": rec.get("service_id",""), "op_id": rec.get("op_id",""),
                "caller_uid": rec.get("caller_uid",""), "operation": rec.get("operation",""),
                "op_evidence": rec.get("_op_evidence",""), "path_tail": rec.get("path_tail","-"),
                "ino": rec.get("ino",""), "s_dev_raw": rec.get("s_dev",""), "s_dev_disp": rec["_sdev"],
                "device_class": device_class(rec["_sdev"]),
                "f_flags_mask": rec["_fmm"], "f_flags_value": rec["_fmv"],
                "f_mode_mask": rec["_fdm"], "f_mode_value": rec["_fdv"],
                "required_relation_type": rec["_relt"], "required_relation_stage": rec["_rels"],
                "decision": rec.get("decision",""), "decision_class": rec["_dcls"],
                "reason": rec.get("reason",""), "subject_role": rec["_subject"], "object_role": rec["_object"],
                "raw_field_key": rec["raw_field_key"], "role_normalized_key": rec["role_normalized_key"]})

    # merge logical configs (UNION)
    logical = OrderedDict()
    for rec in records:
        k = rec["role_normalized_key"]
        v = logical.get(k)
        if v is None:
            v = {"role_normalized_key": k, "schema": rec.get("schema","v2"),
                 "service_id": rec.get("service_id","?"), "op_id": rec.get("op_id","?"),
                 "subject_role": rec["_subject"], "object_role": rec["_object"],
                 "operation": rec["_op"], "device_disp": rec["_sdev"],
                 "device_class": device_class(rec["_sdev"]), "path_selector": rec["_path"],
                 "f_flags_mask": rec["_fmm"], "f_flags_value": rec["_fmv"],
                 "f_mode_mask": rec["_fdm"], "f_mode_value": rec["_fdv"],
                 "relation_type": rec["_relt"], "relation_stage": rec["_rels"],
                 "decision_class": rec["_dcls"],
                 "purposes": set(), "scope_classes": set(), "scope_classes_prev": set(),
                 "sources": set(), "round_ids": set(), "instances": set(),
                 "op_evidence": set(), "rel_evidence": set()}
            logical[k] = v
        v["purposes"].update(rec["_purpose"])
        v["scope_classes"].add(rec["_scope"])
        v["scope_classes_prev"].add(rec["_scope_prev"])
        v["sources"].add(rec["_rel"] + ":" + str(rec["_ln"]))
        v["round_ids"].add(rec["_round"])
        v["op_evidence"].update([rec.get("_op_evidence","")])
        v["rel_evidence"].update([rec.get("_rel_evidence","")])
        v["instances"].add("|".join([rec["_boot"], rec.get("caller_uid","?"), rec.get("ino","?"),
                                     rec["_sdev"], rec["_fmm"], rec["_fmv"], rec["_fdm"], rec["_fdv"],
                                     rec["_relt"], rec["_rels"], rec["_dcls"], rec.get("reason","")]))

    for k, v in logical.items():
        ps = sorted(v["purposes"])
        v["purpose_class"] = purpose_class(ps)
        v["purposes"] = ";".join(ps)
        v["scope_classes"] = ";".join(sorted(v["scope_classes"]))
        v["scope_classes_prev"] = ";".join(sorted(v["scope_classes_prev"]))
        v["sources"] = ";".join(sorted(v["sources"]))
        v["round_ids"] = ";".join(sorted(v["round_ids"]))
        v["op_evidence"] = ";".join(sorted(v["op_evidence"]))
        v["rel_evidence"] = ";".join(sorted(v["rel_evidence"]))
        v["n_instances"] = len(v["instances"])
        # unresolved-candidate test: any op/rel unknown due to missing evidence
        v["op_unknown"] = any(e.startswith("UNKNOWN") or e.startswith("absent-in-add") for e in v["op_evidence"].split(";"))
        v["rel_unknown"] = any(e.startswith("UNKNOWN") for e in v["rel_evidence"].split(";"))
        v["has_authoritative_dump"] = "authoritative-dump" in v["op_evidence"].split(";")
        v["evidence_status"] = ("CONFIRMED" if v["has_authoritative_dump"] or v["decision_class"] != "deny"
                                else ("CANDIDATE_UNRESOLVED" if (v["op_unknown"] or v["rel_unknown"]) else "REPORT_ONLY"))

    fieldnames = ["role_normalized_key","schema","service_id","op_id","subject_role","object_role",
        "operation","device_disp","device_class","path_selector","f_flags_mask","f_flags_value",
        "f_mode_mask","f_mode_value","relation_type","relation_stage","decision_class","purpose_class",
        "purposes","scope_classes","scope_classes_prev","round_ids","n_instances","sources",
        "op_evidence","rel_evidence","evidence_status"]
    with open(os.path.join(OUT, "LOGICAL_CONFIGURATIONS.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for v in logical.values():
            w.writerow(v)

    with open(os.path.join(OUT, "ROLE_VIEW.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[x for x in fieldnames if x != "role_normalized_key"] + ["role_normalized_key"],
                           extrasaction="ignore")
        w.writeheader()
        for v in logical.values():
            row = {k: v[k] for k in fieldnames}
            w.writerow(row)

    # INSTANCE_LEDGER
    inst = OrderedDict()
    for rec in records:
        key = "|".join([rec["_round"], rec["_boot"], rec.get("caller_uid","?"), rec.get("ino","?"),
                        rec["_sdev"], rec["_fmm"], rec["_fmv"], rec["_fdm"], rec["_fdv"],
                        rec["_dcls"], rec.get("reason","")])
        prev = inst.get(key)
        if prev is None:
            inst[key] = rec
        elif prev["_kind"] == "add" and rec["_kind"] == "dump":
            inst[key] = rec
    with open(os.path.join(OUT, "INSTANCE_LEDGER.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["round_id","scope_class","scope_class_prev","boot","caller_uid",
            "subject_role","ino","s_dev_disp","operation","op_evidence","f_flags_mask","f_flags_value",
            "f_mode_mask","f_mode_value","relation_type","relation_stage","decision_class","reason",
            "object_role","file_rel","line","sha256","role_normalized_key"], extrasaction="ignore")
        w.writeheader()
        for rec in inst.values():
            w.writerow({"round_id":rec["_round"],"scope_class":rec["_scope"],"scope_class_prev":rec["_scope_prev"],
                "boot":rec["_boot"],"caller_uid":rec.get("caller_uid",""),"subject_role":rec["_subject"],
                "ino":rec.get("ino",""),"s_dev_disp":rec["_sdev"],"operation":rec.get("operation",""),
                "op_evidence":rec.get("_op_evidence",""),"f_flags_mask":rec["_fmm"],"f_flags_value":rec["_fmv"],
                "f_mode_mask":rec["_fdm"],"f_mode_value":rec["_fdv"],
                "relation_type":rec["_relt"],"relation_stage":rec["_rels"],
                "decision_class":rec["_dcls"],"reason":rec.get("reason",""),"object_role":rec["_object"],
                "file_rel":rec["_rel"],"line":rec["_ln"],"sha256":rec["_sha"],
                "role_normalized_key":rec["role_normalized_key"]})

    # DEPLOYMENT_LEDGER + verified deployment
    # verified add: exists an authoritative dump with same round+boot+reason+caller
    dump_idx = defaultdict(set)
    for rec in records:
        if rec["_kind"] == "dump":
            dump_idx[(rec["_round"], rec["_boot"])].add((rec.get("reason",""), rec.get("caller_uid","")))
    depl_rows = []
    add_records = [r for r in records if r["_kind"] == "add"]
    # per add record: verified iff same (round,boot,reason,caller) has an authoritative dump
    for r in add_records:
        r["_verified_readback"] = (r.get("reason",""), r.get("caller_uid","")) in dump_idx.get(
            (r["_round"], r["_boot"]), set())
    for rd in ROUNDS:
        for s in rd.get("sources", []):
            rel = s["rel"]
            if rel not in parsed_files:
                continue
            ev = parsed_files[rel]["events"]
            rows = [r for r in add_records if r["_rel"] == rel and r["_round"] == rd["id"]]
            verified = sum(1 for r in rows if r["_verified_readback"])
            depl_rows.append({"round_id": rd["id"], "scope_class": rd["scope_class"],
                "scope_class_prev": rd["scope_class_prev"], "boot": s.get("boot","single"),
                "file_rel": rel, "add_events": ev["adds"], "clear_events": ev["clears"],
                "add_with_matching_dump_readback": verified,
                "add_without_readback_candidate": ev["adds"] - verified,
                "readback_available": "yes" if any(k=="dump" for _,k,_,_ in parsed_files[rel]["lines"]) else "no",
                "sha256": parsed_files[rel]["sha"]})
    with open(os.path.join(OUT, "DEPLOYMENT_LEDGER.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["round_id","scope_class","scope_class_prev","boot","file_rel",
            "add_events","clear_events","add_with_matching_dump_readback","add_without_readback_candidate",
            "readback_available","sha256"], extrasaction="ignore")
        w.writeheader()
        for d in depl_rows:
            w.writerow(d)

    # ---- COUNT_CONTRIBUTIONS + stats ----
    contrib = []
    def add_count(metric, value, scope, detail, key, source):
        contrib.append({"metric": metric, "value": value, "scope": scope,
                        "detail": detail, "role_normalized_key": key, "source": source})

    for k, v in logical.items():
        scopes = set(v["scope_classes"].split(";"))
        scopes_prev = set(v["scope_classes_prev"].split(";"))
        in_paper = "IN_PAPER" in scopes
        pending = "COMPLETED_PENDING" in scopes
        prev_main = "MAIN_INCLUDED" in scopes_prev
        if v["decision_class"] == "deny":
            pc = v["purpose_class"]
            is_target = pc in ("CDAC_target_deny", "MIXED_target+control")
            if in_paper:
                if is_target:
                    add_count("paper_role_configs_target", 1, "IN_PAPER", pc, k, v["round_ids"])
                    if v["evidence_status"] == "CANDIDATE_UNRESOLVED":
                        add_count("paper_role_configs_target_candidates", 1, "IN_PAPER",
                                  "op/rel UNKNOWN in package evidence", k, v["round_ids"])
                else:
                    add_count("paper_role_configs_other_control", 1, "IN_PAPER", pc, k, v["round_ids"])
            if pending and not in_paper:
                if is_target:
                    add_count("pending_only_role_configs_target", 1, "COMPLETED_PENDING", pc, k, v["round_ids"])
                else:
                    add_count("pending_only_role_configs_other_control", 1, "COMPLETED_PENDING", pc, k, v["round_ids"])
            if in_paper and pending:
                add_count("paper_pending_intersection_configs", 1, "IN_PAPER∩COMPLETED_PENDING", pc, k, v["round_ids"])
            if in_paper or pending:
                add_count("paper_union_pending_deny", 1, "IN_PAPER∪COMPLETED_PENDING", pc, k, v["round_ids"])
            if prev_main:
                add_count("prev_confirmed_subset_deny", 1, "MAIN_INCLUDED(prev)", pc, k, v["round_ids"])
        elif v["decision_class"] == "audit":
            if in_paper:
                add_count("paper_role_configs_filler_family", 1, "IN_PAPER", "synthetic-filler", k, v["round_ids"])

    def metric_sum(name, scope=None):
        return sum(c["value"] for c in contrib if c["metric"] == name and (scope is None or c["scope"] == scope))

    with open(os.path.join(OUT, "COUNT_CONTRIBUTIONS.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric","value","scope","detail","role_normalized_key","source"], extrasaction="ignore")
        w.writeheader()
        for c in contrib:
            w.writerow(c)


    def cfg_in_paper(k):
        return "IN_PAPER" in logical[k]["scope_classes"].split(";")
    paper_deny = [v for k, v in logical.items() if v["decision_class"] == "deny" and cfg_in_paper(k)]
    paper_target_cands = sum(1 for v in paper_deny if v["purpose_class"] in ("CDAC_target_deny", "MIXED_target+control")
                             and v["evidence_status"] == "CANDIDATE_UNRESOLVED")
    paper_control_cands = sum(1 for v in paper_deny if v["purpose_class"] == "CDAC_other_control"
                              and v["evidence_status"] == "CANDIDATE_UNRESOLVED")
    stats = {
        "paper_version": 8,
        "paper_sha256": "e18ef6a5e584b0d9f984f430e7ab617b7c92d9bcf98102e7cbcbeec9496181a1",
        "paper_scope": "all experiments adopted in current paper (binding: recompute/paper_binding.csv)",
        "round_rows": len(ROUNDS),
        "raw_records_parsed": len(records),
        "paper_role_configs_target": metric_sum("paper_role_configs_target"),
        "paper_role_configs_other_control": metric_sum("paper_role_configs_other_control"),
        "paper_role_configs_filler_family": metric_sum("paper_role_configs_filler_family"),
        "paper_target_candidates_unresolved": paper_target_cands,
        "paper_control_candidates_unresolved": paper_control_cands,
        "pending_only_role_configs_target": metric_sum("pending_only_role_configs_target"),
        "pending_only_role_configs_other_control": metric_sum("pending_only_role_configs_other_control"),
        "paper_pending_intersection_configs": metric_sum("paper_pending_intersection_configs"),
        "paper_union_pending_deny": metric_sum("paper_union_pending_deny"),
        "prev_confirmed_subset_deny": metric_sum("prev_confirmed_subset_deny"),
        "instances_deny": sum(1 for rec in inst.values() if rec["_dcls"] == "deny"),
        "instances_filler_audit": sum(1 for rec in inst.values() if rec["_dcls"] == "audit"),
        "instances_deny_in_paper": sum(1 for rec in inst.values()
                                       if rec["_dcls"] == "deny" and rec["_scope"] == "IN_PAPER"),
        "instances_filler_in_paper": sum(1 for rec in inst.values()
                                         if rec["_dcls"] == "audit" and rec["_scope"] == "IN_PAPER"),
        "add_events_total": sum(parsed_files[r]["events"]["adds"] for r in parsed_files),
        "clear_events_total": sum(parsed_files[r]["events"]["clears"] for r in parsed_files),
        "add_verified_with_dump_readback": sum(1 for r in add_records if r["_verified_readback"]),
        "add_candidates_without_readback": sum(1 for r in add_records if not r["_verified_readback"]),
        "global_template_count": "UNRESOLVED (historical executable templates NOT_RECORDED)",
        "expert_active_hours": "NOT_MEASURED",
    }
    json.dump(stats, open(os.path.join(OUT, "stats.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(stats, indent=1, ensure_ascii=False))

if __name__ == "__main__":
    main()
