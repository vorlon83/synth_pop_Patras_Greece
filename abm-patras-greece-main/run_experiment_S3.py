"""S3-vs-shuffle robustness experiment (reviewer rebuttal).

Repeats the published S1 R-vs-U 50-replicate paired SEIR contrast at the
primary SAR=20% anchor (beta_family=0.0221), but on the S3 (WG-reweighted)
household population instead of S1. S3 has a singleton rate of 33.3%
(vs. S1's 23.6%), much closer to the WG-observed 32.2% -- this tests whether
the "assortative segregation" effect (inactive-subpopulation attack-rate gap,
peak delay, peak reduction under structured vs. shuffled households) found
with S1 is an artifact of S1's known singleton-rate under-production, or a
robust structural finding that persists/grows under a more Greek-realistic
household structure.

This script reuses the exact same simulation loop as the published S1 numbers
(imports run_experiment.py's _build_model/_do_step/run_once/build_u_agents
unchanged). The per-status-AR / peak-shape / SAR->beta helper functions are
copied verbatim from full_sweep_50rep.py (sar_to_beta, activity_category,
per_status_ar, run_once_tracked, count_major_peaks, wpval) rather than
imported as a module, because full_sweep_50rep.py has unguarded top-level
code (no `if __name__ == '__main__':`) that executes its own full 4-SAR x
50-replicate S1 sweep as an import side-effect -- `import full_sweep_50rep`
would silently run ~30-100 minutes of unrelated S1 computation before this
script's own code ever ran. Nothing in the SEIR mechanics is reimplemented;
only these small pure-function helpers are duplicated.

Population: agents_patras_s3.csv (built by build_agents_s3.py from
data/synthpop/patras_households_s3.json, the S3 = WG-reweighted household
population, generated via reweight_s3.py's household_compositions_s3.json
templates run through the IPF pipeline at PIPELINE_SEED=42, i.e. the same
seed as the S1 canonical population).

Scenario U (shuffle): build_u_agents(s3_df, u_seed=999) -- identical
methodology (size-matched household shuffle) and identical u_seed to the
published S1 Scenario U.

Outputs:
  s3_vs_shuffle_50rep_perrun.csv  -- per-seed data (50 rows)
  s3_vs_shuffle_50rep_summary.csv -- 1-row summary (SAR=20% only)
  s3_vs_shuffle_50rep.csv         -- alias/copy of perrun, task-requested name
  S3_RUN_LOG.md                  -- run metadata
"""
import sys, os, time, random
import numpy as np
import pandas as pd
from collections import defaultdict
from scipy.stats import wilcoxon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment as run_exp

BASE = os.path.dirname(os.path.abspath(__file__))

SAR_TARGET  = 0.20
N_SEEDS     = 50
TOTAL_STEPS = run_exp.TOTAL_STEPS  # 180


# ── Helpers copied verbatim from full_sweep_50rep.py (see module docstring for
#    why these are duplicated instead of imported) ────────────────────────────

def sar_to_beta(sar):
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


