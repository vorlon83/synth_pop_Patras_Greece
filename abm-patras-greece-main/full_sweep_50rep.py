"""
full_sweep_50rep.py - 50-replicate SAR sweep, all 5 layers, corrected same-age.

Literature anchor: Madewell et al. (2021) JAMA Netw Open 3(12):e2031756
  Pooled COVID-19 household SAR: 18.8% (95% CI 15.4-22.2%)

SAR targets declared before seeing output: 15%, 20%, 25%, 30%.

Per SAR:
  - 50 paired seeds (R vs U)
  - Wilcoxon signed-rank on paired differences for all key metrics
  - Per-status AR (employed / student / inactive)
  - Curve shape check (validates day_of_peak as a meaningful summary)
  - Mean epidemic curves saved for plotting

Outputs:
  full_sweep_50rep_summary.csv  -- 4-row summary table
  full_sweep_50rep_curves.csv   -- mean daily incidence per SAR x scenario
  full_sweep_50rep_perrun.csv   -- per-seed data (400 rows)
"""
import sys, os, time, random
import numpy as np
import pandas as pd
from collections import defaultdict
from scipy.stats import wilcoxon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment as run_exp

BASE = os.path.dirname(os.path.abspath(__file__))

CATS         = ['employed', 'student', 'inactive']
SAR_TARGETS  = [0.15, 0.20, 0.25, 0.30]
N_SEEDS      = 50
TOTAL_STEPS  = run_exp.TOTAL_STEPS  # 180


# ── Helpers ───────────────────────────────────────────────────────────────────

def sar_to_beta(sar):
    # Derives the per-contact household transmission probability from a target SAR.
    # Under geometric escape: SAR = 1 - (1-β)^(T) where T = 1/GAMMA (mean infectious
    # days).  Inverting: β = 1 - (1-SAR)^GAMMA.  With GAMMA=0.1, T=10 days.
    return 1.0 - (1.0 - sar) ** run_exp.GAMMA


def activity_category(work_id, school_id):
    if work_id   != -1: return 'employed'
    if school_id != -1: return 'student'
    return 'inactive'


def per_status_ar(agents):
    counts = defaultdict(lambda: [0, 0])
    for a in agents:
        cat = activity_category(a.work_id, a.school_id)
        counts[cat][1] += 1
        if a.status != 'S':
            counts[cat][0] += 1
    return {cat: (v[0] / v[1] if v[1] > 0 else 0.0) for cat, v in counts.items()}


def run_once_tracked(agents_df, seed, total_steps=TOTAL_STEPS,
                     beta_family=run_exp.BETA_FAMILY):
    """run_once returning (metrics_dict, agents_list) for per-status analysis."""
    random.seed(seed)
    np.random.seed(seed)
    agents, by_fam, by_work, by_school, by_age, s_in_work, s_in_school = \
        run_exp._build_model(agents_df)
    N = len(agents)
    rng = np.random.default_rng(seed)
    init_ids = rng.choice(N, size=run_exp.INITIAL_INFECTED, replace=False)
    active = []
    for idx in init_ids:
        agents[idx].status      = 'I'
        agents[idx].next_status = 'I'
        active.append(agents[idx])
        a = agents[idx]
        if a.work_id   != -1: s_in_work[a.work_id]   -= 1
        if a.school_id != -1: s_in_school[a.school_id] -= 1
    daily_new = []
    for step in range(total_steps):
        active, new_exp = run_exp._do_step(active, agents, by_fam, by_work,
                                           by_school, by_age, s_in_work,
                                           s_in_school, beta_family)
        daily_new.append(new_exp)
        if not active:
            daily_new.extend([0] * (total_steps - step - 1))
            break
    S_final = sum(1 for a in agents if a.status == 'S')
    return {
        'attack_rate':    1.0 - S_final / N,
        'peak_incidence': max(daily_new),
        'day_of_peak':    int(np.argmax(daily_new)),
        'daily_new':      daily_new,
    }, agents


def count_major_peaks(daily_new, threshold=0.15):
    """Local maxima at or above threshold x global max. >1 means multi-peak."""
    arr = np.array(daily_new, dtype=float)
    pmax = arr.max()
    if pmax == 0:
        return 0
    min_h = threshold * pmax
    n = 0
    for i in range(1, len(arr) - 1):
        if arr[i] > arr[i-1] and arr[i] > arr[i+1] and arr[i] >= min_h:
            n += 1
    return n


def wpval(a, b):
    diff = np.asarray(a) - np.asarray(b)
    if np.all(diff == 0):
        return 1.0
    _, p = wilcoxon(a, b)
    return float(p)


# ── Load agents ───────────────────────────────────────────────────────────────
print("Loading agents ...")
r_df = pd.read_csv(os.path.join(BASE, 'agents_patras.csv'))
u_df = run_exp.build_u_agents(r_df, u_seed=999)
print(f"  {len(r_df):,} agents  |  {r_df['Family_ID'].nunique():,} R households")
print(f"  SAR targets: {[f'{int(100*s)}%' for s in SAR_TARGETS]}  n_seeds={N_SEEDS}")
print()

