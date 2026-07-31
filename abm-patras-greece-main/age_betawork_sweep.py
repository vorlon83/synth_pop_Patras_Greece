"""
Round-3 reviewer response: (1) 65+ attack-rate gap alongside the inactive gap
(is the "inactive/elderly" effect age-mediated?), and (2) beta_work sensitivity
of the inactive gap (does the 6.02 pp headline survive a plausible beta_work
range, given beta_work=0.10 is inherited, not calibrated?).

At the primary SAR=20% (beta_family=0.0221), sweep BETA_WORK over
{0.05, 0.10, 0.15} with 5 paired seeds (R vs U). For each, report overall,
inactive-subpopulation, and 65+ attack-rate gaps. Mirrors the proven structure
of beta_family_sweep.py.
"""
import sys, os, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment as re
from abm_sweep_common import (per_status_ar, elderly65_ar,
                               run_once_tracked as _run_once_tracked)

BASE = os.path.dirname(os.path.abspath(__file__))

BETA_FAMILY_SAR20 = 0.0221      # primary calibrated value at SAR=20%
BETA_WORK_VALUES = [0.05, 0.10, 0.15]
N_SEEDS = 5


def run_once_tracked(agents_df, seed, total_steps=180, beta_family=None, beta_work=None):
    return _run_once_tracked(re, agents_df, seed, total_steps=total_steps,
                              beta_family=beta_family, beta_work=beta_work)


def inactive_ar(agents):
    return per_status_ar(agents).get('inactive', 0.0)


r_df = pd.read_csv(os.path.join(BASE, 'agents_patras.csv'))
u_df = re.build_u_agents(r_df, u_seed=999)
print(f"Loaded {len(r_df):,} agents. U households shuffled.")
n_elderly = int((r_df['Age'] >= 65).sum()) if 'Age' in r_df.columns else -1
print(f"Agents aged 65+: {n_elderly:,}")
print()

rows = []
for bw in BETA_WORK_VALUES:
    r_ov, u_ov, r_ia, u_ia, r_e65, u_e65 = ([] for _ in range(6))
    t0 = time.time()
    for seed in range(N_SEEDS):
        rr, r_ag = run_once_tracked(r_df, seed=seed, beta_family=BETA_FAMILY_SAR20, beta_work=bw)
        ur, u_ag = run_once_tracked(u_df, seed=seed, beta_family=BETA_FAMILY_SAR20, beta_work=bw)
        r_ov.append(rr['attack_rate']); u_ov.append(ur['attack_rate'])
        r_ia.append(inactive_ar(r_ag));  u_ia.append(inactive_ar(u_ag))
        r_e65.append(elderly65_ar(r_ag)); u_e65.append(elderly65_ar(u_ag))
    el = time.time() - t0
    row = {
        'beta_work': bw,
        'R_AR_pct':   100*np.mean(r_ov), 'U_AR_pct':   100*np.mean(u_ov),
        'diff_AR_pp': 100*(np.mean(u_ov)-np.mean(r_ov)),
        'R_inactive_AR_pct': 100*np.mean(r_ia), 'U_inactive_AR_pct': 100*np.mean(u_ia),
        'diff_inactive_pp':  100*(np.mean(u_ia)-np.mean(r_ia)),
        'R_65plus_AR_pct':   100*np.mean(r_e65), 'U_65plus_AR_pct':   100*np.mean(u_e65),
        'diff_65plus_pp':    100*(np.mean(u_e65)-np.mean(r_e65)),
    }
    rows.append(row)
    print(f"{'='*64}")
    print(f"BETA_WORK={bw}  (beta_family={BETA_FAMILY_SAR20}, SAR=20%)  [{el:.0f}s, {N_SEEDS} seeds]")
    print(f"  Overall   R={row['R_AR_pct']:.2f}%  U={row['U_AR_pct']:.2f}%  U-R={row['diff_AR_pp']:+.2f}pp")
    print(f"  Inactive  R={row['R_inactive_AR_pct']:.2f}%  U={row['U_inactive_AR_pct']:.2f}%  U-R={row['diff_inactive_pp']:+.2f}pp")
    print(f"  65+       R={row['R_65plus_AR_pct']:.2f}%  U={row['U_65plus_AR_pct']:.2f}%  U-R={row['diff_65plus_pp']:+.2f}pp")
    print()

df = pd.DataFrame(rows)
out = os.path.join(BASE, 'age_betawork_sweep_results.csv')
df.to_csv(out, index=False)
print("SUMMARY (inactive vs 65+ gap across beta_work):")
for _, r in df.iterrows():
    print(f"  bw={r['beta_work']:.2f}  inactive U-R={r['diff_inactive_pp']:+.2f}pp   65+ U-R={r['diff_65plus_pp']:+.2f}pp")
print(f"\nSaved: {out}")
