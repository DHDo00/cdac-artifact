#!/usr/bin/env python3
"""Charts for round-21 rule-count scaling."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WS = Path(__file__).resolve().parents[1]
OUT = WS / "07_analysis"
A = json.loads((OUT / "analysis.json").read_text())
SCALES = [0, 1, 8, 32, 128]
NONZERO = [1, 8, 32, 128]

# Fig 1: per-scale median +/- P95 whiskers, both boots
fig, ax = plt.subplots(figsize=(9, 5))
for bi, color in (("1", "tab:blue"), ("2", "tab:orange")):
    med, lo, hi = [], [], []
    for s in SCALES:
        p = A[f"boot{bi}"]["per_scale"][str(s)]
        med.append(p["median"] / 1e6)
        lo.append(p["median"] / 1e6)   # bottom of bar at median
        hi.append(p["p95"] / 1e6)
    x = list(range(len(SCALES)))
    off = -0.18 if bi == "1" else 0.18
    ax.bar([v + off for v in x], med, width=0.3, color=color,
           label=f"boot{bi} median")
    for v, m, h in zip(x, med, hi):
        ax.plot([v + off, v + off], [m, h], color="black", lw=1)
        ax.plot([v + off - 0.05, v + off + 0.05], [h, h], color="black", lw=1)
ax.set_xticks(range(len(SCALES)))
ax.set_xticklabels([f"N={s}" for s in SCALES])
ax.set_ylabel("end-to-end open_ns (ms)")
ax.set_title("round-21: T->X allow latency vs active rule count "
             "(median, P95 whisker; LOG_OFF)")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig1_scale_median_p95.png", dpi=150)
fig.savefig(OUT / "fig1_scale_median_p95.pdf")
plt.close(fig)

# Fig 2: paired per-block diffs T(N)-T(0), both boots
fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
for ax, bi in zip(axes, ("1", "2")):
    data = []
    labels = []
    for s in NONZERO:
        d = A[f"boot{bi}"]["paired"][str(s)]["diffs"]
        data.append([v / 1e6 for v in d])
        labels.append(f"N={s}")
    bp = ax.boxplot(data, labels=labels, showfliers=True, widths=0.6)
    ax.axhline(0, color="red", lw=0.8, ls="--")
    ax.set_title(f"boot{bi}: per-block T(N)-T(0), median diff (ms)")
    ax.set_xlabel("active rule count N")
    ax.set_ylabel("T(N)-T(0) ms")
    ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "fig2_paired_block_diffs.png", dpi=150)
fig.savefig(OUT / "fig2_paired_block_diffs.pdf")
plt.close(fig)
print("plots written")
