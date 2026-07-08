"""Quick 5-seed diagnostic: full model with corrected same-age normalization."""
import sys, os, time
import numpy as np
import pandas as pd

_DIAG_DIR = os.path.dirname(os.path.abspath(__file__))
_ABM_DIR  = os.path.dirname(_DIAG_DIR)
sys.path.insert(0, _ABM_DIR)
import run_experiment as re

BASE = _ABM_DIR
r_df = pd.read_csv(os.path.join(BASE, 'agents_patras.csv'))
u_df = re.build_u_agents(r_df, u_seed=999)

N_SEEDS = 5
r_ars, u_ars, r_peaks, u_peaks, r_days, u_days = [], [], [], [], [], []

t0 = time.time()
for seed in range(N_SEEDS):
    rr = re.run_once(r_df, seed=seed)
    ur = re.run_once(u_df, seed=seed)
    r_ars.append(rr['attack_rate'])
    u_ars.append(ur['attack_rate'])
    r_peaks.append(rr['peak_incidence'])
    u_peaks.append(ur['peak_incidence'])
    r_days.append(rr['day_of_peak'])
    u_days.append(ur['day_of_peak'])
    ar_r = 100 * rr['attack_rate']
    ar_u = 100 * ur['attack_rate']
    print(f"  seed {seed}: R AR={ar_r:.3f}% peak={rr['peak_incidence']:6d}"
          f"  |  U AR={ar_u:.3f}% peak={ur['peak_incidence']:6d}")

elapsed = time.time() - t0
print()
print(f"Corrected same-age (sample cpd contacts) -- all 5 layers, {N_SEEDS} seeds, {elapsed:.1f}s")
print(f"  R  AR: {100*np.mean(r_ars):.3f}%  peak: {np.mean(r_peaks):.0f}  day: {np.mean(r_days):.1f}")
print(f"  U  AR: {100*np.mean(u_ars):.3f}%  peak: {np.mean(u_peaks):.0f}  day: {np.mean(u_days):.1f}")
print(f"  U-R:  {100*(np.mean(u_ars)-np.mean(r_ars)):+.3f} pp")

print()
print("Corrected same-age E[transmissions per I agent per step]:")
for ag, vals in re.AGE_GROUPS.items():
    cpd = vals['contacts_per_day']
    n = int(round(cpd))
    exp = n * re.BETA_SAME_AGE
    print(f"  {ag:6s}: sample {n:2d} x BETA_SAME_AGE={re.BETA_SAME_AGE} = {exp:.5f}/step")
