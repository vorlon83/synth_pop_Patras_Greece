"""Quick reproducibility + timing check for the 65+ 50-rep extraction (round-3 item 1.1).

Runs SAR=20% (beta_family=0.0221) for seeds 0..N-1, R vs U, and reports overall,
inactive, and 65+ attack-rate gaps plus per-pair wall time. Purpose: confirm this
machine reproduces the published SAR-20% row (R 70.85 / U 73.28 / inactive gap 6.02)
before committing to the full 50-seed run, and measure timing.
"""
import sys, os, time, random
import numpy as np
import pandas as pd
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment as run_exp

BASE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BETA_FAMILY_SAR20 = 0.0221


def activity_category(work_id, school_id):
    if work_id != -1: return 'employed'
    if school_id != -1: return 'student'
    return 'inactive'


def run_once_tracked(agents_df, seed, total_steps=180, beta_family=BETA_FAMILY_SAR20):
    random.seed(seed); np.random.seed(seed)
    agents, by_fam, by_work, by_school, by_age, s_in_work, s_in_school = \
        run_exp._build_model(agents_df)
    Nag = len(agents)
    rng = np.random.default_rng(seed)
    init_ids = rng.choice(Nag, size=run_exp.INITIAL_INFECTED, replace=False)
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
    return 1.0 - S_final / Nag, agents


def inactive_ar(agents):
    inf = tot = 0
    for a in agents:
        if activity_category(a.work_id, a.school_id) == 'inactive':
            tot += 1
            if a.status != 'S': inf += 1
    return inf / tot if tot else 0.0


def elderly65_ar(agents):
    inf = tot = 0
    for a in agents:
        if a.age >= 65:
            tot += 1
            if a.status != 'S': inf += 1
    return inf / tot if tot else 0.0


r_df = pd.read_csv(os.path.join(BASE, 'agents_patras.csv'))
u_df = run_exp.build_u_agents(r_df, u_seed=999)
print(f"Loaded {len(r_df):,} agents; {r_df['Family_ID'].nunique():,} households; N seeds={N}")

r_ov=[]; u_ov=[]; r_ia=[]; u_ia=[]; r_e=[]; u_e=[]
t0 = time.time()
for seed in range(N):
    ts = time.time()
    rar, rag = run_once_tracked(r_df, seed)
    uar, uag = run_once_tracked(u_df, seed)
    r_ov.append(rar); u_ov.append(uar)
    r_ia.append(inactive_ar(rag)); u_ia.append(inactive_ar(uag))
    r_e.append(elderly65_ar(rag)); u_e.append(elderly65_ar(uag))
    print(f"  seed {seed}: R={100*rar:.2f}% U={100*uar:.2f}% "
          f"inact U-R={100*(u_ia[-1]-r_ia[-1]):+.2f}pp "
          f"65+ U-R={100*(u_e[-1]-r_e[-1]):+.2f}pp  [{time.time()-ts:.0f}s/pair]")

print(f"\n=== MEAN over {N} seeds ===")
print(f"  Overall : R={100*np.mean(r_ov):.2f}%  U={100*np.mean(u_ov):.2f}%  gap={100*(np.mean(u_ov)-np.mean(r_ov)):+.2f}pp")
print(f"  Inactive: R={100*np.mean(r_ia):.2f}%  U={100*np.mean(u_ia):.2f}%  gap={100*(np.mean(u_ia)-np.mean(r_ia)):+.2f}pp")
print(f"  65+     : R={100*np.mean(r_e):.2f}%  U={100*np.mean(u_e):.2f}%  gap={100*(np.mean(u_e)-np.mean(r_e)):+.2f}pp")
print(f"  total {time.time()-t0:.0f}s -> {(time.time()-t0)/N:.0f}s/pair; 50 seeds ~= {50*(time.time()-t0)/N/60:.0f} min")
print("Published SAR20 row: R 70.85 / U 73.28 / inactive gap 6.02 (50 seeds)")
