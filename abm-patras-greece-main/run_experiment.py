"""Section 7 ABM experiment: R vs U comparison, 50 replicates each.

Scenario R: full synthetic population with template-derived household structure.
Scenario U: same agents, same work/school layers, household membership randomised
            while preserving the empirical household-size distribution (U-size-matched,
            as described in manuscript Section 7).

SEIR parameters:
  BETA_FAMILY=0.0221 (primary calibrated value at SAR=20%, matches
    full_sweep_50rep.py's SAR-20% row), BETA_WORK=0.1, BETA_SCHOOL=0.04,
  BETA_RANDOM=0.01, BETA_SAME_AGE=0.0005, GAMMA=0.1, SIGMA=0.2
  total_steps=180, initial_infected=5

  NOTE: full_sweep_50rep.py is the canonical script for the multi-SAR
  (15/20/25/30%) sweep reported in the manuscript; this script reproduces
  only the single SAR=20% anchor row via its default BETA_FAMILY below.

Performance: only E/I agents are iterated each step (pure Python, no Mesa
scheduler overhead). Precomputed dicts for family/work/school/age groups.

Usage:
  python run_experiment.py               # full 50-replicate run
  python run_experiment.py --smoke-test  # 1 replicate each, 20 steps
"""
import sys
import os
import random
import time
import argparse
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

# ── SEIR parameters (do not change) ──────────────────────────────────────────
# BETA_FAMILY default is the primary calibrated value at SAR=20% (beta = 1-(1-0.20)**GAMMA
# = 0.0221), matching full_sweep_50rep.py's SAR-20% row. full_sweep_50rep.py is the
# canonical script for the full multi-SAR (15/20/25/30%) sweep used in the manuscript.
BETA_FAMILY   = 0.0221
BETA_WORK     = 0.1
BETA_SCHOOL   = 0.04
BETA_RANDOM   = 0.01
BETA_SAME_AGE = 0.0005
GAMMA         = 0.1
SIGMA         = 0.2
TOTAL_STEPS   = 180
INITIAL_INFECTED = 5

# contacts_per_day: POLYMOD (Mossong et al. 2008, PLOS Med) mean daily contacts
# by age group, normalised to Greek contact patterns.  interaction_probability =
# cpd / 109.69 (sum of all cpd values) — used only for the same-age layer.
AGE_GROUPS = {
    '0-4':   {'contacts_per_day': 10.21, 'interaction_probability': 0.093},
    '5-9':   {'contacts_per_day': 14.81, 'interaction_probability': 0.135},
    '10-14': {'contacts_per_day': 18.22, 'interaction_probability': 0.166},
    '15-19': {'contacts_per_day': 17.58, 'interaction_probability': 0.160},
    '20-29': {'contacts_per_day': 13.57, 'interaction_probability': 0.124},
    '30-39': {'contacts_per_day': 14.14, 'interaction_probability': 0.129},
    '40-49': {'contacts_per_day': 13.83, 'interaction_probability': 0.126},
    '50-59': {'contacts_per_day': 12.30, 'interaction_probability': 0.112},
    '60-69': {'contacts_per_day':  9.21, 'interaction_probability': 0.084},
    '70+':   {'contacts_per_day':  6.89, 'interaction_probability': 0.063},
}

# Pre-built per-age lookup (keyed by integer age)
_AGE_GROUP_CACHE = {}
def _get_age_group(age):
    if age in _AGE_GROUP_CACHE:
        return _AGE_GROUP_CACHE[age]
    for label in AGE_GROUPS:
        if label == '70+':
            break
        lo, hi = map(int, label.split('-'))
        if lo <= age <= hi:
            _AGE_GROUP_CACHE[age] = label
            return label
    _AGE_GROUP_CACHE[age] = '70+'
    return '70+'

# ── Lightweight agent (plain Python object) ───────────────────────────────────
class Agent:
    # __slots__ cuts memory ~40% vs a regular dict-backed object; with 215k
    # instances the difference is significant for in-memory simulation speed.
    __slots__ = ('uid', 'age', 'gender', 'family_id', 'work_id', 'school_id',
                 'status', 'next_status')
    def __init__(self, uid, age, gender, family_id, work_id, school_id, status):
        self.uid        = uid
        self.age        = age
        self.gender     = gender
        self.family_id  = family_id
        self.work_id    = work_id
        self.school_id  = school_id
        self.status     = status
        self.next_status = status


