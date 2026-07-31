"""sweep_65plus_50rep.py  --  round-3 reviewer item 1.1.

Re-runs the exact 50-replicate SAR sweep of full_sweep_50rep.py (same seeds 0..49,
same beta_family per SAR) but additionally records the 65+ subpopulation attack rate,
so the 65+ U-R gap can be reported at 50 replicates (matching the inactive column) and
cited in the abstract, instead of the earlier 5-seed bolt-on.

Sanity: the overall and inactive gaps produced here must reproduce the published
Table 14 values (SAR20: R 70.85 / U 73.28 / inactive gap 6.02); the 65+ column is the
new output. Writes sweep_65plus_50rep_summary.csv and _perrun.csv.
"""
import sys, os, time, random
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment as run_exp

BASE = os.path.dirname(os.path.abspath(__file__))
SAR_TARGETS = [0.15, 0.20, 0.25, 0.30]
N_SEEDS = 50
TOTAL_STEPS = run_exp.TOTAL_STEPS


def sar_to_beta(sar):
    return 1.0 - (1.0 - sar) ** run_exp.GAMMA


def activity_category(work_id, school_id):
    if work_id != -1: return 'employed'
    if school_id != -1: return 'student'
    return 'inactive'


def run_once_tracked(agents_df, seed, beta_family, total_steps=TOTAL_STEPS):
    random.seed(seed); np.random.seed(seed)
    agents, by_fam, by_work, by_school, by_age, s_in_work, s_in_school = \
        run_exp._build_model(agents_df)
    N = len(agents)
    rng = np.random.default_rng(seed)
    init_ids = rng.choice(N, size=run_exp.INITIAL_INFECTED, replace=False)
    active = []
    for idx in init_ids:
        agents[idx].status = 'I'; agents[idx].next_status = 'I'
        active.append(agents[idx])
        a = agents[idx]
        if a.work_id != -1: s_in_work[a.work_id] -= 1
        if a.school_id != -1: s_in_school[a.school_id] -= 1
    for step in range(total_steps):
        active, _ = run_exp._do_step(active, agents, by_fam, by_work, by_school,
                                     by_age, s_in_work, s_in_school, beta_family)
        if not active:
            break
    S_final = sum(1 for a in agents if a.status == 'S')
    # subpopulation attack rates
    inact_inf = inact_tot = e65_inf = e65_tot = 0
    for a in agents:
        if activity_category(a.work_id, a.school_id) == 'inactive':
            inact_tot += 1
            if a.status != 'S': inact_inf += 1
        if a.age >= 65:
            e65_tot += 1
            if a.status != 'S': e65_inf += 1
    return {
        'ar':       1.0 - S_final / N,
        'inact_ar': inact_inf / inact_tot if inact_tot else 0.0,
        'e65_ar':   e65_inf / e65_tot if e65_tot else 0.0,
    }


def wpval(a, b):
    diff = np.asarray(a) - np.asarray(b)
    if np.all(diff == 0):
        return 1.0
    return float(wilcoxon(a, b)[1])


print("Loading agents ...")
r_df = pd.read_csv(os.path.join(BASE, 'agents_patras.csv'))
u_df = run_exp.build_u_agents(r_df, u_seed=999)
print(f"  {len(r_df):,} agents  |  {r_df['Family_ID'].nunique():,} R households")
print(f"  agents 65+: {int((r_df['Age'] >= 65).sum()):,}")
print()

wall = time.time()
rows = []
perrun = []
for sar in SAR_TARGETS:
    beta = sar_to_beta(sar)
    tag = f"SAR{int(100*sar)}"
    r_ov=[]; u_ov=[]; r_ia=[]; u_ia=[]; r_e=[]; u_e=[]
    t0 = time.time()
    for seed in range(N_SEEDS):
        rr = run_once_tracked(r_df, seed, beta)
        ur = run_once_tracked(u_df, seed, beta)
        r_ov.append(rr['ar']);       u_ov.append(ur['ar'])
        r_ia.append(rr['inact_ar']); u_ia.append(ur['inact_ar'])
        r_e.append(rr['e65_ar']);    u_e.append(ur['e65_ar'])
        perrun.append({'SAR_pct': int(100*sar), 'seed': seed,
                       'R_AR': rr['ar'], 'U_AR': ur['ar'],
                       'R_inactive_AR': rr['inact_ar'], 'U_inactive_AR': ur['inact_ar'],
                       'R_65plus_AR': rr['e65_ar'], 'U_65plus_AR': ur['e65_ar']})
        if (seed + 1) % 10 == 0:
            print(f"  {tag} [{seed+1:2d}/{N_SEEDS}]  "
                  f"R={100*np.mean(r_ov):.2f}%  U={100*np.mean(u_ov):.2f}%  "
                  f"inact U-R={100*(np.mean(u_ia)-np.mean(r_ia)):+.2f}pp  "
                  f"65+ U-R={100*(np.mean(u_e)-np.mean(r_e)):+.2f}pp  "
                  f"[{time.time()-t0:.0f}s]")
    ra, ua = np.array(r_ov), np.array(u_ov)
    ia, uia = np.array(r_ia), np.array(u_ia)
    ea, uea = np.array(r_e), np.array(u_e)
    rows.append({
        'SAR_pct': int(100*sar), 'beta_family': round(beta, 4),
        'R_AR': 100*ra.mean(), 'U_AR': 100*ua.mean(),
        'overall_gap_pp': 100*(ua.mean()-ra.mean()), 'overall_p': wpval(ra, ua),
        'R_inactive': 100*ia.mean(), 'U_inactive': 100*uia.mean(),
        'inactive_gap_pp': 100*(uia.mean()-ia.mean()), 'inactive_p': wpval(ia, uia),
        'R_65plus': 100*ea.mean(), 'U_65plus': 100*uea.mean(),
        'e65_gap_pp': 100*(uea.mean()-ea.mean()),
        'e65_gap_sd': 100*np.std(uea-ea, ddof=1), 'e65_p': wpval(ea, uea),
    })
    print(f"  == {tag} done [{time.time()-t0:.0f}s]  "
          f"65+ gap = {100*(uea.mean()-ea.mean()):+.2f}pp "
          f"(R {100*ea.mean():.1f} vs U {100*uea.mean():.1f}), p={wpval(ea, uea):.2e}\n")

df = pd.DataFrame(rows)
df.to_csv(os.path.join(BASE, 'sweep_65plus_50rep_summary.csv'), index=False)
pd.DataFrame(perrun).to_csv(os.path.join(BASE, 'sweep_65plus_50rep_perrun.csv'), index=False)
print(f"Total wall: {(time.time()-wall)/60:.1f} min")
print("\n== 65+ vs inactive gap (50 replicates) ==")
for _, r in df.iterrows():
    print(f"  SAR {r['SAR_pct']:>2}%:  overall {r['overall_gap_pp']:+.2f}  "
          f"inactive {r['inactive_gap_pp']:+.2f}  65+ {r['e65_gap_pp']:+.2f}pp "
          f"(SD {r['e65_gap_sd']:.2f}, p {r['e65_p']:.1e})")
print("\nSaved sweep_65plus_50rep_summary.csv + _perrun.csv")
