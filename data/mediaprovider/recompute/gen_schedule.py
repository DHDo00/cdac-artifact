#!/usr/bin/env python3
"""Generate the frozen SCHEDULE.csv for round 39 (mediaprovider matrix replication).

Study M (caller-object, table VII): 10 conditions/cycle x 20 cycles x 3 boots = 600.
Study L (method-label, table VIII):   8 conditions/cycle x 20 cycles x 3 boots = 480.
Frozen seed: 2026102939. Within each rule state the request order is randomized
with Random(f"{seed}|{boot}|{study}|{cycle}|{state}"). The two target rules
alternate order per cycle (odd cycles RA->RB / LW->LR; even cycles RB->RA /
LR->LW), giving exactly 10 cycles per order per boot.
"""
import csv, hashlib, random, pathlib, sys

SEED = "2026102939"
BOOTS = [1, 2, 3]
CYCLES = list(range(1, 21))
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "39_mediaprovider_matrix_replication_20261029_230000/SCHEDULE.csv")
FIX = pathlib.Path("39_mediaprovider_matrix_replication_20261029_230000/05_fixtures")

X_BYTES = (FIX / "image1.jpg").read_bytes()
X_MARKER = b"CDAC25GPSMARK_AAAA"
X_IDX = X_BYTES.index(X_MARKER)

def write_sha(token: str) -> str:
    b = bytearray(X_BYTES)
    tok = token.encode("ISO-8859-1")
    for i, ch in enumerate(tok):
        b[X_IDX + 15 + i] = ch
    return hashlib.sha256(bytes(b)).hexdigest()

# oracles (frozen from R35 historical observations)
ORACLES = {
    "AX": dict(sha="e22785cddb56824a19cd77dd45239c403c8d134250f01620f5d825ebc024c375", marker_present="true"),
    "BX": dict(sha="96f60e2770ef563d0c27182baeffd9eaaa660cd924e1e35808adebd04c5a4983", marker_present="false"),
    "AY": dict(sha="f3d29cc26f285cfe7eebdd3177a84b7bafcb93ed6ef7bad65e088e1c7c9fc5f2", marker_present="true"),
    "BY": dict(sha="3116065dfdd82767907c3b5af4d687d4b3e51bfbe4a9360ec70cd817a9250993", marker_present="false"),
}
MARKERS = {"X": "CDAC25GPSMARK_AAAA", "Y": "CDAC25GPSMARK_BBBB"}
PKG = {"A": "com.demo.espafdtest", "B": "com.demo.espafdtestb"}

COLUMNS = ["study","boot","cycle","rule_state","rule_order","exec_order","reqid","condition",
           "caller_pkg","caller_role","api_entry","method_label","mode","object","marker",
           "expected_verdict","expected_read_sha","expected_marker_present","token","expected_write_sha","rule_key"]

def rand_state(boot, study, cycle, state, items):
    r = random.Random(f"{SEED}|{boot}|{study}|{cycle}|{state}")
    out = list(items)
    r.shuffle(out)
    return out

rows = []

# ---------------- Study M: caller-object ----------------
for boot in BOOTS:
    for cycle in CYCLES:
        ra_first = (cycle % 2 == 1)
        # S0 (no rule)
        order = rand_state(boot, "M", cycle, "S0", ["AX", "BX"])
        for i, obj in enumerate(order):
            cond = f"no_rule_{obj.lower()}"
            reqid = f"M-{boot}-C{cycle:02d}-S0-{obj}"
            rows.append(dict(study="M", boot=boot, cycle=cycle, rule_state="S0", rule_order="none",
                             exec_order=i+1, reqid=reqid, condition=cond,
                             caller_pkg=PKG[obj[0]], caller_role=obj[0], api_entry="txn14 openFile",
                             method_label="openFile", mode="r", object=obj[1], marker=MARKERS[obj[1]],
                             expected_verdict="usable", expected_read_sha=ORACLES[obj]["sha"],
                             expected_marker_present=ORACLES[obj]["marker_present"], token="",
                             expected_write_sha="", rule_key=""))
        first, second = (("MA", "MB") if ra_first else ("MB", "MA"))
        for pos, rk in enumerate([first, second]):
            state = f"R{pos+1}"
            if rk == "MA":
                triples = [("AX", "denied"), ("BX", "usable"), ("AY", "usable")]
            else:
                triples = [("BX", "denied"), ("AX", "usable"), ("BY", "usable")]
            order = rand_state(boot, "M", cycle, state, triples)
            for i, (obj, verdict) in enumerate(order):
                cond = f"{rk.lower()}_{obj.lower()}"
                reqid = f"M-{boot}-C{cycle:02d}-{state}-{obj}"
                rows.append(dict(study="M", boot=boot, cycle=cycle, rule_state=state, rule_order=rk,
                                 exec_order=i+1, reqid=reqid, condition=cond,
                                 caller_pkg=PKG[obj[0]], caller_role=obj[0], api_entry="txn14 openFile",
                                 method_label="openFile", mode="r", object=obj[1], marker=MARKERS[obj[1]],
                                 expected_verdict=verdict, expected_read_sha=ORACLES[obj]["sha"],
                                 expected_marker_present=ORACLES[obj]["marker_present"], token="",
                                 expected_write_sha="", rule_key=rk))
        # S3 revoke
        order = rand_state(boot, "M", cycle, "S3", ["AX", "BX"])
        for i, obj in enumerate(order):
            cond = f"revoke_{obj.lower()}"
            reqid = f"M-{boot}-C{cycle:02d}-S3-{obj}"
            rows.append(dict(study="M", boot=boot, cycle=cycle, rule_state="S3", rule_order="none",
                             exec_order=i+1, reqid=reqid, condition=cond,
                             caller_pkg=PKG[obj[0]], caller_role=obj[0], api_entry="txn14 openFile",
                             method_label="openFile", mode="r", object=obj[1], marker=MARKERS[obj[1]],
                             expected_verdict="usable", expected_read_sha=ORACLES[obj]["sha"],
                             expected_marker_present=ORACLES[obj]["marker_present"], token="",
                             expected_write_sha="", rule_key=""))

