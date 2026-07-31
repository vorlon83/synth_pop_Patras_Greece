"""
Saturation diagnostic: isolate which layers are causing 100% attack rate.

Runs 5 seeds under four layer combinations:
  FULL : all 5 layers (published parameters)
  FWS  : family + work + school only  (BETA_SAME_AGE=0, BETA_RANDOM=0)
  FAM  : family only                  (BETA_WORK=0, BETA_SCHOOL=0, BETA_SAME_AGE=0, BETA_RANDOM=0)
  FW   : family + work                (BETA_SCHOOL=0, BETA_SAME_AGE=0, BETA_RANDOM=0)

If FWS still saturates, the saturating force is family or work (not same-age).
If FWS drops below saturation but FAM does not, work is the culprit.
"""
import os, sys, random
import numpy as np
import pandas as pd

_DIAG_DIR = os.path.dirname(os.path.abspath(__file__))
_ABM_DIR  = os.path.dirname(_DIAG_DIR)
sys.path.insert(0, _ABM_DIR)
import run_experiment as re_mod

BASE = _ABM_DIR
N_SEEDS = 5


def run_scenario(agents_df, beta_family, beta_work, beta_school,
                 beta_random, beta_same_age, seed, total_steps=180):
    """Run one replicate with overridden betas."""
    re_mod.BETA_FAMILY   = beta_family
    re_mod.BETA_WORK     = beta_work
    re_mod.BETA_SCHOOL   = beta_school
    re_mod.BETA_RANDOM   = beta_random
    re_mod.BETA_SAME_AGE = beta_same_age
    res = re_mod.run_once(agents_df, seed=seed, total_steps=total_steps)
    return res['attack_rate'], res['peak_incidence'], res['day_of_peak']


print("Loading agents ...")
r_df = pd.read_csv(os.path.join(BASE, 'agents_patras.csv'))
u_df = re_mod.build_u_agents(r_df, u_seed=999)
print(f"  {len(r_df):,} agents")

configs = [
    # label,  beta_fam, beta_work, beta_school, beta_rand, beta_same
    ("FULL",  0.8,      0.1,       0.04,        0.01,      0.0005),
    ("FWS",   0.8,      0.1,       0.04,        0.0,       0.0),
    ("FW",    0.8,      0.1,       0.0,         0.0,       0.0),
    ("FAM",   0.8,      0.0,       0.0,         0.0,       0.0),
]

print(f"\nRunning {N_SEEDS} seeds x {len(configs)} configs x 2 scenarios (R + U) ...")
print()

rows = []
for label, bf, bw, bs, br, bsa in configs:
    r_ars, u_ars = [], []
    r_peaks, u_peaks = [], []
    for seed in range(N_SEEDS):
        ar_r, pk_r, _ = run_scenario(r_df, bf, bw, bs, br, bsa, seed)
        ar_u, pk_u, _ = run_scenario(u_df, bf, bw, bs, br, bsa, seed)
        r_ars.append(ar_r); u_ars.append(ar_u)
        r_peaks.append(pk_r); u_peaks.append(pk_u)

    r_ar_m  = 100 * np.mean(r_ars)
    u_ar_m  = 100 * np.mean(u_ars)
    diff_ar = u_ar_m - r_ar_m
    r_pk_m  = np.mean(r_peaks)
    u_pk_m  = np.mean(u_peaks)
    diff_pk = 100 * (u_pk_m - r_pk_m) / r_pk_m

    rows.append((label, r_ar_m, u_ar_m, diff_ar, r_pk_m, u_pk_m, diff_pk))
    print(f"{label:6s}  R_AR={r_ar_m:6.2f}%  U_AR={u_ar_m:6.2f}%  diff={diff_ar:+.3f}pp"
          f"  |  R_peak={r_pk_m:.0f}  U_peak={u_pk_m:.0f}  diff%={diff_pk:+.1f}%")

print()
print("=== Summary ===")
print(f"{'Config':<6}  {'R AR':>8}  {'U AR':>8}  {'U-R':>9}  {'R peak':>8}  {'U peak':>8}  {'peak diff%':>10}")
print("-" * 70)
for label, r_ar_m, u_ar_m, diff_ar, r_pk_m, u_pk_m, diff_pk in rows:
    print(f"{label:<6}  {r_ar_m:>7.3f}%  {u_ar_m:>7.3f}%  {diff_ar:>+8.4f}pp"
          f"  {r_pk_m:>8.0f}  {u_pk_m:>8.0f}  {diff_pk:>+9.1f}%")

# Restore published values so other scripts importing re_mod are not affected
re_mod.BETA_FAMILY   = 0.8
re_mod.BETA_WORK     = 0.1
re_mod.BETA_SCHOOL   = 0.04
re_mod.BETA_RANDOM   = 0.01
re_mod.BETA_SAME_AGE = 0.0005

# Save results
out = pd.DataFrame(rows, columns=['config','R_AR_pct','U_AR_pct','diff_AR_pp',
                                   'R_peak','U_peak','peak_diff_pct'])
out.to_csv(os.path.join(BASE, 'diagnostic_saturation_results.csv'), index=False)
print("\nSaved: diagnostic_saturation_results.csv")
