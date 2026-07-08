"""Compute conditional ABM statistics excluding stochastic-extinction replicates."""
import os
import pandas as pd
import numpy as np
from scipy.stats import wilcoxon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
df = pd.read_csv(os.path.join(ROOT, 'abm-patras-greece-main', 'full_sweep_50rep_perrun.csv'))

threshold = 0.01  # epidemic considered extinct if R_AR < 1%

for sar in [15, 20, 25, 30]:
    sub = df[df['SAR_pct'] == sar].copy()
    extinct_r = sub[sub['R_AR'] < threshold]
    print(f"SAR={sar}%: R extinct={len(extinct_r)} (seeds {list(extinct_r['seed'])})")

    cond = sub[sub['R_AR'] >= threshold]
    n = len(cond)
    r_ar = 100 * cond['R_AR'].values
    u_ar = 100 * cond['U_AR'].values
    r_in = 100 * cond['R_inactive_AR'].values
    u_in = 100 * cond['U_inactive_AR'].values
    r_pk = cond['R_peak'].values.astype(float)
    u_pk = cond['U_peak'].values.astype(float)
    r_dy = cond['R_day'].values.astype(float)
    u_dy = cond['U_day'].values.astype(float)

    _, p_ar = wilcoxon(r_ar, u_ar)
    _, p_pk = wilcoxon(r_pk, u_pk)
    _, p_dy = wilcoxon(r_dy, u_dy)

    print(f"  n={n}  R_AR={np.mean(r_ar):.2f}({np.std(r_ar,ddof=1):.2f})"
          f"  U_AR={np.mean(u_ar):.2f}({np.std(u_ar,ddof=1):.2f})"
          f"  dAR={np.mean(u_ar-r_ar):+.2f}  p_ar={p_ar:.4f}")
    print(f"  Inactive: R={np.mean(r_in):.2f}({np.std(r_in,ddof=1):.2f})"
          f"  U={np.mean(u_in):.2f}({np.std(u_in,ddof=1):.2f})"
          f"  delta={np.mean(u_in-r_in):+.2f}")
    print(f"  Peak: R={np.mean(r_pk):.0f}({np.std(r_pk,ddof=1):.0f})"
          f"  U={np.mean(u_pk):.0f}({np.std(u_pk,ddof=1):.0f})"
          f"  drop%={100*(np.mean(u_pk)-np.mean(r_pk))/np.mean(u_pk):.1f}  p_pk={p_pk:.4f}")
    print(f"  Day:  R={np.mean(r_dy):.1f}({np.std(r_dy,ddof=1):.1f})"
          f"  U={np.mean(u_dy):.1f}({np.std(u_dy,ddof=1):.1f})"
          f"  delay={np.mean(r_dy)-np.mean(u_dy):+.1f}  p_dy={p_dy:.4f}")
    # Per-employment-status gaps (for manuscript prose)
    r_em = 100 * cond['R_employed_AR'].values
    u_em = 100 * cond['U_employed_AR'].values
    r_st = 100 * cond['R_student_AR'].values
    u_st = 100 * cond['U_student_AR'].values
    print(f"  Employed gap:  {np.mean(u_em-r_em):+.2f} pp"
          f"  Student gap: {np.mean(u_st-r_st):+.2f} pp")
    # Ratio: inactive gap / overall gap
    ratio = (np.mean(u_in-r_in)) / (np.mean(u_ar-r_ar)) if np.mean(u_ar-r_ar) != 0 else float('nan')
    print(f"  Inactive/overall ratio: {ratio:.2f}x"
          f"  (manuscript claims 2.3-2.4x)")
    peak_drop = 100 * (np.mean(u_pk) - np.mean(r_pk)) / np.mean(u_pk) if np.mean(u_pk) > 0 else 0
    print(f"  Peak drop: {peak_drop:.1f}%  delay: {np.mean(r_dy)-np.mean(u_dy):.1f}d")
    print()
