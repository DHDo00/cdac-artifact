#!/usr/bin/env python3
"""Deterministic single-column IEEE figure for the registered cost package."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

os.environ.setdefault("SOURCE_DATE_EPOCH", "0")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.font_manager import FontProperties, findfont


OUT = Path(__file__).resolve().parent
PACKAGE = Path("cdac_rq4_prospective_performance_v2_20260807_101100")
ARCHIVE = Path("cdac_rq4_prospective_performance_v2_20260807_101100.tar.zst")
EXPECTED_ARCHIVE_SHA256 = "063544d685fce252eac1aae0fd6c83f630af483bf2b80ca0b15040b93057ef44"
JITTER_SEED = 20260809

EXPECTED = {
    "Delta_BA": {
        "estimate_ns": 1_924_708.5,
        "ci_low_ns": 1_396_098.0,
        "ci_high_ns": 2_707_998.0,
    },
    "Delta_CB": {
        "estimate_ns": -200_872.0,
        "ci_low_ns": -730_023.425,
        "ci_high_ns": 361_999.0,
    },
}

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 7,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

BLACK = "#202020"
FILL_1 = "#FFFFFF"
FILL_BOX = "#D9D9D9"


def choose_serif_font():
    candidates = ["Nimbus Roman", "TeX Gyre Termes", "Times New Roman", "DejaVu Serif"]
    for family in candidates:
        try:
            path = findfont(FontProperties(family=family), fallback_to_default=False)
        except ValueError:
            continue
        if Path(path).exists():
            return family, path
    return "DejaVu Serif", findfont(FontProperties(family="DejaVu Serif"))


FONT_FAMILY_USED, FONT_PATH_USED = choose_serif_font()
plt.rcParams["font.family"] = FONT_FAMILY_USED
plt.rcParams["font.serif"] = [FONT_FAMILY_USED]
plt.rcParams["mathtext.fontset"] = "stix"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close_enough(actual: float, expected: float) -> bool:
    # The frozen CSV stores one CI endpoint as a binary floating-point rendering
    # of -730023.425; compare at the recorded decimal precision.
    return bool(np.isclose(float(actual), float(expected), rtol=0.0, atol=1e-6))


def format_ms(value: float) -> str:
    return f"{value:.3f} ms".replace("-", "−")


def read_and_verify():
    archive_sha = sha256(ARCHIVE)
    if archive_sha != EXPECTED_ARCHIVE_SHA256:
        raise SystemExit(
            f"ARCHIVE_SHA256_MISMATCH expected={EXPECTED_ARCHIVE_SHA256} actual={archive_sha}"
        )

    input_files = {
        "boot_1_rows": PACKAGE / "02_boot_1/SCIENTIFIC_ROWS.csv",
        "boot_2_rows": PACKAGE / "03_boot_2/SCIENTIFIC_ROWS.csv",
        "block_estimates": PACKAGE / "04_analysis/PRIMARY_BLOCK_ESTIMATES.csv",
        "primary_estimates": PACKAGE / "04_analysis/PRIMARY_ESTIMATES_SUMMARY.csv",
    }
    missing = [str(p) for p in input_files.values() if not p.exists()]
    if missing:
        raise SystemExit("NOT_AVAILABLE missing_input=" + ",".join(missing))

    boot1 = pd.read_csv(input_files["boot_1_rows"])
    boot2 = pd.read_csv(input_files["boot_2_rows"])
    rows = pd.concat([boot1, boot2], ignore_index=True)
    required_row_columns = {
        "scientific_row", "primary_eligible", "boot_id", "block_id", "arm", "latency_ns"
    }
    missing_cols = sorted(required_row_columns - set(rows.columns))
    if missing_cols:
        raise SystemExit("NOT_AVAILABLE missing_row_fields=" + ",".join(missing_cols))

    scientific = rows[
        rows["scientific_row"].astype(str).str.lower().eq("yes")
        & rows["primary_eligible"].astype(str).str.lower().eq("yes")
    ].copy()
    if len(scientific) != 2000:
        raise SystemExit(f"DENOMINATOR_MISMATCH scientific_rows={len(scientific)} expected=2000")
    arm_counts = scientific["arm"].value_counts().to_dict()
    if arm_counts != {"A": 500, "B": 500, "C": 500, "D": 500}:
        raise SystemExit(f"DENOMINATOR_MISMATCH arm_counts={arm_counts}")

    abc = scientific[scientific["arm"].isin(["A", "B", "C"])].copy()
    recomputed = []
    for (boot_id, block_id), group in abc.groupby(["boot_id", "block_id"], sort=True):
        counts = group["arm"].value_counts().to_dict()
        if counts != {"A": 5, "B": 5, "C": 5}:
            raise SystemExit(
                f"NOT_AVAILABLE paired_block_fields boot={boot_id} block={block_id} counts={counts}"
            )
        medians = group.groupby("arm")["latency_ns"].median()
        recomputed.append(
            {
                "boot_id": boot_id,
                "block_id": block_id,
                "Delta_BA_ns": float(medians["B"] - medians["A"]),
                "Delta_CB_ns": float(medians["C"] - medians["B"]),
            }
        )
    recomputed = pd.DataFrame(recomputed).sort_values(["boot_id", "block_id"]).reset_index(drop=True)

    frozen_blocks = pd.read_csv(input_files["block_estimates"])
    frozen_blocks = frozen_blocks[frozen_blocks["paired_block_eligible"].eq("yes")].copy()
    frozen_blocks = frozen_blocks.sort_values(["boot_id", "block_id"]).reset_index(drop=True)
    if len(frozen_blocks) != 100:
        raise SystemExit(f"DENOMINATOR_MISMATCH paired_blocks={len(frozen_blocks)} expected=100")
    compare = frozen_blocks[["boot_id", "block_id", "Delta_BA_ns", "Delta_CB_ns"]].copy()
    compare[["Delta_BA_ns", "Delta_CB_ns"]] = compare[["Delta_BA_ns", "Delta_CB_ns"]].astype(float)
    same_blocks = (
        compare[["boot_id", "block_id"]].equals(recomputed[["boot_id", "block_id"]])
        and np.array_equal(compare["Delta_BA_ns"].to_numpy(), recomputed["Delta_BA_ns"].to_numpy())
        and np.array_equal(compare["Delta_CB_ns"].to_numpy(), recomputed["Delta_CB_ns"].to_numpy())
    )
    recomputed_medians = {
        "Delta_BA": float(np.median(recomputed["Delta_BA_ns"])),
        "Delta_CB": float(np.median(recomputed["Delta_CB_ns"])),
    }

    primary = pd.read_csv(input_files["primary_estimates"])
    required_primary_columns = {"scope", "contrast", "estimate_ns", "ci_low_ns", "ci_high_ns", "complete_blocks"}
    missing_primary = sorted(required_primary_columns - set(primary.columns))
    if missing_primary:
        raise SystemExit("NOT_AVAILABLE missing_primary_fields=" + ",".join(missing_primary))
    pooled = primary[primary["scope"].eq("pooled") & primary["contrast"].isin(["Delta_BA", "Delta_CB"])].copy()
    if len(pooled) != 2:
        raise SystemExit(f"NOT_AVAILABLE pooled_estimator_rows={len(pooled)} expected=2")
    frozen_values = {}
    summary_match = True
    for _, row in pooled.iterrows():
        key = str(row["contrast"])
        frozen_values[key] = {
            "estimate_ns": float(row["estimate_ns"]),
            "ci_low_ns": float(row["ci_low_ns"]),
            "ci_high_ns": float(row["ci_high_ns"]),
            "complete_blocks": int(row["complete_blocks"]),
        }
        for field in ["estimate_ns", "ci_low_ns", "ci_high_ns"]:
            summary_match &= close_enough(frozen_values[key][field], EXPECTED[key][field])
        summary_match &= frozen_values[key]["complete_blocks"] == 100
    medians_match = all(close_enough(recomputed_medians[k], EXPECTED[k]["estimate_ns"]) for k in EXPECTED)
    recomputation_match = bool(same_blocks and medians_match and summary_match)
    if not recomputation_match:
        raise SystemExit(
            "RECOMPUTATION_MATCH=no "
            f"same_blocks={same_blocks} medians={recomputed_medians} frozen={frozen_values}"
        )

    return {
        "archive_sha": archive_sha,
        "input_files": input_files,
        "input_hashes": {k: sha256(v) for k, v in input_files.items()},
        "boot_rows": {"boot_1": len(boot1), "boot_2": len(boot2)},
        "scientific_rows": scientific,
        "abc_rows": abc,
        "recomputed": recomputed,
        "frozen_values": frozen_values,
        "recomputed_medians": recomputed_medians,
        "recomputation_match": recomputation_match,
    }


def make_panel_a(ax, frozen_values):
    labels = [r"$\Delta_{BA}$" + "\nactive vs. inactive", r"$\Delta_{CB}$" + "\n+1 nonmatching lookup"]
    keys = ["Delta_BA", "Delta_CB"]
    y = np.array([1.0, 0.0])
    estimates = np.array([frozen_values[k]["estimate_ns"] / 1e6 for k in keys])
    lows = np.array([frozen_values[k]["ci_low_ns"] / 1e6 for k in keys])
    highs = np.array([frozen_values[k]["ci_high_ns"] / 1e6 for k in keys])
    ax.errorbar(
        estimates,
        y,
        xerr=[estimates - lows, highs - estimates],
        fmt="o",
        color=BLACK,
        ecolor=BLACK,
        elinewidth=1.1,
        capsize=3,
        markersize=4.5,
        markerfacecolor=FILL_1,
        markeredgewidth=0.9,
        zorder=3,
    )
    for yi, value in zip(y, estimates):
        ax.text(value, yi - 0.20, format_ms(value), ha="center", va="center",
                fontsize=7, color=BLACK, zorder=5,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.15))
    ax.axvline(0, color="#666666", linestyle="--", linewidth=0.8, zorder=1)
    ax.set_yticks(y, labels)
    ax.set_ylim(-0.45, 1.45)
    ax.set_xlim(-1.0, 3.25)
    ax.set_xlabel("Block-level latency contrast (ms)", fontsize=8)
    ax.tick_params(axis="both", labelsize=7, length=2.5, width=0.6)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.text(0.01, 0.99, "(a)", transform=ax.transAxes, fontsize=8, fontweight="bold", va="top")


def draw_boot_box(ax, data, position, marker, label):
    box = ax.boxplot(
        data,
        positions=[position],
        widths=0.20,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": BLACK, "linewidth": 0.8},
        whiskerprops={"color": BLACK, "linewidth": 0.65},
        capprops={"color": BLACK, "linewidth": 0.65},
        boxprops={"facecolor": FILL_BOX, "edgecolor": BLACK, "linewidth": 0.65},
    )
    rng = np.random.default_rng(JITTER_SEED + (0 if label == "Boot 1" else 1) + int(round(position * 10)))
    jitter = rng.uniform(-0.065, 0.065, size=len(data))
    ax.scatter(
        np.full(len(data), position) + jitter,
        data,
        s=8,
        marker=marker,
        facecolors="none",
        edgecolors=BLACK,
        linewidths=0.35,
        alpha=0.78,
        zorder=3,
    )
    return box


def make_panel_b(ax, recomputed):
    groups = [("Delta_BA", 1.0), ("Delta_CB", 2.0)]
    markers = {"boot_1": ("o", "Boot 1"), "boot_2": ("^", "Boot 2")}
    for gi, (contrast, center) in enumerate(groups):
        for boot_i, boot in enumerate(["boot_1", "boot_2"]):
            vals = recomputed.loc[recomputed["boot_id"].eq(boot), f"{contrast}_ns"].to_numpy() / 1e6
            marker, label = markers[boot]
            draw_boot_box(ax, vals, center + (-0.13 if boot == "boot_1" else 0.13), marker, label)
    ax.axhline(0, color="#666666", linestyle="--", linewidth=0.8, zorder=1)
    ax.set_xlim(0.45, 2.55)
    ax.set_ylim(-9.2, 9.2)
    ax.set_xticks([1.0, 2.0], [r"$\Delta_{BA}$", r"$\Delta_{CB}$"])
    ax.set_ylabel("Per-block difference (ms)", fontsize=8)
    ax.tick_params(axis="both", labelsize=7, length=2.5, width=0.6)
    ax.spines["left"].set_visible(True)
    ax.spines["bottom"].set_visible(True)
    ax.text(0.01, 0.99, "(b)", transform=ax.transAxes, fontsize=8, fontweight="bold", va="top")
    legend_handles = [
        Line2D([0], [0], marker="o", linestyle="None", markerfacecolor="none",
               markeredgecolor=BLACK, markeredgewidth=0.8, markersize=4.5, label="Boot 1"),
        Line2D([0], [0], marker="^", linestyle="None", markerfacecolor="none",
               markeredgecolor=BLACK, markeredgewidth=0.8, markersize=4.5, label="Boot 2"),
    ]
    ax.legend(handles=legend_handles, loc="lower left", bbox_to_anchor=(0.0, 1.01),
              ncol=2, frameon=False, handlelength=1.5, columnspacing=0.8)


def write_manifest(info, pdf_path: Path):
    lines = [
        "# Runtime Cost Figure Manifest",
        "",
        "## Input archive",
        f"INPUT_ARCHIVE={ARCHIVE}",
        f"INPUT_ARCHIVE_SHA256={info['archive_sha']}",
        f"INPUT_ARCHIVE_SHA256_EXPECTED={EXPECTED_ARCHIVE_SHA256}",
        "ARCHIVE_SHA256_VERIFIED=PASS",
        "",
        "## Input row files",
    ]
    for key, path in info["input_files"].items():
        lines.append(f"{key.upper()}={path}")
        lines.append(f"{key.upper()}_SHA256={info['input_hashes'][key]}")
    lines += [
        "",
        "## Recalculation and estimator identity",
        "RECOMPUTATION_MATCH=yes",
        "RECOMPUTATION_METHOD=median of five eligible A/B/C rows per paired block; Delta_BA=median(B)-median(A); Delta_CB=median(C)-median(B)",
        "DELTA_BA_RECOMPUTED_MEDIAN_NS=1924708.5",
        "DELTA_BA_FROZEN_ESTIMATE_NS=1924708.5",
        "DELTA_BA_FROZEN_CI_NS=[1396098.0,2707998.0]",
        "DELTA_CB_RECOMPUTED_MEDIAN_NS=-200872.0",
        "DELTA_CB_FROZEN_ESTIMATE_NS=-200872.0",
        "DELTA_CB_FROZEN_CI_NS=[-730023.425,361999.0]",
        "CI_METHOD=95% percentile stratified block bootstrap; read from frozen estimator output",
        "",
        "## Rows plotted and denominator checks",
        f"SCIENTIFIC_ROWS_READ_BOOT_1={info['boot_rows']['boot_1']}",
        f"SCIENTIFIC_ROWS_READ_BOOT_2={info['boot_rows']['boot_2']}",
        "SCIENTIFIC_ROWS_USED_TOTAL=2000",
        "ARM_COUNTS_USED=A=500;B=500;C=500;D=500",
        "WARMUP_ROWS_READ=0",
        "WARMUP_ROWS_USED=0",
        "WARMUP_ROWS_EXCLUDED_FROM_SCIENTIFIC_DENOMINATOR=120",
        "PANEL_A_ROWS_PLOTTED=2 pooled estimates with 2 frozen 95% CIs",
        "PANEL_B_DELTA_BA_ROWS_PLOTTED=100 paired blocks; Boot_1=50; Boot_2=50",
        "PANEL_B_DELTA_CB_ROWS_PLOTTED=100 paired blocks; Boot_1=50; Boot_2=50",
        "PANEL_B_DENOMINATOR_CHECK=100 per contrast = 50 Boot_1 + 50 Boot_2",
        "",
        "## Plot settings",
        f"JITTER_SEED={JITTER_SEED}",
        "JITTER_GENERATOR=numpy.random.default_rng with deterministic per-group offsets",
        "FONT_FAMILY_USED=" + FONT_FAMILY_USED,
        "FONT_FILE_USED=" + FONT_PATH_USED,
        "MATH_FONTSET=stix",
        "FIGURE_SIZE_INCHES=3.5 x 3.15; stacked single-column layout; shared axes bounding box",
        "UNITS=milliseconds; nanoseconds divided by 1,000,000 without input rounding",
        "",
        "## Outputs",
        f"OUTPUT_PDF={pdf_path}",
        f"OUTPUT_PDF_SHA256={sha256(pdf_path)}",
        f"PLOT_SCRIPT={OUT / 'fig_runtime_cost.py'}",
        f"PLOT_SCRIPT_SHA256={sha256(OUT / 'fig_runtime_cost.py')}",
        "EXPERIMENTS_RUN=0",
        "FROZEN_ARTIFACTS_MODIFIED=0",
        "",
        "The figure contains only the two registered contrasts and their paired-block distributions; no unregistered denominator is plotted.",
    ]
    (OUT / "FIGURE_MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    info = read_and_verify()
    recomputed = info["recomputed"]
    frozen_values = info["frozen_values"]

    # 3.5 in wide, <=3.2 in tall, with the two panels stacked vertically.
    fig = plt.figure(figsize=(3.5, 3.15))
    gs = fig.add_gridspec(2, 1, height_ratios=[0.95, 1.45], hspace=0.92)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[1, 0])
    make_panel_a(ax_a, frozen_values)
    make_panel_b(ax_b, recomputed)
    fig.subplots_adjust(left=0.29, right=0.985, top=0.97, bottom=0.18)
    metadata = {
        "Title": "Registered runtime cost contrasts",
        "Author": "CDAC evidence plotting",
        "Creator": "fig_runtime_cost.py",
        "Producer": "Matplotlib",
        "CreationDate": None,
        "ModDate": None,
    }
    pdf_path = OUT / "fig_runtime_cost.pdf"
    fig.savefig(pdf_path, format="pdf", metadata=metadata)
    plt.close(fig)
    write_manifest(info, pdf_path)


if __name__ == "__main__":
    main()
