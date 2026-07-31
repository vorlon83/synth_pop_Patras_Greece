"""
Beta-family sweep: corrected full model (all 5 layers, normalized same-age)
at literature-consistent household SAR values for COVID-19.

Reference: Madewell et al. (2021) JAMA Network Open 3(12):e2031756
  Pooled COVID-19 household SAR: 18.8% (95% CI 15.4-22.2%)

SAR targets and implied per-day beta (infectious period 1/GAMMA = 10 days):
  SAR = 1 - (1 - beta)^10  =>  beta = 1 - (1 - SAR)^(1/10)

For each SAR: run 5 paired seeds (R vs U), collect attack rate and
per-status (employed / student / inactive) breakdown.
"""
import sys, os, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment as re
from abm_sweep_common import (sar_to_beta, activity_category, per_status_ar,
                               run_once_tracked as _run_once_tracked)

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Target SARs and derived betas ────────────────────────────────────────────
SAR_TARGETS = [0.15, 0.20, 0.25, 0.30]
GAMMA = re.GAMMA   # 0.1  → mean infectious period 10 days

sar_betas = {}
for sar in SAR_TARGETS:
    beta = sar_to_beta(sar, GAMMA)
    sar_betas[sar] = beta

print("SAR -> beta_family conversions (1/GAMMA = 10 days):")
for sar, beta in sar_betas.items():
    print(f"  SAR {100*sar:.0f}% -> beta_family = {beta:.4f}")
print()

# ── Load population ───────────────────────────────────────────────────────────
r_df = pd.read_csv(os.path.join(BASE, 'agents_patras.csv'))
u_df = re.build_u_agents(r_df, u_seed=999)
print(f"Loaded {len(r_df):,} agents. U households shuffled.")
print()

N_SEEDS = 5


def run_once_tracked(agents_df, seed, total_steps=180, beta_family=None):
    return _run_once_tracked(re, agents_df, seed, total_steps=total_steps,
                              beta_family=beta_family)


# ── Sweep ─────────────────────────────────────────────────────────────────────
all_rows = []
CATS = ['employed', 'student', 'inactive']

for sar in SAR_TARGETS:
    beta = sar_betas[sar]

    r_ars, u_ars = [], []
    r_peaks, u_peaks = [], []
    r_days, u_days = [], []
    r_status_ars = {c: [] for c in CATS}
    u_status_ars = {c: [] for c in CATS}

    t0 = time.time()
    for seed in range(N_SEEDS):
        rr, r_agents = run_once_tracked(r_df, seed=seed, beta_family=beta)
        ur, u_agents = run_once_tracked(u_df, seed=seed, beta_family=beta)

        r_ars.append(rr['attack_rate'])
        u_ars.append(ur['attack_rate'])
        r_peaks.append(rr['peak_incidence'])
        u_peaks.append(ur['peak_incidence'])
        r_days.append(rr['day_of_peak'])
        u_days.append(ur['day_of_peak'])

        for cat in CATS:
            r_status_ars[cat].append(per_status_ar(r_agents).get(cat, 0.0))
            u_status_ars[cat].append(per_status_ar(u_agents).get(cat, 0.0))

    elapsed = time.time() - t0

    r_ar_m = 100 * np.mean(r_ars)
    u_ar_m = 100 * np.mean(u_ars)
    diff   = u_ar_m - r_ar_m

    print(f"{'='*60}")
    print(f"SAR {100*sar:.0f}%  (beta_family={beta:.4f})  [{elapsed:.0f}s]")
    print(f"  Overall  R={r_ar_m:.2f}%  U={u_ar_m:.2f}%  U-R={diff:+.2f}pp")
    print(f"  Day-of-peak  R={np.mean(r_days):.1f}  U={np.mean(u_days):.1f}  diff={np.mean(u_days)-np.mean(r_days):+.1f}")
    print(f"  Peak incidence  R={np.mean(r_peaks):.0f}  U={np.mean(u_peaks):.0f}")
    print()
    print(f"  Per-status AR:  {'Category':12s}  {'R AR':>8}  {'U AR':>8}  {'U-R':>8}")
    print(f"  {'':14s}  {'-'*36}")
    for cat in CATS:
        r_s = 100 * np.mean(r_status_ars[cat])
        u_s = 100 * np.mean(u_status_ars[cat])
        diff_s = u_s - r_s
        flag = '  <-- contrast' if cat == 'inactive' else ''
        print(f"  {'':14s}  {cat:12s}  {r_s:>7.2f}%  {u_s:>7.2f}%  {diff_s:>+7.2f}pp{flag}")
    print()

    all_rows.append({
        'SAR_pct': 100*sar,
        'beta_family': beta,
        'R_AR_pct': r_ar_m,
        'U_AR_pct': u_ar_m,
        'diff_AR_pp': diff,
        'R_peak_day': np.mean(r_days),
        'U_peak_day': np.mean(u_days),
        'R_peak_inc': np.mean(r_peaks),
        'U_peak_inc': np.mean(u_peaks),
        **{f'R_{c}_AR_pct': 100*np.mean(r_status_ars[c]) for c in CATS},
        **{f'U_{c}_AR_pct': 100*np.mean(u_status_ars[c]) for c in CATS},
        **{f'diff_{c}_pp': 100*(np.mean(u_status_ars[c])-np.mean(r_status_ars[c]))
           for c in CATS},
    })

# ── Summary table ─────────────────────────────────────────────────────────────
df = pd.DataFrame(all_rows)
print("="*60)
print("SWEEP SUMMARY")
print(f"{'SAR':>6}  {'beta':>6}  {'R AR':>8}  {'U AR':>8}  {'U-R':>8}  {'inactive U-R':>14}")
print("-"*60)
for _, row in df.iterrows():
    print(f"{row['SAR_pct']:>5.0f}%  {row['beta_family']:>6.4f}  "
          f"{row['R_AR_pct']:>7.2f}%  {row['U_AR_pct']:>7.2f}%  "
          f"{row['diff_AR_pp']:>+7.2f}pp  {row['diff_inactive_pp']:>+12.2f}pp")

out_path = os.path.join(BASE, 'beta_family_sweep_results.csv')
df.to_csv(out_path, index=False)
print(f"\nSaved: {out_path}")