# ── Main sweep ────────────────────────────────────────────────────────────────
wall_start   = time.time()
all_per_run  = []
summary_rows = []
curve_cols   = {'step': list(range(TOTAL_STEPS))}

for sar in SAR_TARGETS:
    beta = sar_to_beta(sar)
    tag = f"SAR{int(100*sar)}"

    r_ars,  u_ars  = [], []
    r_peaks, u_peaks = [], []
    r_days,  u_days  = [], []
    r_inact, u_inact = [], []
    r_empl,  u_empl  = [], []
    r_stud,  u_stud  = [], []
    r_peaks_n, u_peaks_n = [], []   # peak-shape counts
    r_curve = np.zeros(TOTAL_STEPS)
    u_curve = np.zeros(TOTAL_STEPS)

    t0 = time.time()
    for seed in range(N_SEEDS):
        rr, r_agt = run_once_tracked(r_df, seed=seed, beta_family=beta)
        ur, u_agt = run_once_tracked(u_df, seed=seed, beta_family=beta)

        r_ars.append(rr['attack_rate']); u_ars.append(ur['attack_rate'])
        r_peaks.append(rr['peak_incidence']); u_peaks.append(ur['peak_incidence'])
        r_days.append(rr['day_of_peak']); u_days.append(ur['day_of_peak'])
        r_curve += np.array(rr['daily_new'])
        u_curve += np.array(ur['daily_new'])
        r_peaks_n.append(count_major_peaks(rr['daily_new']))
        u_peaks_n.append(count_major_peaks(ur['daily_new']))

        r_ps = per_status_ar(r_agt)
        u_ps = per_status_ar(u_agt)
        r_inact.append(r_ps.get('inactive', 0.0))
        u_inact.append(u_ps.get('inactive', 0.0))
        r_empl.append(r_ps.get('employed', 0.0))
        u_empl.append(u_ps.get('employed', 0.0))
        r_stud.append(r_ps.get('student', 0.0))
        u_stud.append(u_ps.get('student', 0.0))

        all_per_run.append({
            'SAR_pct': int(100*sar), 'beta_family': round(beta, 4), 'seed': seed,
            'R_AR': rr['attack_rate'], 'U_AR': ur['attack_rate'],
            'R_peak': rr['peak_incidence'], 'U_peak': ur['peak_incidence'],
            'R_day': rr['day_of_peak'], 'U_day': ur['day_of_peak'],
            'R_inactive_AR': r_ps.get('inactive', 0.0),
            'U_inactive_AR': u_ps.get('inactive', 0.0),
            'R_employed_AR': r_ps.get('employed', 0.0),
            'U_employed_AR': u_ps.get('employed', 0.0),
            'R_student_AR':  r_ps.get('student',  0.0),
            'U_student_AR':  u_ps.get('student',  0.0),
        })

        if (seed + 1) % 10 == 0:
            elapsed = time.time() - t0
            print(f"  {tag} [{seed+1:2d}/{N_SEEDS}]  "
                  f"R={100*np.mean(r_ars):.2f}%  U={100*np.mean(u_ars):.2f}%  "
                  f"inactive U-R={100*(np.mean(u_inact)-np.mean(r_inact)):+.2f}pp  "
                  f"[{elapsed:.0f}s]")

    elapsed = time.time() - t0
    r_curve /= N_SEEDS
    u_curve /= N_SEEDS
    curve_cols[f'R_{tag}'] = r_curve.tolist()
    curve_cols[f'U_{tag}'] = u_curve.tolist()

    # Arrays for stats
    ra, ua = np.array(r_ars),  np.array(u_ars)
    ri, ui = np.array(r_inact), np.array(u_inact)
    re_, ue = np.array(r_empl), np.array(u_empl)
    rs, us = np.array(r_stud), np.array(u_stud)
    rp, up = np.array(r_peaks), np.array(u_peaks)
    rd, ud = np.array(r_days),  np.array(u_days)

    multi_r = sum(1 for n in r_peaks_n if n > 1)
    multi_u = sum(1 for n in u_peaks_n if n > 1)

    print()
    print(f"{'='*72}")
    print(f"{tag}  beta_family={beta:.4f}  "
          f"[{elapsed:.0f}s total, {elapsed/N_SEEDS:.1f}s/pair]")
    print(f"  Curve shape: R multi-peak {multi_r}/{N_SEEDS}  "
          f"U multi-peak {multi_u}/{N_SEEDS}")
    print()
    print(f"  {'Metric':<22}  {'R mean':>9}  {'(SD)':>8}  "
          f"{'U mean':>9}  {'(SD)':>8}  {'U-R':>8}  {'p':>8}")
    print(f"  {'-'*76}")

    def row(label, rv, uv, pct=True):
        sc = 100 if pct else 1
        rm, rs_ = sc*float(np.mean(rv)), sc*float(np.std(rv, ddof=1))
        um, us_ = sc*float(np.mean(uv)), sc*float(np.std(uv, ddof=1))
        diff = um - rm
        p = wpval(rv, uv)
        sfx = '%' if pct else ''
        print(f"  {label:<22}  {rm:>8.2f}{sfx}  ({rs_:>6.2f})  "
              f"{um:>8.2f}{sfx}  ({us_:>6.2f})  {diff:>+7.2f}{sfx}  {p:>8.4f}")
        return rm, rs_, um, us_, diff, p

    r_ar_m,  r_ar_s,  u_ar_m,  u_ar_s,  ar_diff,   ar_p   = row('Overall AR',     ra, ua)
    r_in_m,  r_in_s,  u_in_m,  u_in_s,  in_diff,   in_p   = row('Inactive AR',    ri, ui)
    r_em_m,  r_em_s,  u_em_m,  u_em_s,  em_diff,   em_p   = row('Employed AR',    re_, ue)
    r_st_m,  r_st_s,  u_st_m,  u_st_s,  st_diff,   st_p   = row('Student AR',     rs, us)
    r_pk_m,  r_pk_s,  u_pk_m,  u_pk_s,  pk_diff,   pk_p   = row('Peak incidence', rp, up, pct=False)
    r_dy_m,  r_dy_s,  u_dy_m,  u_dy_s,  dy_diff,   dy_p   = row('Day of peak',    rd, ud, pct=False)
    print()

    # day_diff: R-U (positive = R peaks LATER, as expected for structured pop)
    day_delay = r_dy_m - u_dy_m
    peak_drop_pct = 100.0 * (u_pk_m - r_pk_m) / u_pk_m if u_pk_m > 0 else 0.0

    summary_rows.append({
        'SAR_pct': int(100*sar),
        'beta_family': round(beta, 4),
        # Overall AR
        'R_AR_mean': r_ar_m, 'R_AR_sd': r_ar_s,
        'U_AR_mean': u_ar_m, 'U_AR_sd': u_ar_s,
        'overall_UminusR_pp': ar_diff, 'overall_p': ar_p,
        # Inactive AR
        'R_inactive_mean': r_in_m, 'R_inactive_sd': r_in_s,
        'U_inactive_mean': u_in_m, 'U_inactive_sd': u_in_s,
        'inactive_UminusR_pp': in_diff, 'inactive_p': in_p,
        # Employed AR
        'R_employed_mean': r_em_m, 'R_employed_sd': r_em_s,
        'U_employed_mean': u_em_m, 'U_employed_sd': u_em_s,
        'employed_UminusR_pp': em_diff, 'employed_p': em_p,
        # Student AR
        'R_student_mean': r_st_m, 'R_student_sd': r_st_s,
        'U_student_mean': u_st_m, 'U_student_sd': u_st_s,
        'student_UminusR_pp': st_diff, 'student_p': st_p,
        # Peak incidence
        'R_peak_mean': r_pk_m, 'R_peak_sd': r_pk_s,
        'U_peak_mean': u_pk_m, 'U_peak_sd': u_pk_s,
        'peak_UminusR': pk_diff, 'peak_p': pk_p,
        'peak_drop_pct': peak_drop_pct,
        # Day of peak
        'R_day_mean': r_dy_m, 'R_day_sd': r_dy_s,
        'U_day_mean': u_dy_m, 'U_day_sd': u_dy_s,
        'day_RminusU': day_delay, 'day_p': dy_p,
        # Curve shape
        'R_multi_peak': multi_r, 'U_multi_peak': multi_u,
    })

