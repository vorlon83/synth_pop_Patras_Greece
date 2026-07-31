"""
=============================================================================
 MANUSCRIPT FIGURE 11  ->  img/fig_household_validation.png
=============================================================================
External validation of the synthetic household-size distribution:
    Synthetic S1 (this study)  vs  ELSTAT 2021 Western Greece reference.

This is a standalone, dependency-light regeneration of the two-series bar
chart originally in `visualize_gis.py` (its "FIG 3 - household size
distribution" block). It is kept as its own script so that the code which
produces manuscript Figure 11 lives in the repository and can be re-run
without the GIS stack (geopandas / GDAL): the household-size distribution
only needs household member counts, so we read them straight from the
canonical synthetic population JSON instead of the assigned-building geojson.

Every number on the figure is computed from real data - nothing is hard-coded
by eye:
  * Synthetic S1 shares  <- data/synthpop/patras_households.json  (the canonical
                            population; identical source used by
                            validation/compute_jsd.py)
  * Western Greece shares <- ELSTAT 2021 people-per-household counts
                            (same reference array as compute_jsd.py /
                            compute_s3_metrics.py)
  * JSD (bits)           <- Jensen-Shannon divergence, base 2, of the two
                            5-category distributions (matches compute_jsd.py)

Note on the old figure: the previous fig_household_validation.png carried a
legend value "JSD = 0.005 bits" and an arrow "27.4%" that disagreed with the
canonical computation (JSD = 0.009 bits; S1 singleton rate = 23.6%). This
script recomputes both correctly.

Reads : data/synthpop/patras_households.json
Writes: Synthetic_Population_manuscript/img/fig_household_validation.png
Run   : python figures/generate_household_size_validation.py
=============================================================================
"""

import json
import os
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")            # headless backend (no display needed)
import matplotlib.pyplot as plt
from scipy.spatial.distance import jensenshannon

# ---------------------------------------------------------------------------
# Paths (repo-root-anchored so the script runs from any working directory)
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POP_PATH = os.path.join(ROOT, "data", "synthpop", "patras_households.json")
IMG_DIR = os.path.join(ROOT, "Synthetic_Population_manuscript", "img")
OUT_PATH = os.path.join(IMG_DIR, "fig_household_validation.png")
os.makedirs(IMG_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Synthetic S1 household-size distribution (5 categories: 1,2,3,4,5+)
#    Computed directly from the canonical synthetic population.
# ---------------------------------------------------------------------------
with open(POP_PATH) as f:
    households = json.load(f)

sizes = Counter(len(hh["members"]) for hh in households)   # exact size -> count
total_hh = len(households)

# collapse into the five reporting categories used for WG validation
synth_counts = np.array(
    [sizes.get(1, 0),
     sizes.get(2, 0),
     sizes.get(3, 0),
     sizes.get(4, 0),
     sum(n for s, n in sizes.items() if s >= 5)],           # 5+ bucket
    dtype=float,
)
synth_dist = synth_counts / synth_counts.sum()              # normalised
synth_pct = synth_dist * 100

# ---------------------------------------------------------------------------
# 2. ELSTAT 2021 Western Greece reference distribution (5 categories)
#    Raw household counts (1P, 2P, 3P, 4P, 5+); identical array to the one in
#    validation/compute_jsd.py and validation/compute_s3_metrics.py.
# ---------------------------------------------------------------------------
wg_counts = np.array([82783, 70859, 44848, 37766, 21083], dtype=float)
wg_dist = wg_counts / wg_counts.sum()
wg_pct = wg_dist * 100

# ---------------------------------------------------------------------------
# 3. Effect-size metric: Jensen-Shannon divergence in bits (base-2), squared
#    so it is a true divergence (scipy returns the distance = sqrt(JSD)).
#    This reproduces the 0.009-bit value reported in the manuscript.
# ---------------------------------------------------------------------------
jsd_bits = jensenshannon(synth_dist, wg_dist, base=2) ** 2

# descriptive means (5+ bucket counted as exactly 5, a lower bound, for WG)
synth_mean = sum(s * n for s, n in sizes.items()) / total_hh
wg_mean_lb = float((wg_counts * np.array([1, 2, 3, 4, 5])).sum() / wg_counts.sum())

print(f"Synthetic households:      {total_hh:,}")
print(f"Synthetic size shares (%): {np.round(synth_pct, 2)}")
print(f"WG reference shares (%):   {np.round(wg_pct, 2)}")
print(f"JSD (bits):                {jsd_bits:.4f}")
print(f"Synthetic singleton rate:  {synth_pct[0]:.1f}%   WG singleton: {wg_pct[0]:.1f}%")

# ---------------------------------------------------------------------------
# 4. Grouped bar chart (same style as the original visualize_gis.py Fig 3:
#    blue = synthetic, orange = ELSTAT WG, per-bar % labels, dashed y-grid).
# ---------------------------------------------------------------------------
cats = ["1", "2", "3", "4", "5+"]
x = np.arange(len(cats))
w = 0.35

fig, ax = plt.subplots(figsize=(8, 5))
b1 = ax.bar(x - w / 2, synth_pct, w,
            label="Synthetic S1 (this study)", color="#2196F3", alpha=0.88)
b2 = ax.bar(x + w / 2, wg_pct, w,
            label="ELSTAT 2021 Western Greece (reference)", color="#FF7043", alpha=0.88)

# print the exact percentage above every bar
for bar in list(b1) + list(b2):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
            f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8)

ax.set_xticks(x)
ax.set_xticklabels(cats, fontsize=10)
ax.set_xlabel("Household size (number of members)", fontsize=10)
ax.set_ylabel("Share of households (%)", fontsize=10)
ax.set_title(
    "Household size distribution - Synthetic S1 vs ELSTAT Western Greece\n"
    f"N={total_hh:,} synthetic households   |   JSD = {jsd_bits:.3f} bits   |   "
    f"mean size: synthetic {synth_mean:.2f}, WG {wg_mean_lb:.2f}",
    fontsize=9,
)
ax.legend(fontsize=9)
ax.grid(axis="y", alpha=0.3, linestyle="--")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig(OUT_PATH, dpi=180, bbox_inches="tight")
plt.close()
print(f"Saved: {OUT_PATH}")
