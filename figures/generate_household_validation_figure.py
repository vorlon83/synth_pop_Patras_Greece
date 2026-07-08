"""
Regenerate Synthetic_Population_manuscript/img/fig_household_validation.png.

The previously committed PNG was stale (wrong JSD/singleton numbers baked into
the legend text) and had a rendering bug: a second, garbled text box overlapping
the legend. This script recomputes both scenarios from actual data and renders
a clean grouped bar chart.

Data sources (no fabricated numbers):
  - WG reference (Western Greece 2021, ELSTAT, 5-category household-size
    distribution): [32.2, 28.9, 17.4, 14.7, 6.8] -- the same reference values
    already used in figures/visualize_gis.py's fig3_hh_size_distribution.png
    generator, reused here verbatim (see manuscript main.tex for citation).
  - S1 (canonical default, Italian templates as-is): computed live from
    data/synthpop/patras_households.json (82,507 households) -- the exact
    file the manuscript's synthetic population figures are built from.
    Cross-check: singleton share must equal 19,494 / 82,507 = 23.6%.
  - S3 (sensitivity scenario, WG-reweighted templates): computed live from
    data/synthpop/patras_households_s3.json (92,261 households). This file
    was produced by running Thesis_Synthpop-main/python_ipf/main_ipf_pipeline.py
    with TEMPLATE_FILE=household_compositions_s3.json (the WG-reweighted
    template library written by reweight_s3.py) and PIPELINE_SEED=42, i.e. the
    same pipeline/method validation/compute_s3_metrics.py expects, then
    filtering location_id==2423701 (Patras) exactly as that script does.

JSD is computed the same way as validation/compute_s3_metrics.py (Jensen-
Shannon divergence in bits, log base 2).

Run from the repository root:
    python figures/generate_household_validation_figure.py
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.special import rel_entr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S1_PATH = os.path.join(ROOT, "data", "synthpop", "patras_households.json")
S3_PATH = os.path.join(ROOT, "data", "synthpop", "patras_households_s3.json")
OUT_PATH = os.path.join(ROOT, "Synthetic_Population_manuscript", "img", "fig_household_validation.png")

CATS = ["1", "2", "3", "4", "5+"]

# WG 2021 five-category reference distribution (Western Greece, ELSTAT) --
# same values already used in figures/visualize_gis.py (fig3 generator).
WG_PCT = np.array([32.2, 28.9, 17.4, 14.7, 6.8])


def size_distribution_pct(path):
    with open(path) as f:
        households = json.load(f)
    sizes = np.array([len(h["members"]) for h in households])
    total = len(sizes)
    counts = np.array([
        (sizes == 1).sum(),
        (sizes == 2).sum(),
        (sizes == 3).sum(),
        (sizes == 4).sum(),
        (sizes >= 5).sum(),
    ])
    assert counts.sum() == total
    return counts, counts / total * 100.0


def jsd_bits(p, q):
    p = np.asarray(p, dtype=float); p = p / p.sum()
    q = np.asarray(q, dtype=float); q = q / q.sum()
    m = 0.5 * (p + q)
    j_nats = 0.5 * rel_entr(p, m).sum() + 0.5 * rel_entr(q, m).sum()
    return j_nats / np.log(2)


print(f"Loading S1 households from {S1_PATH} ...")
s1_counts, s1_pct = size_distribution_pct(S1_PATH)
s1_total = s1_counts.sum()
s1_singleton_pct = s1_pct[0]
print(f"  S1: N={s1_total:,} households; size-1..5+ %: {np.round(s1_pct, 2)}")
# Cross-check against the known canonical S1 singleton figure (19,494 / 82,507).
assert s1_total == 82507, f"unexpected S1 household count: {s1_total}"
assert s1_counts[0] == 19494, f"unexpected S1 singleton count: {s1_counts[0]}"
assert abs(s1_singleton_pct - 23.6) < 0.1, f"S1 singleton % drifted: {s1_singleton_pct:.2f}"

print(f"Loading S3 households from {S3_PATH} ...")
s3_counts, s3_pct = size_distribution_pct(S3_PATH)
s3_total = s3_counts.sum()
s3_singleton_pct = s3_pct[0]
print(f"  S3: N={s3_total:,} households; size-1..5+ %: {np.round(s3_pct, 2)}")

jsd_s1 = jsd_bits(s1_pct, WG_PCT)
jsd_s3 = jsd_bits(s3_pct, WG_PCT)
print(f"JSD(S1 vs WG) = {jsd_s1:.6f} bits  (manuscript: 0.009 bits)")
print(f"JSD(S3 vs WG) = {jsd_s3:.6f} bits  (manuscript: 0.001 bits)")
print(f"S1 singleton = {s1_singleton_pct:.2f}%  (manuscript: 23.6%)")
print(f"S3 singleton = {s3_singleton_pct:.2f}%  (manuscript: 33.3%)")
print(f"WG singleton = {WG_PCT[0]:.1f}%")

# ── Plot ──────────────────────────────────────────────────────────────────────
# Categorical colors kept consistent with the paper's existing house style
# (figures/visualize_gis.py fig3: WG = orange, S1 = blue); S3 gets a third,
# CVD-distinct hue (aqua/green) rather than a re-cycled one.
COLOR_WG = "#FF7043"
COLOR_S1 = "#2196F3"
COLOR_S3 = "#1baf7a"

x = np.arange(len(CATS))
w = 0.26

fig, ax = plt.subplots(figsize=(9, 6))

b_wg = ax.bar(x - w, WG_PCT, w,
              label="Western Greece (ELSTAT 2021, reference)",
              color=COLOR_WG, alpha=0.9, edgecolor="white", linewidth=0.4)
b_s1 = ax.bar(x, s1_pct, w,
              label=f"Synthetic S1 (JSD = {jsd_s1:.3f} bits)",
              color=COLOR_S1, alpha=0.9, edgecolor="white", linewidth=0.4)
b_s3 = ax.bar(x + w, s3_pct, w,
              label=f"Synthetic S3, WG-reweighted (JSD = {jsd_s3:.3f} bits)",
              color=COLOR_S3, alpha=0.9, edgecolor="white", linewidth=0.4)

for bars in (b_wg, b_s1, b_s3):
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4,
                 f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=7.5)

ax.set_xticks(x)
ax.set_xticklabels(CATS, fontsize=10)
ax.set_xlabel("Household size (number of members)", fontsize=10)
ax.set_ylabel("Share of households (%)", fontsize=10)
y_max = max(WG_PCT.max(), s1_pct.max(), s3_pct.max())
ax.set_ylim(0, y_max * 1.38)
ax.set_title(
    "Household-size distribution validation\n"
    "S1 (Italian templates) vs S3 (WG-reweighted) vs Western Greece observed",
    fontsize=12, fontweight="bold", pad=14)

ax.legend(fontsize=9, loc="upper right", framealpha=0.95,
          facecolor="white", edgecolor="#aaaaaa")
ax.grid(axis="y", alpha=0.3, linestyle="--")
ax.spines[["top", "right"]].set_visible(False)
ax.set_xlim(-0.6, len(CATS) - 1 + 0.6)

# Singleton-gap annotation (S1 vs WG only, per manuscript framing) -- anchored
# in the top-left quadrant (legend occupies the top-right), well clear of both
# the title (above the axes) and the legend box.
ax.annotate(
    f"Singleton gap:\nS1 {s1_singleton_pct:.1f}% vs WG {WG_PCT[0]:.1f}%",
    xy=(-0.13, WG_PCT[0] + 1.2),
    xytext=(-0.5, y_max * 1.24),
    fontsize=9, color="#555555", ha="left", va="top",
    arrowprops=dict(arrowstyle="-|>", color="#777777", lw=1.1,
                     connectionstyle="arc3,rad=0.1"),
)

plt.tight_layout()
plt.savefig(OUT_PATH, dpi=200, facecolor="white", bbox_inches="tight")
plt.close()
print(f"Saved {OUT_PATH}")
