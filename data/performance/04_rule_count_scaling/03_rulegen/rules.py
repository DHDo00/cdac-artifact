#!/usr/bin/env python3
"""CDAC round-21 rule-count scaling: frozen rule generator + schedule.

Frozen BEFORE sampling (2026-10-26). Deterministic:
  - schedule: 4 seeded latin squares of order 5 -> 20 blocks; same for both boots.
  - rules:    target deny (A+X) first, then N-1 synthetic fillers (caller=T, deep-fail).
  - payloads: fixed 16-byte correctness payloads.

Usage:
  rules.py schedule [out_csv]
  rules.py rules N cfg.json          # print add commands for scale N
  rules.py payloads [out_json]       # expected sha256 for correctness payloads
"""
import json, random, sys, hashlib

SEED = 20261026
SCALES = [0, 1, 8, 32, 128]
TARGET_REASON = "rcs21_tgt_A_X"
FILLER_INO_BASE = 2_000_000
SYNTH_TAG = "synthetic workload (no real-business review)"
TREE = "content://com.android.externalstorage.documents/tree/primary%3Aespafd_tree"


def gen_schedule(out_csv=None):
    """4 latin squares, order 5; symbols=SCALES; seed SEED."""
    rng = random.Random(SEED)
    rows = []
    n = len(SCALES)
    for sq in range(4):
        sym = SCALES[:]
        rng.shuffle(sym)
        row_perm = list(range(n))
        col_perm = list(range(n))
        rng.shuffle(row_perm)
        rng.shuffle(col_perm)
        ls = [[sym[(r + c) % n] for c in range(n)] for r in range(n)]
        ls = [ls[i] for i in row_perm]
        ls = [[row[j] for j in col_perm] for row in ls]
        for r in range(n):
            rows.append(ls[r])
    header = "block,position,scale"
    lines = [header]
    for b, row in enumerate(rows, start=1):
        for p, s in enumerate(row, start=1):
            lines.append(f"{b},{p},{s}")
    txt = "\n".join(lines) + "\n"
    if out_csv:
        with open(out_csv, "w") as f:
            f.write(txt)
    return rows


def s_dev_raw(dev_decimal):
    return ((dev_decimal >> 8) << 20) + (dev_decimal & 255)


def target_cmd(cfg):
    return ("add service_id=5 op_id=401 caller_uid={A} operation=openAssetFile "
            "ino={X} s_dev={D} i_mode=00 f_flags_mask=0x3 f_flags_value=0x1 "
            "decision=deny reason={R}").format(
        A=cfg["A"], X=cfg["X"], D=cfg["DEVRAW"], R=TARGET_REASON)


def filler_cmd(cfg, i):
    return ("add service_id=5 op_id=401 caller_uid={T} operation=openAssetFile "
            "path_tail=X.bin ino={INO} s_dev={D} i_mode=00 "
            "decision=audit reason=rcs21_fill_{i}").format(
        T=cfg["T"], INO=FILLER_INO_BASE + i, D=cfg["DEVRAW"], i=i)


def rules_for_scale(N, cfg):
    """Return ordered list of commands: target first, then fillers 1..N-1."""
    out = []
    if N < 0:
        raise ValueError("negative N")
    if N >= 1:
        out.append(("target", target_cmd(cfg)))
    for i in range(1, N):
        out.append(("filler", filler_cmd(cfg, i)))
    return out


def payload_hashes():
    """Correctness payloads: fixed 16 bytes, unique per step. sha256 as hex."""
    out = {}
    for scale in SCALES:
        if scale == 0:
            continue
        for it in range(1, 4):
            deny = (f"DX{scale:02d}{it:02d}" + "P" * 16)[:16]
            ay = (f"AY{scale:02d}{it:02d}" + "P" * 16)[:16]
            bx = (f"BX{scale:02d}{it:02d}" + "P" * 16)[:16]
            rx = (f"RX{scale:02d}{it:02d}" + "P" * 16)[:16]
            for k, v in [("deny_A_X", deny), ("allow_A_Y", ay),
                         ("allow_B_X", bx), ("restore_A_X", rx)]:
                assert len(v.encode()) == 16, (k, v)
                out[f"{k}_{scale}_{it}"] = {
                    "payload": v,
                    "sha256": hashlib.sha256(v.encode()).hexdigest()}
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "schedule":
        gen_schedule(sys.argv[2] if len(sys.argv) > 2 else None)
        for row in gen_schedule():
            print(row)
    elif mode == "rules":
        N = int(sys.argv[2])
        cfg = json.load(open(sys.argv[3]))
        for kind, cmd in rules_for_scale(N, cfg):
            print(f"{kind}\t{cmd}")
    elif mode == "payloads":
        out = payload_hashes()
        p = sys.argv[2] if len(sys.argv) > 2 else None
        if p:
            json.dump(out, open(p, "w"), indent=1)
        print(json.dumps(out, indent=1))
    else:
        sys.exit(f"unknown mode {mode}")