# ---------------- Study L: method-label ----------------
for boot in BOOTS:
    for cycle in CYCLES:
        lw_first = (cycle % 2 == 1)
        order = rand_state(boot, "L", cycle, "S0", ["R", "W"])
        for i, req in enumerate(order):
            cond = f"no_rule_{req.lower()}"
            reqid = f"L-{boot}-C{cycle:02d}-S0-{req}"
            tok = reqid if req == "W" else ""
            rows.append(dict(study="L", boot=boot, cycle=cycle, rule_state="S0", rule_order="none",
                             exec_order=i+1, reqid=reqid, condition=cond,
                             caller_pkg=PKG["A"], caller_role="A",
                             api_entry=("txn14 openFile" if req == "R" else "txn15 openAssetFile"),
                             method_label=("openFile" if req == "R" else "openAssetFile"),
                             mode=("r" if req == "R" else "w"), object="X", marker=MARKERS["X"],
                             expected_verdict="usable",
                             expected_read_sha=ORACLES["AX"]["sha"] if req == "R" else "",
                             expected_marker_present=("true" if req == "R" else ""),
                             token=tok, expected_write_sha=(write_sha(tok) if req == "W" else ""),
                             rule_key=""))
        first, second = (("LW", "LR") if lw_first else ("LR", "LW"))
        for pos, rk in enumerate([first, second]):
            state = f"R{pos+1}"
            order = rand_state(boot, "L", cycle, state, ["R", "W"])
            for i, req in enumerate(order):
                verdict = "denied" if ((rk == "LW" and req == "W") or (rk == "LR" and req == "R")) else "usable"
                cond = f"{rk.lower()}_{req.lower()}"
                reqid = f"L-{boot}-C{cycle:02d}-{state}-{req}"
                tok = reqid if req == "W" else ""
                rows.append(dict(study="L", boot=boot, cycle=cycle, rule_state=state, rule_order=rk,
                                 exec_order=i+1, reqid=reqid, condition=cond,
                                 caller_pkg=PKG["A"], caller_role="A",
                                 api_entry=("txn14 openFile" if req == "R" else "txn15 openAssetFile"),
                                 method_label=("openFile" if req == "R" else "openAssetFile"),
                                 mode=("r" if req == "R" else "w"), object="X", marker=MARKERS["X"],
                                 expected_verdict=verdict,
                                 expected_read_sha=ORACLES["AX"]["sha"] if req == "R" else "",
                                 expected_marker_present=("true" if req == "R" else ""),
                                 token=tok, expected_write_sha=(write_sha(tok) if req == "W" else ""),
                                 rule_key=rk))
        order = rand_state(boot, "L", cycle, "S3", ["R", "W"])
        for i, req in enumerate(order):
            cond = f"revoke_{req.lower()}"
            reqid = f"L-{boot}-C{cycle:02d}-S3-{req}"
            tok = reqid if req == "W" else ""
            rows.append(dict(study="L", boot=boot, cycle=cycle, rule_state="S3", rule_order="none",
                             exec_order=i+1, reqid=reqid, condition=cond,
                             caller_pkg=PKG["A"], caller_role="A",
                             api_entry=("txn14 openFile" if req == "R" else "txn15 openAssetFile"),
                             method_label=("openFile" if req == "R" else "openAssetFile"),
                             mode=("r" if req == "R" else "w"), object="X", marker=MARKERS["X"],
                             expected_verdict="usable",
                             expected_read_sha=ORACLES["AX"]["sha"] if req == "R" else "",
                             expected_marker_present=("true" if req == "R" else ""),
                             token=tok, expected_write_sha=(write_sha(tok) if req == "W" else ""),
                             rule_key=""))

assert len(rows) == 1080, len(rows)
assert len({r["reqid"] for r in rows}) == 1080
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLUMNS)
    w.writeheader()
    for r in rows:
        w.writerow(r)
print(f"wrote {len(rows)} rows to {OUT}")
from collections import Counter
print(Counter(r["study"] for r in rows))
print(Counter(r["expected_verdict"] for r in rows))
