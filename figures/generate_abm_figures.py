# === FIGURE GENERATOR ===
# Generates (manuscript figures): img/fig_epidemic_curves.png, fig_peak_comparison.png, fig_ar_violin.png, fig_inactive_gap.png
# Run from repo root: python figures/generate_abm_figures.py
# ============================================================
"""
Regenerate ABM epidemic-curve, peak-comparison, and inactive-gap figures from
sweep output CSVs. Also archives a timestamped copy of all three sweep CSVs to
data/abm_results/ for long-term reference (never overwritten by future sweeps).
"""
import os
import shutil
import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURVES_CSV  = os.path.join(ROOT, 'abm-patras-greece-main', 'full_sweep_50rep_curves.csv')
PERRUN_CSV  = os.path.join(ROOT, 'abm-patras-greece-main', 'full_sweep_50rep_perrun.csv')
OUT_CURVES  = os.path.join(ROOT, 'Synthetic_Population_manuscript', 'img', 'fig_epidemic_curves.png')
OUT_PEAK    = os.path.join(ROOT, 'Synthetic_Population_manuscript', 'img', 'fig_peak_comparison.png')
OUT_INACT   = os.path.join(ROOT, 'Synthetic_Population_manuscript', 'img', 'fig_inactive_gap.png')
OUT_VIOLIN  = os.path.join(ROOT, 'Synthetic_Population_manuscript', 'img', 'fig_ar_violin.png')

SARS = [15, 20, 25, 30]
EXTINCTION_THRESHOLD = 0.01  # exclude R replicates with AR < 1%

curves = pd.read_csv(CURVES_CSV)
perrun = pd.read_csv(PERRUN_CSV)

# ── Epidemic curves figure ────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 4, figsize=(16, 4), sharey=False)
steps = curves['step'].values

