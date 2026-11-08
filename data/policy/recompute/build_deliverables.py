#!/usr/bin/env python3
"""Build scope-binding derived tables from outputs/accounting + frozen references."""
import csv, json, os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACC = os.path.join(ROOT, "outputs", "accounting")
os.makedirs(ACC, exist_ok=True)

def read(name):
    return list(csv.DictReader(open(os.path.join(ACC, name))))

logical = read("LOGICAL_CONFIGURATIONS.csv")
inst = read("INSTANCE_LEDGER.csv")
depl = read("DEPLOYMENT_LEDGER.csv")
binding = list(csv.DictReader(open(os.path.join(ROOT, "recompute", "paper_binding.csv"))))
overrides = json.load(open(os.path.join(ROOT, "recompute", "scope_overrides.json")))

# ============ Panel A: algorithm comparison over the common experiment scope ============
panel_a = [
 {"panel":"A_same_range_algorithm","metric":"deny_logical_configs_CDAC","old":26,"new":24,"delta":-2,
  "cause":"field fix + source recovery","detail":"R39 LR/LW bogus keys removed and re-parsed from six real dumps (they merge into existing R36-SR/SW keys): -2; exact 0:45 no longer treated as wildcard splits R27-eq23 from R40-RA: +1; R30-name-O report-only row dropped (no add/dump originals): -1",
  "evidence":"audit_result.json normalization_counterexamples; ERRATA.md A/C; COUNT_CONTRIBUTIONS.csv"},
 {"panel":"A_same_range_algorithm","metric":"target_or_mixed_configs","old":19,"new":17,"delta":-2,
  "cause":"field fix + class fix","detail":"R39-lr bogus (flags 0x3/0x0 hardcoded) -1; R39-lw bogus (flags 0x3/0x2 hardcoded) -1; R27-eq23/R40-RA split +1; R30-name-O dropped -1; R16-flags1 reclassified from target to control; R35-rev/R39-mb reclassified from control to MIXED target+control",
  "evidence":"audit_result.json r39_rule_comparisons (flags_agree=false); ERRATA.md A/C/D"},
 {"panel":"A_same_range_algorithm","metric":"other_control_configs","old":7,"new":7,"delta":0,
  "cause":"class re-balance only","detail":"R16-flags1 target->control (+1 control), R35-rev/R39-mb control->MIXED target (-1 control); net 0",
  "evidence":"ERRATA.md D; ROLE_VIEW.csv"},
 {"panel":"A_same_range_algorithm","metric":"synthetic_filler_family","old":1,"new":1,"delta":0,
  "cause":"unchanged","detail":"R21 filler family (127 audit slots) excluded from CDAC target counts in both algorithms",
  "evidence":"COUNTING_SPEC.md"},
 {"panel":"A_same_range_algorithm","metric":"provider_local_L","old":1,"new":2,"delta":1,
  "cause":"batch split","detail":"old merged R12-L and R12-L-reversal into one L row; corrected keeps both L phases (L excluded from CDAC deny counts either way)",
  "evidence":"ERRATA.md F"},
 {"panel":"A_same_range_algorithm","metric":"boot_bound_deny_instances","old":45,"new":56,"delta":11,
  "cause":"source recovery","detail":"R39 LR/LW six dumps (3 boots x 2 labels) newly parsed: +6; R39 MA/MB boot2+boot3 dumps: +4; R27-probe counted: +1",
  "evidence":"INSTANCE_LEDGER.csv; INPUT_MANIFEST.csv r39 dump hashes"},
 {"panel":"A_same_range_algorithm","metric":"add_command_records_parsed","old":29,"new":39,"delta":10,
  "cause":"source recovery","detail":"R39 MA/MB/LR/LW add files for 3 boots parsed (12 adds) vs old 2 adds",
  "evidence":"DEPLOYMENT_LEDGER.csv"},
 {"panel":"A_same_range_algorithm","metric":"clear_command_records_parsed","old":10,"new":10,"delta":0,
  "cause":"unchanged","detail":"clear commands are not deny deployments and are reported separately",
  "evidence":"DEPLOYMENT_LEDGER.csv"},
 {"panel":"A_same_range_algorithm","metric":"post_hoc_structure_signatures","old":8,"new":9,"delta":1,
  "cause":"field fix","detail":"wildcard device signature separated from exact-device signatures after prefix-test fix",
  "evidence":"TEMPLATE_PROVENANCE.csv"},
 {"panel":"A_same_range_algorithm","metric":"authored_template_count","old":"9 (7 canonical + 2 generators)","new":"7 canonical + 2 generators + historical executable NOT_RECORDED","delta":"re-interpreted",
  "cause":"template accounting fix","detail":"7 route descriptions and 2 R21 generator functions are different object kinds and cannot be summed as 9 expert target templates; no standalone historical template file retained",
  "evidence":"TEMPLATE_PROVENANCE.csv; Independent_Accounting_Review_20261101.md section 3"},
]

