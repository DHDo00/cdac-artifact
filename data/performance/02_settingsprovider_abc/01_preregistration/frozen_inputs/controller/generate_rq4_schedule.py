#!/usr/bin/env python3
"""Generate the byte-stable, from-zero RQ4 V2 schedules."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONSTANTS = json.loads((HERE.parent / "schemas" / "rq4_constants.json").read_text(encoding="utf-8"))


MEASURED_FIELDS = [
    "global_schedule_position", "boot_id", "boot_schedule_position", "stage",
    "block_id", "block_index", "randomized_position", "arm", "trial_index",
    "trial_id", "schedule_seed", "derived_seed",
]
WARMUP_FIELDS = [
    "boot_id", "warmup_position", "warmup_cycle", "randomized_position",
    "arm", "arm_warmup_index", "trial_id", "schedule_seed", "derived_seed",
]


def measured_rows() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    global_position = 0
    seed = int(CONSTANTS["schedule_seed_v2"])
    for boot_number in (1, 2):
        boot_id = f"boot_{boot_number}"
        derived = seed + boot_number * 1_000_003
        rng = random.Random(derived)
        boot_position = 0
        for block_index in range(1, int(CONSTANTS["abc_blocks_per_boot"]) + 1):
            order = ["A", "B", "C"]
            rng.shuffle(order)
            block_id = f"B{boot_number}-ABC-{block_index:03d}"
            for randomized_position, arm in enumerate(order, start=1):
                for trial_index in range(1, int(CONSTANTS["trials_per_arm_per_block"]) + 1):
                    global_position += 1
                    boot_position += 1
                    result.append({
                        "global_schedule_position": global_position,
                        "boot_id": boot_id,
                        "boot_schedule_position": boot_position,
                        "stage": "ALLOW_PATH",
                        "block_id": block_id,
                        "block_index": block_index,
                        "randomized_position": randomized_position,
                        "arm": arm,
                        "trial_index": trial_index,
                        "trial_id": f"RQ4V2-B{boot_number}-ABC-{block_index:03d}-P{randomized_position}-{arm}-{trial_index:02d}",
                        "schedule_seed": seed,
                        "derived_seed": derived,
                    })
        for block_index in range(1, int(CONSTANTS["denial_blocks_per_boot"]) + 1):
            block_id = f"B{boot_number}-D-{block_index:03d}"
            for trial_index in range(1, int(CONSTANTS["denial_trials_per_block"]) + 1):
                global_position += 1
                boot_position += 1
                result.append({
                    "global_schedule_position": global_position,
                    "boot_id": boot_id,
                    "boot_schedule_position": boot_position,
                    "stage": "ABSOLUTE_DENIAL_LATENCY",
                    "block_id": block_id,
                    "block_index": block_index,
                    "randomized_position": 1,
                    "arm": "D",
                    "trial_index": trial_index,
                    "trial_id": f"RQ4V2-B{boot_number}-D-{block_index:03d}-{trial_index:02d}",
                    "schedule_seed": seed,
                    "derived_seed": derived,
                })
    return result


def warmup_rows() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seed = int(CONSTANTS["schedule_seed_v2"])
    for boot_number in (1, 2):
        boot_id = f"boot_{boot_number}"
        derived = seed + 5_000_009 + boot_number * 1_000_003
        rng = random.Random(derived)
        arm_counts = {"A": 0, "B": 0, "C": 0}
        position = 0
        for cycle in range(1, int(CONSTANTS["warmup_cycles_per_boot"]) + 1):
            order = ["A", "B", "C"]
            rng.shuffle(order)
            for randomized_position, arm in enumerate(order, start=1):
                position += 1
                arm_counts[arm] += 1
                result.append({
                    "boot_id": boot_id,
                    "warmup_position": position,
                    "warmup_cycle": cycle,
                    "randomized_position": randomized_position,
                    "arm": arm,
                    "arm_warmup_index": arm_counts[arm],
                    "trial_id": f"RQ4V2-WARMUP-B{boot_number}-C{cycle:02d}-P{randomized_position}-{arm}",
                    "schedule_seed": seed,
                    "derived_seed": derived,
                })
    return result


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def validate(measured: list[dict[str, object]], warmups: list[dict[str, object]]) -> None:
    if len(measured) != 2000:
        raise RuntimeError(f"measured schedule has {len(measured)} rows")
    if len(warmups) != 120:
        raise RuntimeError(f"warm-up schedule has {len(warmups)} rows")
    for arm in "ABCD":
        if sum(row["arm"] == arm for row in measured) != 500:
            raise RuntimeError(f"arm {arm} measured denominator mismatch")
    for boot_id in ("boot_1", "boot_2"):
        selected = [row for row in measured if row["boot_id"] == boot_id]
        if len(selected) != 1000:
            raise RuntimeError(f"{boot_id} measured denominator mismatch")
        warm = [row for row in warmups if row["boot_id"] == boot_id]
        if len(warm) != 60:
            raise RuntimeError(f"{boot_id} warm-up denominator mismatch")
        for arm in "ABC":
            if sum(row["arm"] == arm for row in warm) != 20:
                raise RuntimeError(f"{boot_id} arm {arm} warm-up mismatch")
    positions = [int(row["global_schedule_position"]) for row in measured]
    if positions != list(range(1, 2001)):
        raise RuntimeError("global schedule positions are not contiguous")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("measured", type=Path)
    parser.add_argument("warmup", type=Path)
    args = parser.parse_args()
    measured = measured_rows()
    warmups = warmup_rows()
    validate(measured, warmups)
    write_csv(args.measured, MEASURED_FIELDS, measured)
    write_csv(args.warmup, WARMUP_FIELDS, warmups)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