# ── Model ─────────────────────────────────────────────────────────────────────
def _build_model(agents_df):
    """Build list of Agent objects and precomputed contact indices."""
    agents = []
    for uid, row in enumerate(agents_df.itertuples(index=False)):
        agents.append(Agent(
            uid        = uid,
            age        = int(row.Age),
            gender     = int(row.Gender),
            family_id  = int(row.Family_ID),
            work_id    = int(row.Work_ID),
            school_id  = int(row.School_ID),
            status     = str(row.Infection_Status),
        ))

    by_family  = defaultdict(list)
    by_work    = defaultdict(list)
    by_school  = defaultdict(list)
    by_age     = defaultdict(list)
    # S-count guards: skip group iteration when no S members remain
    s_in_work   = defaultdict(int)
    s_in_school = defaultdict(int)

    for a in agents:
        by_family[a.family_id].append(a)
        if a.work_id   != -1:
            by_work[a.work_id].append(a)
            s_in_work[a.work_id] += 1
        if a.school_id != -1:
            by_school[a.school_id].append(a)
            s_in_school[a.school_id] += 1
        by_age[a.age].append(a)

    return agents, by_family, by_work, by_school, by_age, s_in_work, s_in_school


# ── Single step (iterates only E/I agents) ────────────────────────────────────
def _do_step(active, agents, by_family, by_work, by_school, by_age,
             s_in_work, s_in_school, beta_family=BETA_FAMILY):
    """Process one day. Returns (new_active, new_exposed_count)."""
    for a in active:
        a.next_status = a.status

    random.shuffle(active)
    new_exposed = 0
    # Collect newly exposed agents separately; apply status after the full loop
    # so an agent exposed mid-step cannot infect others in the same step.
    newly_exposed = []

    def expose(m):
        nonlocal new_exposed
        m.next_status = 'E'
        newly_exposed.append(m)
        new_exposed += 1

    for a in active:
        if a.status == 'E':
            if random.random() < SIGMA:
                a.next_status = 'I'
            continue

        # a.status == 'I'
        for m in by_family[a.family_id]:
            if m.status == 'S' and m.next_status != 'E' and random.random() < beta_family:
                expose(m)

        # S-count guard: skip group entirely when no S members remain
        if a.work_id != -1 and s_in_work[a.work_id] > 0:
            for m in by_work[a.work_id]:
                if m.status == 'S' and m.next_status != 'E' and random.random() < BETA_WORK:
                    expose(m)

        if a.school_id != -1 and s_in_school[a.school_id] > 0:
            for m in by_school[a.school_id]:
                if m.status == 'S' and m.next_status != 'E' and random.random() < BETA_SCHOOL:
                    expose(m)

        if random.random() < BETA_RANDOM:
            rnd = agents[random.randrange(len(agents))]
            if rnd.status == 'S' and rnd.next_status != 'E':
                expose(rnd)

        # Same-age layer: sample exactly cpd contacts (independent of cohort size).
        # Performance note: building a filtered list [p for p in cohort if p is not a]
        # is O(cohort_size ~2700) per active agent. At peak infection with 60K+ active
        # agents this costs 60K×2700 = 162M iterations/step. Instead, sample cpd+1
        # items directly from the raw cohort (O(cpd) via Python's reservoir sampler)
        # and skip self inline — self appears in a draw of 19 from 2700 with p≈0.7%.
        ag     = _get_age_group(a.age)
        cpd    = int(round(AGE_GROUPS[ag]['contacts_per_day']))
        cohort = by_age[a.age]
        n_avail = len(cohort) - 1          # excluding self
        if cpd > 0 and n_avail > 0:
            draw = random.sample(cohort, min(cpd + 1, len(cohort)))
            count = 0
            for peer in draw:
                if peer is a:
                    continue
                if peer.status == 'S' and peer.next_status != 'E':
                    if random.random() < BETA_SAME_AGE:
                        expose(peer)
                count += 1
                if count >= cpd:
                    break

        if random.random() < GAMMA:
            a.next_status = 'R'

    # Apply transitions for active agents (E→I or I→R)
    new_active = []
    for a in active:
        a.status = a.next_status
        if a.status in ('E', 'I'):
            new_active.append(a)

    # Apply and enqueue newly exposed S→E agents; update S-count guards
    for a in newly_exposed:
        a.status = 'E'
        new_active.append(a)
        if a.work_id   != -1: s_in_work[a.work_id]   -= 1
        if a.school_id != -1: s_in_school[a.school_id] -= 1

    return new_active, new_exposed