for ax, sar in zip(axes, SARS):
    r_col = f'R_SAR{sar}'
    u_col = f'U_SAR{sar}'
    r_curve = curves[r_col].values
    u_curve = curves[u_col].values

    ax.plot(steps, r_curve, color='#1f77b4', lw=2, label='Scenario R')
    ax.plot(steps, u_curve, color='#d62728', lw=2, linestyle='--', label='Scenario U')

    # Peak delay annotation for SAR=20% panel: compute from conditional per-run stats
    if sar == 20:
        r_day = steps[np.argmax(r_curve)]
        u_day = steps[np.argmax(u_curve)]
        peak_r = r_curve[r_day]
        peak_u = u_curve[u_day]
        sub20 = perrun[perrun['SAR_pct'] == 20]
        cond20 = sub20[sub20['R_AR'] >= EXTINCTION_THRESHOLD]
        delay_20 = float(np.mean(cond20['R_day']) - np.mean(cond20['U_day']))
        ax.annotate('', xy=(u_day, 0.6*max(peak_r, peak_u)),
                    xytext=(r_day, 0.6*max(peak_r, peak_u)),
                    arrowprops=dict(arrowstyle='<->', color='gray', lw=1.5))
        ax.text((r_day+u_day)/2, 0.62*max(peak_r, peak_u),
                f'{delay_20:.1f} d', ha='center', va='bottom', fontsize=8, color='gray')

    ax.set_title(f'SAR = {sar}%', fontsize=11)
    ax.set_xlabel('Day', fontsize=10)
    ax.set_ylabel('Mean daily new exposures', fontsize=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

axes[0].legend(fontsize=9)
plt.suptitle('Mean epidemic curves: Scenario R (structured) vs Scenario U (shuffled)\n'
             '50 paired replicates per panel; n=50 at all SAR levels',
             fontsize=11, y=1.02)
plt.tight_layout()
plt.savefig(OUT_CURVES, dpi=200, bbox_inches='tight')
print(f'Saved: {OUT_CURVES}')
plt.close()

# ── Peak comparison figure ─────────────────────────────────────────────────────
# Compute conditional per-SAR means and SDs
r_peak_m, u_peak_m, r_peak_s, u_peak_s = [], [], [], []
r_day_m,  u_day_m,  r_day_s,  u_day_s  = [], [], [], []

for sar in SARS:
    sub  = perrun[perrun['SAR_pct'] == sar]
    cond = sub[sub['R_AR'] >= EXTINCTION_THRESHOLD]
    r_peak_m.append(cond['R_peak'].mean());  r_peak_s.append(cond['R_peak'].std(ddof=1))
    u_peak_m.append(cond['U_peak'].mean());  u_peak_s.append(cond['U_peak'].std(ddof=1))
    r_day_m.append(cond['R_day'].mean());    r_day_s.append(cond['R_day'].std(ddof=1))
    u_day_m.append(cond['U_day'].mean());    u_day_s.append(cond['U_day'].std(ddof=1))

r_peak_m, u_peak_m = np.array(r_peak_m), np.array(u_peak_m)
r_peak_s, u_peak_s = np.array(r_peak_s), np.array(u_peak_s)
r_day_m,  u_day_m  = np.array(r_day_m),  np.array(u_day_m)
r_day_s,  u_day_s  = np.array(r_day_s),  np.array(u_day_s)

x = np.array(SARS, dtype=float)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Left: peak incidence
ax1.errorbar(x, r_peak_m, yerr=r_peak_s, fmt='o-', color='#1f77b4',
             capsize=5, label='Scenario R', lw=2)
ax1.errorbar(x, u_peak_m, yerr=u_peak_s, fmt='s--', color='#d62728',
             capsize=5, label='Scenario U', lw=2)
ax1.set_xlabel('Household SAR (%)', fontsize=11)
ax1.set_ylabel('Mean peak daily incidence', fontsize=11)
ax1.set_title('Peak incidence by SAR scenario', fontsize=11)
ax1.legend(fontsize=10)
ax1.grid(axis='y', alpha=0.3, linestyle='--')
ax1.set_xticks(SARS)

# Right: day of peak
ax2.errorbar(x, r_day_m, yerr=r_day_s, fmt='o-', color='#1f77b4',
             capsize=5, label='Scenario R', lw=2)
ax2.errorbar(x, u_day_m, yerr=u_day_s, fmt='s--', color='#d62728',
             capsize=5, label='Scenario U', lw=2)
ax2.set_xlabel('Household SAR (%)', fontsize=11)
ax2.set_ylabel('Mean day of peak', fontsize=11)
ax2.set_title('Day of peak by SAR scenario', fontsize=11)
ax2.legend(fontsize=10)
ax2.grid(axis='y', alpha=0.3, linestyle='--')
ax2.set_xticks(SARS)

plt.tight_layout()
plt.savefig(OUT_PEAK, dpi=200, bbox_inches='tight')
print(f'Saved: {OUT_PEAK}')
plt.close()

# ── Inactive-gap figure ────────────────────────────────────────────────────────
# Shows attack-rate gap (U minus R) for the inactive subpopulation and overall
# population across all four SAR scenarios. Illustrates the assortative-
# segregation mechanism: inactive agents are disproportionately affected by the
# household shuffle because they have no work/school contacts of their own.
overall_gaps  = []
inactive_gaps = []

for sar in SARS:
    sub  = perrun[perrun['SAR_pct'] == sar]
    cond = sub[sub['R_AR'] >= EXTINCTION_THRESHOLD]
    overall_gaps.append(100 * float(np.mean(cond['U_AR'] - cond['R_AR'])))
    inactive_gaps.append(100 * float(np.mean(cond['U_inactive_AR'] - cond['R_inactive_AR'])))

fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(SARS, inactive_gaps, 'ro-', lw=2, markersize=7, label='Inactive/elderly subpopulation')
ax.plot(SARS, overall_gaps,  'bs--', lw=2, markersize=7, label='Overall population')
ax.axvline(20, color='gray', linestyle=':', lw=1.5, label='SAR=20% (primary anchor)')
ax.set_xlabel('Household SAR (%)', fontsize=12)
ax.set_ylabel('Attack-rate gap: U − R (pp)', fontsize=12)
ax.set_title('Assortative segregation: attack-rate gap by subpopulation', fontsize=12)
ax.set_xticks(SARS)
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')
plt.tight_layout()
plt.savefig(OUT_INACT, dpi=200, bbox_inches='tight')
print(f'Saved: {OUT_INACT}')
plt.close()

# ── Violin: per-replicate AR distributions ────────────────────────────────────
# Shows the full replicate-to-replicate variability for both scenarios,
# making clear that the R vs U separation is not driven by a few outliers.
fig, axes = plt.subplots(1, 4, figsize=(14, 5), sharey=False)

for ax, sar in zip(axes, SARS):
    sub  = perrun[perrun['SAR_pct'] == sar]
    cond = sub[sub['R_AR'] >= EXTINCTION_THRESHOLD]
    r_ar = 100 * cond['R_AR'].values
    u_ar = 100 * cond['U_AR'].values

    parts = ax.violinplot([r_ar, u_ar], positions=[1, 2],
                          showmedians=True, showextrema=True)
    for i, (body, color) in enumerate(zip(parts['bodies'], ['#1f77b4','#d62728'])):
        body.set_facecolor(color)
        body.set_alpha(0.6)
    parts['cmedians'].set_color(['#1f77b4','#d62728'])
    parts['cmaxes'].set_color('gray')
    parts['cmins'].set_color('gray')
    parts['cbars'].set_color('gray')

    ax.scatter([1]*len(r_ar), r_ar, s=6, color='#1f77b4', alpha=0.4, zorder=3)
    ax.scatter([2]*len(u_ar), u_ar, s=6, color='#d62728', alpha=0.4, zorder=3)

    ax.set_xticks([1, 2])
    ax.set_xticklabels(['R', 'U'], fontsize=11)
    ax.set_title(f'SAR = {sar}%', fontsize=11)
    ax.set_xlabel('Scenario', fontsize=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

axes[0].set_ylabel('Final attack rate (%)', fontsize=11)
plt.suptitle('Per-replicate attack-rate distributions: Scenario R vs U\n'
             '(50 paired seeds; n=50 at all SAR levels)',
             fontsize=11, y=1.02)
plt.tight_layout()
plt.savefig(OUT_VIOLIN, dpi=200, bbox_inches='tight')
print(f'Saved: {OUT_VIOLIN}')
plt.close()

# ── Archive sweep CSVs for reference ─────────────────────────────────────────
ABM_DIR    = os.path.join(ROOT, 'abm-patras-greece-main')
ARCH_DIR   = os.path.join(ROOT, 'data', 'abm_results')
os.makedirs(ARCH_DIR, exist_ok=True)
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
for fname in ['full_sweep_50rep_summary.csv',
              'full_sweep_50rep_perrun.csv',
              'full_sweep_50rep_curves.csv']:
    src = os.path.join(ABM_DIR, fname)
    dst = os.path.join(ARCH_DIR, fname.replace('.csv', f'_{stamp}.csv'))
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f'Archived: {dst}')
print('Archive complete.')
