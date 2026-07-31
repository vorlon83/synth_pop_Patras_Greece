# === FIGURE GENERATOR ===
# Generates (manuscript figures): img/fig_flowchart.png
# Run from repo root: python figures/generate_flowchart.py
# ============================================================
"""
Generate a reproduction flowchart for the manuscript pipeline.
Output: Synthetic_Population_manuscript/img/fig_flowchart.png
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, 'Synthetic_Population_manuscript', 'img', 'fig_flowchart.png')

# ── colour palette ────────────────────────────────────────────────────────────
C_SYNTH  = '#2563EB'   # blue   — synthesis / population steps
C_GIS    = '#16A34A'   # green  — GIS step
C_ABM    = '#DC2626'   # red    — ABM steps
C_FIG    = '#7C3AED'   # purple — figure generation
C_PDF    = '#B45309'   # amber  — manuscript output
C_ARROW  = '#374151'
C_BG     = '#F9FAFB'
C_TEXT   = '#111827'
C_SUB    = '#6B7280'   # grey   — subtext

ALPHA_BOX = 0.13

fig, ax = plt.subplots(figsize=(13, 21))
ax.set_xlim(0, 11)
ax.set_ylim(0, 18)
ax.axis('off')
fig.patch.set_facecolor('white')

# ── helper: rounded box ────────────────────────────────────────────────────────
def box(ax, x, y, w, h, color, label, sublabel='', tag='', time=''):
    pad = 0.18
    rect = FancyBboxPatch(
        (x - w/2, y - h/2), w, h,
        boxstyle='round,pad=0.12',
        facecolor=color, alpha=ALPHA_BOX,
        edgecolor=color, linewidth=2.2,
        zorder=3
    )
    ax.add_patch(rect)

    # step tag (top-left bubble)
    if tag:
        ax.text(x - w/2 + 0.22, y + h/2 - 0.22, tag,
                ha='center', va='center', fontsize=12, fontweight='bold',
                color='white', zorder=5,
                bbox=dict(boxstyle='circle,pad=0.18', facecolor=color,
                          edgecolor='none', zorder=4))

    # main label
    ax.text(x, y + (0.12 if sublabel else 0), label,
            ha='center', va='center', fontsize=14, fontweight='bold',
            color=color, zorder=5, wrap=True)

    # sublabel (script path)
    if sublabel:
        ax.text(x, y - 0.28, sublabel,
                ha='center', va='center', fontsize=11,
                color=C_SUB, zorder=5,
                fontstyle='italic')

    # time badge (right side)
    if time:
        ax.text(x + w/2 - 0.12, y,
                time, ha='right', va='center', fontsize=11,
                color=color, fontweight='bold', zorder=5)

def arrow(ax, x1, y1, x2, y2, label=''):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=C_ARROW,
                                lw=2.0, connectionstyle='arc3,rad=0.0'))
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.15, my, label, fontsize=11, color=C_SUB,
                va='center', ha='left')

def output_chip(ax, x, y, text, color):
    ax.text(x, y, f'→ {text}',
            ha='center', va='center', fontsize=11, color=color,
            bbox=dict(boxstyle='round,pad=0.22', facecolor=color,
                      alpha=0.08, edgecolor=color, linewidth=1.2))

# ── layout constants ──────────────────────────────────────────────────────────
CX  = 5.5     # centre x
BW  = 8.8     # box width
BH  = 0.90    # box height
GAP = 1.55    # vertical gap between box centres

ys = [16.8, 15.2, 13.6, 12.0, 10.4, 8.8, 7.2, 5.3, 3.0, 1.3]
#      1      2     3     4     5     6    7   8a/8b  9  (label row)

# ── title ─────────────────────────────────────────────────────────────────────
ax.text(CX, 17.55, 'Reproduction Pipeline',
        ha='center', va='center', fontsize=20, fontweight='bold', color=C_TEXT)
ax.text(CX, 17.18, 'Run steps 1–9 in order to regenerate all manuscript numbers, figures, and PDF.',
        ha='center', va='center', fontsize=12, color=C_SUB)

# ── step boxes ────────────────────────────────────────────────────────────────
# 1
box(ax, CX, ys[0], BW, BH, C_SYNTH,
    'IPF Synthesis — Achaia household population',
    'Thesis_Synthpop-main/python_ipf/main_ipf_pipeline.py',
    tag='1', time='~5 min')
output_chip(ax, CX, ys[0] - 0.62, '119,070 HH  /  306,021 individuals', C_SYNTH)

# 2
box(ax, CX, ys[1], BW, BH, C_SYNTH,
    'Filter to Patras municipality',
    'filter_patras.py',
    tag='2', time='< 1 min')
output_chip(ax, CX, ys[1] - 0.62, '82,507 HH  /  215,927 individuals', C_SYNTH)

# 3
box(ax, CX, ys[2], BW, BH, C_SYNTH,
    'Validate population',
    'validation/verify_population.py',
    tag='3', time='< 1 min')
output_chip(ax, CX, ys[2] - 0.62, 'max marginal error ≤ 0.01 pp  ·  band-14 solo rate 13.5%', C_SYNTH)

# 4
box(ax, CX, ys[3], BW, BH, C_GIS,
    'GIS spatial assignment',
    'pipeline.ipynb  (Stages 1–10)',
    tag='4', time='15–30 min')
output_chip(ax, CX, ys[3] - 0.62, '84.4% placed  ·  100% district fill  ·  32,734 buildings used', C_GIS)

# 5
box(ax, CX, ys[4], BW, BH, C_SYNTH,
    'Build agent CSV',
    'abm-patras-greece-main/build_agents.py',
    tag='5', time='~1 min')
output_chip(ax, CX, ys[4] - 0.62, 'agents_patras.csv  (215,927 rows)', C_SYNTH)

# 6
box(ax, CX, ys[5], BW, BH, C_ABM,
    'ABM sensitivity sweep  (4 SAR × 50 seeds × 2 scenarios)',
    'abm-patras-greece-main/full_sweep_50rep.py',
    tag='6', time='~2 hours')
output_chip(ax, CX, ys[5] - 0.62, 'full_sweep_50rep_summary/perrun/curves.csv  ·  n=50 at all SAR levels', C_ABM)

# 7
box(ax, CX, ys[6], BW, BH, C_ABM,
    'Conditional statistics  &  Wilcoxon tests',
    'validation/abm_conditional_stats.py',
    tag='7', time='< 1 min')
output_chip(ax, CX, ys[6] - 0.62, 'p < 10⁻⁴ at all SAR levels', C_ABM)

# ── split: 8a and 8b ──────────────────────────────────────────────────────────
X8a = 3.0
X8b = 8.0
BW2 = 4.0

y8 = 5.3

box(ax, X8a, y8, BW2, BH, C_FIG,
    'Main figures  (reads CSVs)',
    'figures/generate_abm_figures.py',
    tag='8a', time='< 1 min')
output_chip(ax, X8a, y8 - 0.62, '4 PNG figures', C_FIG)

box(ax, X8b, y8, BW2, BH, C_FIG,
    'Fan curves  (re-runs ABM)',
    'figures/generate_fan_curves.py',
    tag='8b', time='~25 min')
output_chip(ax, X8b, y8 - 0.62, 'fig_fan_curves.png', C_FIG)

# branch label
ax.text(CX, (ys[6] - 0.62 + y8 + BH/2) / 2 + 0.1,
        'run in parallel or sequentially',
        ha='center', va='center', fontsize=11, color=C_SUB, fontstyle='italic')

# 9
box(ax, CX, ys[9], BW, BH, C_PDF,
    'Compile manuscript PDF',
    'Synthetic_Population_manuscript/  →  pdflatex main.tex  (×2)',
    tag='9', time='~1 min')
output_chip(ax, CX, ys[9] - 0.62, 'main.pdf  ·  45 pages', C_PDF)

# ── arrows ────────────────────────────────────────────────────────────────────
def va(y_top, y_bot):
    arrow(ax, CX, y_top - BH/2 - 0.62, CX, y_bot + BH/2)

va(ys[0], ys[1])
va(ys[1], ys[2])
va(ys[2], ys[3])
va(ys[3], ys[4])
va(ys[4], ys[5])
va(ys[5], ys[6])

# step 7 → split into 8a and 8b
y7_bot = ys[6] - BH/2 - 0.62
# fork point
fork_y = (y7_bot + y8 + BH/2) / 2
ax.plot([CX, CX], [y7_bot, fork_y], color=C_ARROW, lw=2.0)
ax.plot([CX, X8a], [fork_y, fork_y], color=C_ARROW, lw=2.0)
ax.plot([CX, X8b], [fork_y, fork_y], color=C_ARROW, lw=2.0)
ax.annotate('', xy=(X8a, y8 + BH/2), xytext=(X8a, fork_y),
            arrowprops=dict(arrowstyle='->', color=C_ARROW, lw=2.0))
ax.annotate('', xy=(X8b, y8 + BH/2), xytext=(X8b, fork_y),
            arrowprops=dict(arrowstyle='->', color=C_ARROW, lw=2.0))

# merge 8a and 8b → 9
merge_y = (y8 - BH/2 - 0.62 + ys[9] + BH/2) / 2
ax.plot([X8a, X8a], [y8 - BH/2 - 0.62, merge_y], color=C_ARROW, lw=2.0)
ax.plot([X8b, X8b], [y8 - BH/2 - 0.62, merge_y], color=C_ARROW, lw=2.0)
ax.plot([X8a, X8b], [merge_y, merge_y], color=C_ARROW, lw=2.0)
ax.plot([CX, CX], [merge_y, merge_y], color=C_ARROW, lw=2.0)
ax.annotate('', xy=(CX, ys[9] + BH/2), xytext=(CX, merge_y),
            arrowprops=dict(arrowstyle='->', color=C_ARROW, lw=2.0))

# ── legend ────────────────────────────────────────────────────────────────────
legend_items = [
    mpatches.Patch(facecolor=C_SYNTH, alpha=0.7, label='Population synthesis'),
    mpatches.Patch(facecolor=C_GIS,   alpha=0.7, label='GIS assignment'),
    mpatches.Patch(facecolor=C_ABM,   alpha=0.7, label='ABM simulation'),
    mpatches.Patch(facecolor=C_FIG,   alpha=0.7, label='Figure generation'),
    mpatches.Patch(facecolor=C_PDF,   alpha=0.7, label='Manuscript output'),
]
ax.legend(handles=legend_items, loc='lower right',
          bbox_to_anchor=(1.0, 0.0),
          fontsize=11, framealpha=0.9, edgecolor='#D1D5DB',
          title='Step type', title_fontsize=11)

plt.tight_layout()
plt.savefig(OUT, dpi=250, bbox_inches='tight', facecolor='white')
print(f'Saved: {OUT}')
plt.close()