# ============ Panel B: scope comparison with the corrected algorithm ============
stats = json.load(open(os.path.join(ACC, "stats.json")))
panel_b = [
 {"panel":"B_fixed_algorithm_scope","scope":"prev confirmed subset (R39 4 + R41 = old MAIN_INCLUDED)",
  "target_configs":5,"control_configs":0,"filler_family":0,"deny_instances":None,"note":"previous round's reviewer-confirmed subset; NOT the whole-paper total"},
 {"panel":"B_fixed_algorithm_scope","scope":"current paper (IN_PAPER bound to v8 snapshot)",
  "target_configs":stats["paper_role_configs_target"],
  "control_configs":stats["paper_role_configs_other_control"],
  "filler_family":stats["paper_role_configs_filler_family"],
  "deny_instances":stats["instances_deny_in_paper"],
  "note":"includes SettingsProvider, DownloadProvider, ESP N/L/C, ESP concurrency/rule-count/no-grant, MediaProvider matrices/write/final-entry, A15/A17 ports; 2 target + 6 control candidates with UNKNOWN op/rel"},
 {"panel":"B_fixed_algorithm_scope","scope":"completed but pending (R40-72/720, R24-lc, R25, R27-eq23, R30)",
  "target_configs":stats["pending_only_role_configs_target"],
  "control_configs":stats["pending_only_role_configs_other_control"],
  "filler_family":0,"deny_instances":None,
  "note":"R40 72 and 720 denominators preserved separately; not adopted by current paper"},
 {"panel":"B_fixed_algorithm_scope","scope":"IN_PAPER ∩ COMPLETED_PENDING",
  "target_configs":stats["paper_pending_intersection_configs"],"control_configs":0,"filler_family":0,"deny_instances":None,
  "note":"one config (openFile A,X exact 0:45) sourced by in-paper R39-ma/R35 and pending R27-eq14"},
 {"panel":"B_fixed_algorithm_scope","scope":"IN_PAPER ∪ COMPLETED_PENDING",
  "target_configs":None,"control_configs":None,"filler_family":1,"deny_instances":None,
  "note":"total deny configs = " + str(stats["paper_union_pending_deny"])},
 {"panel":"B_fixed_algorithm_scope","scope":"unresolved equivalence candidates (kept separate)",
  "target_configs":None,"control_configs":None,"filler_family":0,"deny_instances":None,
  "note":"R38 deputy X(proxy) vs R40-RD deputy X (same rule, reason-derived object label differs); R12-C/R16 add-only op/rel UNKNOWN vs dump-backed ESP A,X; A15 exact 0:46 vs A16/A17 exact 0:45 cross-platform device"},
]

with open(os.path.join(ACC, "COUNT_CHANGE_DECOMPOSITION.csv"), "w", newline="") as f:
    fields = ["panel","metric","scope","old","new","delta","cause","detail","evidence","target_configs","control_configs","filler_family","deny_instances","note"]
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in panel_a:
        r = dict(r); r.setdefault("scope","common experiment rows (R12..R41, batch3d)"); w.writerow(r)
    for r in panel_b:
        r = dict(r); w.writerow(r)

# ============ SCOPE_MANIFEST.csv (updated) ============
cfg_by_round = defaultdict(set)
for r in read("RAW_POLICY_RECORDS.csv"):
    cfg_by_round[r["round_id"]].add(r["role_normalized_key"][:110])
round_purpose = {}
for r in read("RAW_POLICY_RECORDS.csv"):
    round_purpose.setdefault(r["round_id"], set()).add(r["scope_class"])

rounds_meta = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "ref_correction", "recompute", "rounds.json")))["rounds"]}
with open(os.path.join(ACC, "SCOPE_MANIFEST.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["experiment_batch","scope_class","endpoint_route","mechanism","purpose","paper_location",
                "evidence_grade","associated_role_configs","denominator_note"])
    for b in binding:
        rid = b["experiment_batch"]
        m = rounds_meta.get(rid, {})
        route = m.get("route", "")
        mech = m.get("mechanism", "")
        pur = ";".join(m.get("purposes", []))
        if rid.startswith(("A15", "A17")):
            route, mech = "6/501", "C"
        if rid in ("A15-port-historical", "A15-port-corrected", "A15c-"):
            pur = "target-deny;subject-reversal"
        cfg = ";".join(sorted(cfg_by_round.get(rid, set())))
        w.writerow([rid, b["scope_decision"], route, mech, pur, b["paper_location"],
                    "", cfg, b["denominator_evidence_note"]])