def main():
    beta = sar_to_beta(SAR_TARGET)  # = 0.0221 for SAR=20%
    print(f"S3-vs-shuffle robustness experiment: SAR={int(100*SAR_TARGET)}%  "
          f"beta_family={beta:.4f}")

    csv_path = os.path.join(BASE, 'agents_patras_s3.csv')
    print(f"Loading {csv_path} ...")
    r_df = pd.read_csv(csv_path)
    print(f"  {len(r_df):,} agents  |  {r_df['Family_ID'].nunique():,} S3 R households")

    print("Building S3-U (size-matched shuffle, u_seed=999) ...")
    u_df = run_exp.build_u_agents(r_df, u_seed=999)
    print(f"  S3-U households: {u_df['Family_ID'].nunique():,}")

    r_ars,  u_ars  = [], []
    r_peaks, u_peaks = [], []
    r_days,  u_days  = [], []
    r_inact, u_inact = [], []
    r_empl,  u_empl  = [], []
    r_stud,  u_stud  = [], []
    r_peaks_n, u_peaks_n = [], []
    r_curve = np.zeros(TOTAL_STEPS)
    u_curve = np.zeros(TOTAL_STEPS)
    all_per_run = []

    wall_start = time.time()
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
            'population': 'S3', 'SAR_pct': int(100*SAR_TARGET),
            'beta_family': round(beta, 4), 'seed': seed,
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
            print(f"  [{seed+1:2d}/{N_SEEDS}]  "
                  f"R={100*np.mean(r_ars):.2f}%  U={100*np.mean(u_ars):.2f}%  "
                  f"inactive U-R={100*(np.mean(u_inact)-np.mean(r_inact)):+.2f}pp  "
                  f"[{elapsed:.0f}s]")

    elapsed = time.time() - t0
    r_curve /= N_SEEDS
    u_curve /= N_SEEDS

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
    print(f"S3  SAR20  beta_family={beta:.4f}  "
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

    day_delay = r_dy_m - u_dy_m
    peak_drop_pct = 100.0 * (u_pk_m - r_pk_m) / u_pk_m if u_pk_m > 0 else 0.0

    summary_row = {
        'population': 'S3', 'SAR_pct': int(100*SAR_TARGET), 'beta_family': round(beta, 4),
        'R_AR_mean': r_ar_m, 'R_AR_sd': r_ar_s,
        'U_AR_mean': u_ar_m, 'U_AR_sd': u_ar_s,
        'overall_UminusR_pp': ar_diff, 'overall_p': ar_p,
        'R_inactive_mean': r_in_m, 'R_inactive_sd': r_in_s,
        'U_inactive_mean': u_in_m, 'U_inactive_sd': u_in_s,
        'inactive_UminusR_pp': in_diff, 'inactive_p': in_p,
        'R_employed_mean': r_em_m, 'R_employed_sd': r_em_s,
        'U_employed_mean': u_em_m, 'U_employed_sd': u_em_s,
        'employed_UminusR_pp': em_diff, 'employed_p': em_p,
        'R_student_mean': r_st_m, 'R_student_sd': r_st_s,
        'U_student_mean': u_st_m, 'U_student_sd': u_st_s,
        'student_UminusR_pp': st_diff, 'student_p': st_p,
        'R_peak_mean': r_pk_m, 'R_peak_sd': r_pk_s,
        'U_peak_mean': u_pk_m, 'U_peak_sd': u_pk_s,
        'peak_UminusR': pk_diff, 'peak_p': pk_p,
        'peak_drop_pct': peak_drop_pct,
        'R_day_mean': r_dy_m, 'R_day_sd': r_dy_s,
        'U_day_mean': u_dy_m, 'U_day_sd': u_dy_s,
        'day_RminusU': day_delay, 'day_p': dy_p,
        'R_multi_peak': multi_r, 'U_multi_peak': multi_u,
    }

    wall_elapsed = time.time() - wall_start

    perrun_path = os.path.join(BASE, 's3_vs_shuffle_50rep_perrun.csv')
    pd.DataFrame(all_per_run).to_csv(perrun_path, index=False)
    print(f"Saved: {perrun_path}")

    # Task-requested raw per-replicate filename (alias of perrun)
    raw_path = os.path.join(BASE, 's3_vs_shuffle_50rep.csv')
    pd.DataFrame(all_per_run).to_csv(raw_path, index=False)
    print(f"Saved: {raw_path}")

    summary_path = os.path.join(BASE, 's3_vs_shuffle_50rep_summary.csv')
    pd.DataFrame([summary_row]).to_csv(summary_path, index=False)
    print(f"Saved: {summary_path}")

    curve_path = os.path.join(BASE, 's3_vs_shuffle_50rep_curves.csv')
    pd.DataFrame({'step': list(range(TOTAL_STEPS)), 'R_SAR20': r_curve.tolist(),
                  'U_SAR20': u_curve.tolist()}).to_csv(curve_path, index=False)
    print(f"Saved: {curve_path}")

    log_path = os.path.join(BASE, 'S3_RUN_LOG.md')
    with open(log_path, 'w') as f:
        f.write("# S3-vs-shuffle robustness experiment run log\n\n")
        f.write("Reviewer rebuttal: repeats the published S1 R-vs-U 50-replicate paired SEIR\n")
        f.write("contrast at SAR=20% on the S3 (WG-reweighted) household population instead of S1,\n")
        f.write("to test whether the S1 segregation effect is an artifact of S1's under-produced\n")
        f.write("singleton rate (23.6% vs WG 32.2%) or a robust finding (S3 singleton rate 33.3%).\n\n")
        f.write(f"- **Population**: agents_patras_s3.csv, {len(r_df):,} agents, "
                f"{r_df['Family_ID'].nunique():,} households (S3, WG-reweighted templates, "
                f"PIPELINE_SEED=42, same seed as S1 canonical)\n")
        f.write(f"- **Seeds**: 0 to {N_SEEDS-1} (paired R/U)\n")
        f.write("- **Initial seeding rule**: 5 random agents set to I, chosen with "
                "np.random.default_rng(seed)\n")
        f.write("- **U definition**: size-matched shuffle (u_seed=999); household membership "
                "randomised, work/school/age unchanged -- identical methodology to published S1 "
                "Scenario U\n")
        f.write(f"- **Total steps**: {TOTAL_STEPS}\n")
        f.write(f"- **SAR**: 20% (primary manuscript anchor)  beta_family={beta:.4f}\n")
        f.write(f"- **SEIR params**: BETA_WORK={run_exp.BETA_WORK}, "
                f"BETA_SCHOOL={run_exp.BETA_SCHOOL}, BETA_RANDOM={run_exp.BETA_RANDOM}, "
                f"BETA_SAME_AGE={run_exp.BETA_SAME_AGE}, GAMMA={run_exp.GAMMA}, "
                f"SIGMA={run_exp.SIGMA}\n")
        f.write(f"- **Wall-clock**: {wall_elapsed:.1f}s ({wall_elapsed/N_SEEDS:.1f}s per pair)\n")
    print(f"Saved: {log_path}")

    print()
    print("DONE.")


if __name__ == '__main__':
    main()