# ── Scenario U construction ───────────────────────────────────────────────────
def build_u_agents(r_df, u_seed=999):
    """Return DataFrame with Family_IDs randomised (size-matched shuffle).
    Work_ID, School_ID, Age, Gender unchanged.
    """
    rng = np.random.default_rng(u_seed)

    hh_sizes = r_df.groupby('Family_ID').size().values.copy()
    rng.shuffle(hh_sizes)

    indices = np.arange(len(r_df))
    rng.shuffle(indices)

    new_fid = np.empty(len(r_df), dtype=int)
    cursor = 0
    for new_id, sz in enumerate(hh_sizes):
        new_fid[indices[cursor:cursor + sz]] = new_id
        cursor += sz

    u_df = r_df.copy()
    u_df['Family_ID'] = new_fid
    return u_df


# ── Single replicate ──────────────────────────────────────────────────────────
def run_once(agents_df, seed, total_steps=TOTAL_STEPS, beta_family=BETA_FAMILY):
    """Run one replicate. Returns dict with metrics and daily_series list."""
    random.seed(seed)
    np.random.seed(seed)

    agents, by_family, by_work, by_school, by_age, s_in_work, s_in_school = _build_model(agents_df)
    N = len(agents)

    # Initial seeding: 5 random agents become I; update S-count guards
    rng_seed = np.random.default_rng(seed)
    initial_ids = rng_seed.choice(N, size=INITIAL_INFECTED, replace=False)
    active = []
    for idx in initial_ids:
        agents[idx].status = 'I'
        agents[idx].next_status = 'I'
        active.append(agents[idx])
        a = agents[idx]
        if a.work_id   != -1: s_in_work[a.work_id]   -= 1
        if a.school_id != -1: s_in_school[a.school_id] -= 1

    daily_new = []
    for step in range(total_steps):
        active, new_exp = _do_step(active, agents, by_family, by_work, by_school,
                                   by_age, s_in_work, s_in_school, beta_family)
        daily_new.append(new_exp)
        if not active:
            daily_new.extend([0] * (total_steps - step - 1))
            break

    S_final = sum(1 for a in agents if a.status == 'S')
    attack_rate    = 1.0 - S_final / N
    peak_incidence = max(daily_new)
    day_of_peak    = int(np.argmax(daily_new))

    return {
        'seed':           seed,
        'peak_incidence': peak_incidence,
        'attack_rate':    attack_rate,
        'day_of_peak':    day_of_peak,
        'daily_new':      daily_new,
    }


