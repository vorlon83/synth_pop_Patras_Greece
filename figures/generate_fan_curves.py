"""
Generate per-replicate epidemic curves for SAR=20% (primary parameterisation) and
plot a fan chart showing median + IQR (25th–75th percentile) bands.

Runs 50 paired replicates (R and U) at SAR=20% independently of the main sweep
so we capture full daily curves, not just scalar summaries.

Output:
  Synthetic_Population_manuscript/img/fig_fan_curves.png
  data/abm_results/fan_curves_perrun_SAR20.csv   (per-replicate daily curves)
"""
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ABM_DIR = os.path.join(ROOT, 'abm-patras-greece-main')
sys.path.insert(0, ABM_DIR)
import run_experiment as re
from abm_sweep_common import sar_to_beta, run_once_tracked

AGENTS_CSV      = os.path.join(ABM_DIR, 'agents_patras.csv')
OUT_FIGURE      = os.path.join(ROOT, 'Synthetic_Population_manuscript', 'img', 'fig_fan_curves.png')
OUT_CURVES_CSV  = os.path.join(ROOT, 'data', 'abm_results', 'fan_curves_perrun_SAR20.csv')

SAR          = 0.20
N_SEEDS      = 50
TOTAL_STEPS  = re.TOTAL_STEPS          # 180
EXTINCTION_THRESHOLD = 0.01

os.makedirs(os.path.join(ROOT, 'data', 'abm_results'), exist_ok=True)

# Household transmission rate for SAR=20%, passed explicitly to every _do_step
# call below -- never mutate re.BETA_FAMILY, since it is a default argument
# bound at _do_step's definition time and a later attribute mutation would
# silently have no effect (see bugs_to_fix.md BUG-A/BUG-B).
BETA_FAMILY = sar_to_beta(SAR, re.GAMMA)

print(f'Fan-curve run: SAR={int(SAR*100)}%  β_family={BETA_FAMILY:.4f}  seeds=0–{N_SEEDS-1}')
print(f'Loading agents from {AGENTS_CSV} ...')
r_df = pd.read_csv(AGENTS_CSV)
u_df = re.build_u_agents(r_df, u_seed=999)
print(f'  {len(r_df):,} agents  |  {r_df["Family_ID"].nunique():,} households')

def run_and_track(agents_df, seed):
    metrics, _ = run_once_tracked(re, agents_df, seed, total_steps=TOTAL_STEPS,
                                   beta_family=BETA_FAMILY)
    return np.array(metrics['daily_new'], dtype=float), metrics['attack_rate']

r_curves, u_curves = [], []
r_ars,    u_ars    = [], []

for seed in range(N_SEEDS):
    r_c, r_ar = run_and_track(r_df, seed)
    u_c, u_ar = run_and_track(u_df, seed)
    r_curves.append(r_c)
    u_curves.append(u_c)
    r_ars.append(r_ar)
    u_ars.append(u_ar)
    if (seed + 1) % 10 == 0:
        print(f'  seed {seed+1:2d}/50  R_AR={100*r_ar:.1f}%  U_AR={100*u_ar:.1f}%')

# Save per-replicate curve CSV for reference
rows = []
days = np.arange(TOTAL_STEPS)
for seed in range(N_SEEDS):
    for d in range(TOTAL_STEPS):
        rows.append({'seed': seed, 'day': d,
                     'R_new': r_curves[seed][d],
                     'U_new': u_curves[seed][d]})
pd.DataFrame(rows).to_csv(OUT_CURVES_CSV, index=False)
print(f'Saved curves CSV: {OUT_CURVES_CSV}')

# Exclude extinction replicates from R (AR < 1%) for statistics
valid_r = [i for i in range(N_SEEDS) if r_ars[i] >= EXTINCTION_THRESHOLD]
r_mat = np.array([r_curves[i] for i in valid_r])    # (n_valid, 180)
u_mat = np.array(u_curves)                            # (50, 180)

r_med = np.median(r_mat, axis=0)
r_q25 = np.percentile(r_mat, 25, axis=0)
r_q75 = np.percentile(r_mat, 75, axis=0)

u_med = np.median(u_mat, axis=0)
u_q25 = np.percentile(u_mat, 25, axis=0)
u_q75 = np.percentile(u_mat, 75, axis=0)

extinct_seeds = [i for i in range(N_SEEDS) if r_ars[i] < EXTINCTION_THRESHOLD]
print(f'R extinction seeds: {extinct_seeds}  (excluded from fan)')

fig, ax = plt.subplots(figsize=(9, 5))
t = np.arange(TOTAL_STEPS)

# Thin individual replicate lines (light, in background)
for i in valid_r:
    ax.plot(t, r_curves[i], color='#1f77b4', alpha=0.07, lw=0.7)
for i in range(N_SEEDS):
    ax.plot(t, u_curves[i], color='#d62728', alpha=0.07, lw=0.7)

# IQR bands
ax.fill_between(t, r_q25, r_q75, color='#1f77b4', alpha=0.25,
                label='R IQR (25th–75th %ile)')
ax.fill_between(t, u_q25, u_q75, color='#d62728', alpha=0.25,
                label='U IQR (25th–75th %ile)')

# Median lines
ax.plot(t, r_med, color='#1f77b4', lw=2.2, label=f'R median (n={len(valid_r)})')
ax.plot(t, u_med, color='#d62728', lw=2.2, linestyle='--',
        label=f'U median (n={N_SEEDS})')

ax.set_xlabel('Day', fontsize=12)
ax.set_ylabel('Daily new exposures', fontsize=12)
ax.set_title('Epidemic trajectories: Scenario R vs U at SAR=20%\n'
             'Median ± IQR across 50 paired replicates', fontsize=11)
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')
ax.set_xlim(0, TOTAL_STEPS - 1)

plt.tight_layout()
plt.savefig(OUT_FIGURE, dpi=200, bbox_inches='tight')
print(f'Saved: {OUT_FIGURE}')
plt.close()

print('Done.')