# ── Save outputs ──────────────────────────────────────────────────────────────
wall_elapsed = time.time() - wall_start
print(f"{'='*72}")
print(f"All done. Total: {wall_elapsed:.0f}s ({wall_elapsed/60:.1f} min)")
print()

out_summary = os.path.join(BASE, 'full_sweep_50rep_summary.csv')
pd.DataFrame(summary_rows).to_csv(out_summary, index=False)
print(f"Saved: {out_summary}")

out_curves = os.path.join(BASE, 'full_sweep_50rep_curves.csv')
pd.DataFrame(curve_cols).to_csv(out_curves, index=False)
print(f"Saved: {out_curves}")

out_perrun = os.path.join(BASE, 'full_sweep_50rep_perrun.csv')
pd.DataFrame(all_per_run).to_csv(out_perrun, index=False)
print(f"Saved: {out_perrun}")

# ── Cross-SAR monotonicity check ──────────────────────────────────────────────
print()
print("MONOTONICITY CHECK across SAR range:")
print(f"{'SAR':>5}  {'overall U-R':>12}  {'inactive U-R':>13}  "
      f"{'R peak day':>11}  {'R peak delay':>13}  {'R peak drop%':>13}")
for row in summary_rows:
    print(f"{row['SAR_pct']:>4}%  "
          f"{row['overall_UminusR_pp']:>+11.2f}pp  "
          f"{row['inactive_UminusR_pp']:>+12.2f}pp  "
          f"{row['R_day_mean']:>10.1f}d  "
          f"{row['day_RminusU']:>+12.1f}d  "
          f"{row['peak_drop_pct']:>+12.1f}%")

print()
print("DONE.")
