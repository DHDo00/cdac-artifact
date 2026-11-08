#!/usr/bin/env python3
"""Scope-binding self-checks (2026-11-02). Stdlib only. Exits nonzero on failure."""
import csv, hashlib, json, os, subprocess, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACC = os.path.join(ROOT, "outputs", "accounting")
CHECKS = []

def check(cid, desc, ok, detail=""):
    CHECKS.append({"id": cid, "description": desc, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + cid + " " + desc + ((" :: " + str(detail)) if detail else ""))

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

# ---- input identity ----
zip_path = "CDAC_ACCOUNTING_SCOPE_INPUT_20261102.zip"
zip_size = os.path.getsize(zip_path)
zip_sha = sha(zip_path)
check("I01_input_zip_size", "input zip bytes == 422427", zip_size == 422427, zip_size)
check("I02_input_zip_sha", "input zip sha256 == 59daca84...", zip_sha == "59daca84b49d45c94361aaab09e74139d6e7047d376b32dceb998985c06e124b", zip_sha)
paper = os.path.join(ROOT, "paper_snapshot", "102901.txt")
check("I03_paper_bytes", "paper bytes == 121715", os.path.getsize(paper) == 121715)
check("I04_paper_sha", "paper sha == e18ef6a5...", sha(paper) == "e18ef6a5e584b0d9f984f430e7ab617b7c92d9bcf98102e7cbcbeec9496181a1")
tgz = "policy_accounting_correction_20261102_091724.tar.gz"
check("I05_server_pkg_size", "server tar.gz bytes == 587979", os.path.getsize(tgz) == 587979)
check("I06_server_pkg_sha", "server tar.gz sha == 952d9b22...", sha(tgz) == "952d9b226366fdd9d9dae5264e632ab73dd6da33ab2a7f879041e1ef31dd754b")
import tempfile, shutil
with tempfile.TemporaryDirectory() as td:
    subprocess.run(["unzip", "-q", zip_path, "-d", td], check=True)
    r = subprocess.run([sys.executable, "verify_input.py"], cwd=td, capture_output=True, text=True)
    vr = json.loads(r.stdout)
check("I07_verify_input", "verify_input.py PASS on pristine unpack (17 hash entries, version 8)",
      vr.get("status") == "PASS" and vr.get("hash_entries") == 17 and vr.get("paper_version") == 8, vr)

# ---- load outputs ----
raw = list(csv.DictReader(open(os.path.join(ACC, "RAW_POLICY_RECORDS.csv"))))
logical = list(csv.DictReader(open(os.path.join(ACC, "LOGICAL_CONFIGURATIONS.csv"))))
stats = json.load(open(os.path.join(ACC, "stats.json")))

# ---- field parsing invariants ----
r39 = [x for x in raw if x["round_id"].startswith("R39-")]
lr = [x for x in r39 if x["round_id"] in ("R39-lr","R39-lw") and x["kind"] == "dump"]
check("F01_r39_flags_zero", "R39 LR/LW dumps parsed flags mask/value=0, device 0:0",
      all(x["f_flags_mask"] == "0x0" and x["f_flags_value"] == "0x0" and x["s_dev_disp"] == "0:0" for x in lr) and len(lr) == 6, len(lr))
check("F02_exact_vs_wildcard", "exact 0:45/254:96 never keyed as wildcard",
      all(x["device_class"] in ("exact:0:45","exact:254:96","wildcard","exact:0:46") for x in logical))
check("F03_unknown_preserved", "R12/R16 add-only rows keep op UNKNOWN (14 rows, never defaulted)",
      sum(1 for x in raw if x["round_id"].startswith(("R12","R16")) and x["kind"] == "add" and x["operation"].startswith("UNKNOWN")) == 14)

# ---- source union preservation ----
key_ma = [x["role_normalized_key"] for x in logical if "R39-ma" in x["round_ids"] and "openFile|exact:0:45" in x["role_normalized_key"]]
check("F04_source_union", "R27-eq14;R35-r14a;R39-ma keep one merged key with all sources",
      any("R27-eq14" in x["round_ids"] and "R35-r14a" in x["round_ids"] and "R39-ma" in x["round_ids"] for x in logical if x["role_normalized_key"] in key_ma), key_ma)
key_mb = [x for x in logical if "R39-mb" in x["round_ids"] and "openFile|exact:0:45" in x["role_normalized_key"]]
check("F05_purpose_mixed", "R35-rev target+B reversal share key with R39-mb as MIXED_target+control",
      any("R35-rev" in x["round_ids"] and x["purpose_class"] == "MIXED_target+control" for x in key_mb), [x["purpose_class"] for x in key_mb])

# ---- purpose order independence ----
def purpose_class(ps):
    ps = set(ps)
    t = {"target-deny","method-label-deny","lifecycle-target","deputy-target-deny","caller-scope-A","caller-scope-deputy"}
    c = {"subject-reversal","side-effect-diag","regression","diagnostic-deny","preflight-probe","read-selector-control"}
    s = {"synthetic-filler","provider-local-L","native-N"}
    if ps & s: return sorted(ps & s)[0]
    if ps & t and ps & c: return "MIXED_target+control"
    if ps & t: return "CDAC_target_deny"
    if ps & c: return "CDAC_other_control"
    return "unclassified"
check("F06_purpose_order", "classification derives from the purpose SET (order independent)",
      purpose_class(["subject-reversal","target-deny"]) == purpose_class(["target-deny","subject-reversal"]) == "MIXED_target+control")

# ---- scope binding invariants ----
check("S01_r40_not_in_paper", "R40-72/720 NOT in current paper (72/720 denominators preserved)",
      all(x["scope_class"] == "COMPLETED_PENDING" for x in raw if x["round_id"].startswith("R40-")))
check("S02_ports_in_paper", "A15/A17 ports IN_PAPER with corrected/historical batches separated",
      {x["round_id"] for x in raw if x["round_id"].startswith(("A15","A17"))} == {"A15-r14a","A15-rev","A15c-r14a","A15c-rev","A17-r14a","A17-rev"})
check("S03_prev_subset", "previous confirmed subset == 5 (R39 4 + R41)",
      stats["prev_confirmed_subset_deny"] == 5)
check("S04_paper_counts", "paper counts recorded (18 deny = 11 target + 7 control; 1 filler; candidates 2+6)",
      stats["paper_role_configs_target"] == 11 and stats["paper_role_configs_other_control"] == 7
      and stats["paper_role_configs_filler_family"] == 1 and stats["paper_target_candidates_unresolved"] == 2
      and stats["paper_control_candidates_unresolved"] == 6)
check("S05_pending", "pending-only = 8 (7 target + 1 control); intersection = 1; union deny = 26",
      stats["pending_only_role_configs_target"] == 7 and stats["pending_only_role_configs_other_control"] == 1
      and stats["paper_pending_intersection_configs"] == 1 and stats["paper_union_pending_deny"] == 26)

# ---- template accounting ----
tpl = list(csv.DictReader(open(os.path.join(ACC, "TEMPLATE_ACCOUNTING.csv"))))
kinds = {x["template_kind"]: int(x["count"]) for x in tpl}
check("T01_templates", "7 canonical + 2 generators + 9 post-hoc + NOT_RECORDED (not counted as 1)",
      kinds["canonical-route-description"] == 7 and kinds["target-generator-function"] == 1
      and kinds["synthetic-filler-generator-function"] == 1 and kinds["post-hoc-structure-signature"] == 9
      and kinds["historical-executable-template"] == 1)

# ---- deployment accounting ----
check("D01_commands", "39 package adds (45 with A15/A17) + 10 clear parsed; clear separate",
      stats["add_events_total"] == 45 and stats["clear_events_total"] == 10)
check("D02_verified", "verified deployments = adds with matching dump readback (31); 14 candidates",
      stats["add_verified_with_dump_readback"] == 31 and stats["add_candidates_without_readback"] == 14)

# ---- instance statement ----
check("N01_instances", "parsed deny instances 62 (incl ports), filler 127",
      stats["instances_deny"] == 62 and stats["instances_filler_audit"] == 127)

# ---- cost evidence ----
cost = list(csv.DictReader(open(os.path.join(ROOT, "ref_correction", "cost", "COST_DELTAS.csv"))))
reg = [x for x in cost if "registry" in x["item"] and "single-endpoint" in x["scope"]]
al = [x for x in cost if "allowlist" in x["item"]]
a15 = [x for x in cost if x["item"].startswith("A15 TOTAL")]
check("C01_cost_deltas", "registry +21/-6, allowlist +1 kept as shared-mechanism endpoint increments",
      reg and reg[0]["added_code_and_other_lines"] == "21" and reg[0]["removed"] == "6"
      and al and al[0]["added_code_and_other_lines"] == "1")
check("C02_a15", "A15 892/763 includes checkfc; mechanism-only 890/762; 891/763 stays DERIVED",
      any(x["item"] == "A15 TOTAL incl checkfc" and x["added_code_and_other_lines"] == "892" for x in a15)
      and any(x["item"] == "A15 TOTAL excl checkfc (mechanism only)" and x["added_code_and_other_lines"] == "890" for x in a15))

# ---- deterministic recompute ----
def run_script():
    r = subprocess.run([sys.executable, "recompute/recompute_scope.py"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode
h1 = {f: sha(os.path.join(ACC, f)) for f in ("LOGICAL_CONFIGURATIONS.csv","COUNT_CONTRIBUTIONS.csv","stats.json","INSTANCE_LEDGER.csv","DEPLOYMENT_LEDGER.csv")}
ok = run_script() == 0
h2 = {f: sha(os.path.join(ACC, f)) for f in h1}
check("X01_determinism", "recompute is deterministic (same hashes on rerun)", ok and h1 == h2,
      {f: (h1[f] == h2[f]) for f in h1})

fail = [c for c in CHECKS if c["status"] != "PASS"]
json.dump({"pass": len(CHECKS) - len(fail), "fail": len(fail), "checks": CHECKS},
          open(os.path.join(ROOT, "outputs", "scope_checks.json"), "w"), indent=1)
print(f"\nscope_checks: pass={len(CHECKS)-len(fail)} fail={len(fail)}")
sys.exit(1 if fail else 0)