# ── Parallel experiment harness ───────────────────────────────────────────────
def run_experiment(n_seeds=50, total_steps=TOTAL_STEPS, n_jobs=4, out_dir=None):
    BASE = os.path.dirname(os.path.abspath(__file__))
    if out_dir is None:
        out_dir = os.path.join(BASE, 'runs')
    os.makedirs(out_dir, exist_ok=True)

    csv_path = os.path.join(BASE, 'agents_patras.csv')
    print(f"Loading {csv_path} ...")
    r_df = pd.read_csv(csv_path)
    print(f"  {len(r_df):,} agents loaded.")

    print("Building U (size-matched shuffle, u_seed=999) ...")
    u_df = build_u_agents(r_df, u_seed=999)
    print(f"  U households: {u_df['Family_ID'].nunique():,}")

    results = {'R': [], 'U': []}

    def run_pair(seed):
        t0 = time.time()
        r_res = run_once(r_df, seed=seed, total_steps=total_steps)
        u_res = run_once(u_df, seed=seed, total_steps=total_steps)
        elapsed = time.time() - t0
        print(f"  seed {seed:2d}: R peak={r_res['peak_incidence']:6d} "
              f"AR={r_res['attack_rate']:.4f}  "
              f"U peak={u_res['peak_incidence']:6d} "
              f"AR={u_res['attack_rate']:.4f}  ({elapsed:.1f}s)")
        # Write per-replicate CSVs immediately so a mid-run crash loses only the
        # current pair, not the entire run.
        pd.DataFrame({'step': range(total_steps),
                      'new_exposed': r_res['daily_new']}).to_csv(
            os.path.join(out_dir, f'R_seed{seed}.csv'), index=False)
        pd.DataFrame({'step': range(total_steps),
                      'new_exposed': u_res['daily_new']}).to_csv(
            os.path.join(out_dir, f'U_seed{seed}.csv'), index=False)
        return r_res, u_res

    print(f"\nRunning {n_seeds} replicates x 2 scenarios ({total_steps} steps each) ...")
    wall_start = time.time()

    if n_jobs > 1:
        try:
            from joblib import Parallel, delayed
            pairs = Parallel(n_jobs=n_jobs, backend='loky')(
                delayed(run_pair)(s) for s in range(n_seeds))
        except ImportError:
            print("  joblib not available; running sequentially.")
            pairs = [run_pair(s) for s in range(n_seeds)]
    else:
        pairs = [run_pair(s) for s in range(n_seeds)]

    for r_res, u_res in pairs:
        results['R'].append(r_res)
        results['U'].append(u_res)

    wall_elapsed = time.time() - wall_start
    print(f"\nAll runs complete in {wall_elapsed:.1f}s  "
          f"({wall_elapsed/n_seeds:.1f}s per pair)")

    # Sort results by seed
    results['R'].sort(key=lambda x: x['seed'])
    results['U'].sort(key=lambda x: x['seed'])

    # ── Statistics ────────────────────────────────────────────────────────────
    metrics = ['peak_incidence', 'attack_rate', 'day_of_peak']
    labels  = ['Peak daily incidence', 'Final attack rate', 'Day of peak']

    print("\n=== SECTION 7 TABLE ===")
    hdr = f"{'Metric':<25} {'R mean (SD)':>22} {'U mean (SD)':>22} {'p':>8} {'test':>17}"
    print(hdr)
    print("-" * len(hdr))

    table_rows = []
    for metric, label in zip(metrics, labels):
        r_vals = np.array([r[metric] for r in results['R']])
        u_vals = np.array([r[metric] for r in results['U']])
        r_m, r_s = float(np.mean(r_vals)), float(np.std(r_vals, ddof=1))
        u_m, u_s = float(np.mean(u_vals)), float(np.std(u_vals, ddof=1))

        diff = r_vals - u_vals
        if np.any(diff != 0):
            _, pval = wilcoxon(r_vals, u_vals)
            test_name = 'Wilcoxon paired'
        else:
            pval = 1.0
            test_name = 'tied'

        if metric == 'attack_rate':
            r_str = f"{r_m:.4f} ({r_s:.4f})"
            u_str = f"{u_m:.4f} ({u_s:.4f})"
        else:
            r_str = f"{r_m:.1f} ({r_s:.1f})"
            u_str = f"{u_m:.1f} ({u_s:.1f})"

        print(f"{label:<25} {r_str:>22} {u_str:>22} {pval:>8.4f} {test_name:>17}")
        table_rows.append({'metric': label, 'R_mean': r_m, 'R_sd': r_s,
                           'U_mean': u_m, 'U_sd': u_s, 'p_value': pval,
                           'test': test_name})

    # Save per-run summary
    summary_rows = []
    for scen, res_list in results.items():
        for r in res_list:
            summary_rows.append({'scenario': scen, 'seed': r['seed'],
                                 'peak_incidence': r['peak_incidence'],
                                 'attack_rate':    r['attack_rate'],
                                 'day_of_peak':    r['day_of_peak']})
    summary_df = pd.DataFrame(summary_rows)
    summary_path = os.path.join(BASE, 'section7_summary.csv')
    summary_df.to_csv(summary_path, index=False)
    print(f"\nSaved: {summary_path}")

    # Save markdown table
    md_path = os.path.join(BASE, 'section7_table.md')
    with open(md_path, 'w') as f:
        f.write("# Section 7 ABM Results\n\n")
        f.write(f"50 replicates per scenario; seeds 0–{n_seeds-1}; "
                f"paired Wilcoxon signed-rank test.\n")
        f.write("U scenario: size-matched household shuffle (u_seed=999).\n\n")
        f.write("| Metric | R mean (SD) | U mean (SD) | p-value | Test |\n")
        f.write("|--------|-------------|-------------|---------|------|\n")
        for row in table_rows:
            if 'attack' in row['metric'].lower():
                r_str = f"{row['R_mean']:.4f} ({row['R_sd']:.4f})"
                u_str = f"{row['U_mean']:.4f} ({row['U_sd']:.4f})"
            else:
                r_str = f"{row['R_mean']:.1f} ({row['R_sd']:.1f})"
                u_str = f"{row['U_mean']:.1f} ({row['U_sd']:.1f})"
            f.write(f"| {row['metric']} | {r_str} | {u_str} "
                    f"| {row['p_value']:.4f} | {row['test']} |\n")
    print(f"Saved: {md_path}")

    # Write run log
    log_path = os.path.join(BASE, 'RUN_LOG.md')
    with open(log_path, 'w') as f:
        f.write("# ABM Experiment Run Log\n\n")
        f.write(f"- **Mesa version**: not used for scheduler (pure Python active-agent loop)\n")
        f.write(f"- **Seeds**: 0 to {n_seeds-1} (paired R/U)\n")
        f.write(f"- **Initial seeding rule**: 5 random agents set to I, "
                f"chosen with np.random.default_rng(seed)\n")
        f.write(f"- **U definition**: size-matched shuffle (u_seed=999); "
                f"household membership randomised, work/school/age unchanged\n")
        f.write(f"- **Total steps**: {total_steps}\n")
        f.write(f"- **Wall-clock**: {wall_elapsed:.1f}s "
                f"({wall_elapsed/n_seeds:.1f}s per pair)\n")
        f.write(f"- **SEIR params**: BETA_FAMILY={BETA_FAMILY}, "
                f"BETA_WORK={BETA_WORK}, BETA_SCHOOL={BETA_SCHOOL}, "
                f"BETA_RANDOM={BETA_RANDOM}, BETA_SAME_AGE={BETA_SAME_AGE}, "
                f"GAMMA={GAMMA}, SIGMA={SIGMA}\n")
        f.write(f"- **Population**: agents_patras.csv, {len(r_df):,} agents, {r_df['Family_ID'].nunique():,} households\n")
    print(f"Saved: {log_path}")

    return table_rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true',
                        help='Run 1 replicate each scenario, 20 steps only')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()

    BASE = os.path.dirname(os.path.abspath(__file__))

    if args.smoke_test:
        print("=== SMOKE TEST: 1 replicate, 20 steps ===")
        r_df = pd.read_csv(os.path.join(BASE, 'agents_patras.csv'))
        u_df = build_u_agents(r_df, u_seed=999)
        t0 = time.time()
        r = run_once(r_df, seed=0, total_steps=20)
        u = run_once(u_df, seed=0, total_steps=20)
        elapsed = time.time() - t0
        print(f"Smoke test passed in {elapsed:.1f}s")
        print(f"R: peak={r['peak_incidence']}, AR={r['attack_rate']:.4f}, "
              f"day_of_peak={r['day_of_peak']}")
        print(f"U: peak={u['peak_incidence']}, AR={u['attack_rate']:.4f}, "
              f"day_of_peak={u['day_of_peak']}")
        est_per_pair = elapsed / 20 * TOTAL_STEPS
        print(f"Est. per full run pair (lower bound — pre-exponential phase): "
              f"{est_per_pair:.0f}s  "
              f"(50 pairs on {args.jobs} cores: {50*est_per_pair/args.jobs:.0f}s)")
    else:
        run_experiment(n_seeds=50, total_steps=TOTAL_STEPS, n_jobs=args.jobs)