# ============ PURPOSE summary ============
with open(os.path.join(ACC, "PURPOSE_SUMMARY.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["purpose_class","count","configs"])
    cnt = Counter(r["purpose_class"] for r in logical if r["decision_class"] == "deny")
    for pc, n in sorted(cnt.items()):
        keys = [r["role_normalized_key"][:90] for r in logical if r["decision_class"] == "deny" and r["purpose_class"] == pc]
        w.writerow([pc, n, ";".join(keys)])
    w.writerow(["synthetic-filler", 1, "R21 filler family (audit decision, excluded from deny)"])
    w.writerow(["provider-local-L", 2, "R12-L;R12-L-reversal + R16-MP-L report (excluded from CDAC)"])
    w.writerow(["native-N", 1, "R12-N (authorized-access reference)"])

# ============ TEMPLATE_ACCOUNTING.csv ============
tpl = list(csv.DictReader(open(os.path.join(ROOT, "ref_correction", "accounting", "TEMPLATE_PROVENANCE.csv"))))
with open(os.path.join(ACC, "TEMPLATE_ACCOUNTING.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["template_kind","count","items","counts_as_authored_target_template","note"])
    kinds = Counter(r["kind"] for r in tpl)
    for k in ["canonical-route-description","target-generator-function","synthetic-filler-generator-function",
              "post-hoc-structure-signature","historical-executable-template","provider-local-mechanism-patch"]:
        n = kinds.get(k, 0)
        w.writerow([k, n, ";".join(r["template_id"] for r in tpl if r["kind"] == k),
                    "no" if k != "historical-executable-template" else "UNKNOWN",
                    "" if k != "historical-executable-template" else "NOT_RECORDED is a status, not a count of 1"])

# ============ DEPLOYMENT_SUMMARY.csv ============
with open(os.path.join(ACC, "DEPLOYMENT_SUMMARY.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["metric","value","definition","evidence"])
    w.writerow(["add_command_records_parsed", stats["add_events_total"],
                "policy_add ok lines parsed from package + A15/A17 rule files", "DEPLOYMENT_LEDGER.csv"])
    w.writerow(["clear_command_records_parsed", stats["clear_events_total"],
                "policy_clear ok lines parsed; clear is NOT a deny deployment", "DEPLOYMENT_LEDGER.csv"])
    w.writerow(["add_with_matching_dump_readback", stats["add_verified_with_dump_readback"],
                "add record whose (round,boot,reason,caller) has an authoritative [slot] dump in the package", "RAW_POLICY_RECORDS.csv op_evidence"])
    w.writerow(["add_without_readback_candidate", stats["add_candidates_without_readback"],
                "add-only records (R12 x6, R16 x8) without dump in package; deployment success not verifiable offline", "DEPLOYMENT_LEDGER.csv"])
    w.writerow(["request_level_execution_results", "per-round",
                "real-enforce denials with request association exist per round (R39 240, R38 6, R41 4, R35 6, A15 6, A17 12, R21 17 of 61 checks...) but are outside this rule-accounting package",
                "round ledgers; paper app:media-method-label etc."])

# ============ INSTANCE_SUMMARY.csv ============
with open(os.path.join(ACC, "INSTANCE_SUMMARY.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["metric","value","instance_key_definition","evidence_tier"])
    w.writerow(["deny_instances_parsed", stats["instances_deny"],
                "(round, boot, caller_uid, ino, s_dev, flags_mask/value, mode_mask/value, decision, reason); add+dump of same bound value set merge; repeated deployment does not add instances",
                "DUMP_AUTHORITATIVE for dump rows; DUMP_INHERITED for add rows with unique same-round dump"])
    w.writerow(["deny_instances_in_paper", stats["instances_deny_in_paper"],
                "same key restricted to IN_PAPER rounds", "as above"])
    w.writerow(["filler_instances", stats["instances_filler_audit"],
                "R21 filler audit slots (127) bound to N=128 dump", "DUMP_AUTHORITATIVE"])
    w.writerow(["56_deny_127_filler_statement","holds for the parsed subset",
                "56 = prior correction parsed deny instances (now 62 with A15/A17); 127 = R21 filler slots; A17 boot2 and R30-name-O lack packaged originals and are excluded",
                "INSTANCE_LEDGER.csv; MISSING_AND_LIMITATIONS.md"])

print("deliverables built")
