"""Activity-status diagnostic for Section 7.

Tests the assortative-segregation mechanism prediction:

  PASS signature (confirms mechanism):
    U − R attack rate ≈ 0 for employed and students
    U − R attack rate > 0 (concentrated) for inactive

  FAIL signature (breaks mechanism, requires investigation):
    U − R positive roughly uniformly across all three statuses

Activity categories derived from agents_patras.csv:
  employed : Work_ID != -1 (may also have school; work contact dominates)
  student  : School_ID != -1 and Work_ID == -1
  inactive : Work_ID == -1 and School_ID == -1

Usage:
  python diagnostic_status.py             # 10 seeds, 180 steps
  python diagnostic_status.py --seeds 5  # fewer seeds for speed
"""
import sys
import os
import random
import argparse
from collections import defaultdict

import numpy as np
import pandas as pd

# Re-use constants and helpers from run_experiment without re-importing the
# __main__ block.
_DIAG_DIR = os.path.dirname(os.path.abspath(__file__))
_ABM_DIR  = os.path.dirname(_DIAG_DIR)
sys.path.insert(0, _ABM_DIR)
from run_experiment import (
    BETA_FAMILY, BETA_WORK, BETA_SCHOOL, BETA_RANDOM, BETA_SAME_AGE,
    GAMMA, SIGMA, TOTAL_STEPS, INITIAL_INFECTED,
    _build_model, _do_step, build_u_agents, _get_age_group, AGE_GROUPS
)


def run_once_tracked(agents_df, seed, total_steps=TOTAL_STEPS):
    """Run one replicate and return (metrics_dict, agents_list).

    Like run_once() but also returns the agents list so callers can
    inspect per-agent final status for the activity-status diagnostic.
    """
    random.seed(seed)
    np.random.seed(seed)

    agents, by_family, by_work, by_school, by_age, s_in_work, s_in_school = \
        _build_model(agents_df)
    N = len(agents)

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
        active, new_exp = _do_step(active, agents, by_family, by_work,
                                   by_school, by_age, s_in_work, s_in_school)
        daily_new.append(new_exp)
        if not active:
            daily_new.extend([0] * (total_steps - step - 1))
            break

    S_final = sum(1 for a in agents if a.status == 'S')
    return {
        'seed':           seed,
        'attack_rate':    1.0 - S_final / N,
        'peak_incidence': max(daily_new),
        'day_of_peak':    int(np.argmax(daily_new)),
    }, agents


def activity_category(agent):
    """Return 'employed', 'student', or 'inactive' for an agent."""
    if agent.work_id != -1:
        return 'employed'
    if agent.school_id != -1:
        return 'student'
    return 'inactive'


def compute_ar_by_status(agents):
    """Return dict: category → (infected, total, attack_rate)."""
    counts = defaultdict(lambda: [0, 0])  # [infected, total]
    for a in agents:
        cat = activity_category(a)
        counts[cat][1] += 1
        if a.status != 'S':
            counts[cat][0] += 1
    return {cat: (v[0], v[1], v[0] / v[1] if v[1] > 0 else 0.0)
            for cat, v in counts.items()}


def run_diagnostic(n_seeds=10, total_steps=TOTAL_STEPS):
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(BASE, 'agents_patras.csv')
    print(f"Loading {csv_path} ...")
    r_df = pd.read_csv(csv_path)
    print(f"  {len(r_df):,} agents loaded.")

    print("Building U (size-matched shuffle, u_seed=999) ...")
    u_df = build_u_agents(r_df, u_seed=999)

    categories = ['employed', 'student', 'inactive']
    # r_ars[cat] and u_ars[cat] accumulate per-seed attack rates
    r_ars = {cat: [] for cat in categories}
    u_ars = {cat: [] for cat in categories}

    # Population composition (constant across seeds)
    pop_composition = None

    for seed in range(n_seeds):
        print(f"  seed {seed:2d} ...", end='', flush=True)

        r_metrics, r_agents = run_once_tracked(r_df, seed=seed,
                                               total_steps=total_steps)
        u_metrics, u_agents = run_once_tracked(u_df, seed=seed,
                                               total_steps=total_steps)

        r_by_cat = compute_ar_by_status(r_agents)
        u_by_cat = compute_ar_by_status(u_agents)

        if pop_composition is None:
            pop_composition = {cat: r_by_cat[cat][1] for cat in categories
                               if cat in r_by_cat}

        for cat in categories:
            r_ars[cat].append(r_by_cat.get(cat, (0, 0, 0.0))[2])
            u_ars[cat].append(u_by_cat.get(cat, (0, 0, 0.0))[2])

        print(f"  R_AR={r_metrics['attack_rate']:.4f} "
              f"U_AR={u_metrics['attack_rate']:.4f}")

    # ── Report ────────────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print("ACTIVITY-STATUS DIAGNOSTIC")
    print(f"({n_seeds} seeds, {total_steps} steps each)")
    print("=" * 72)

    if pop_composition:
        total_pop = sum(pop_composition.values())
        print(f"\nPopulation composition:")
        for cat in categories:
            n = pop_composition.get(cat, 0)
            print(f"  {cat:<12s} {n:>7,}  ({100*n/total_pop:.1f}%)")

    print()
    print(f"{'Category':<12} {'R AR %':>10} {'U AR %':>10} "
          f"{'U-R (pp)':>10}  Prediction")
    print("-" * 60)

    results = {}
    for cat in categories:
        r_mean = 100 * np.mean(r_ars[cat])
        u_mean = 100 * np.mean(u_ars[cat])
        diff   = u_mean - r_mean
        # Predict direction based on mechanism
        pred = "near-zero" if cat in ('employed', 'student') else "positive"
        results[cat] = {'R_AR': r_mean, 'U_AR': u_mean, 'diff': diff}
        print(f"  {cat:<12} {r_mean:>9.3f}% {u_mean:>9.3f}% "
              f"{diff:>+9.4f}pp  (expected: {pred})")

    print()
    # Pass/fail determination
    inactive_diff  = results['inactive']['diff']
    employed_diff  = results['employed']['diff']
    student_diff   = results['student']['diff']

    active_max = max(abs(employed_diff), abs(student_diff))
    # PASS: inactive gap substantially larger than active-core gap
    # Threshold: inactive diff > 3x max(employed, student) diff
    if inactive_diff > 0 and (active_max == 0 or inactive_diff > 3 * active_max):
        verdict = "PASS"
        explanation = ("U-R excess concentrated in inactive; "
                       "active core AR unchanged — assortative segregation confirmed.")
    elif abs(employed_diff - inactive_diff) < 0.01:
        verdict = "FAIL (uniform shift)"
        explanation = ("U-R positive roughly uniformly across all categories. "
                       "Not consistent with assortative segregation — "
                       "investigate global effect or second bug.")
    else:
        verdict = "AMBIGUOUS"
        explanation = ("Inactive gap larger but not decisively concentrated. "
                       "Near-null ARs may mask structure; interpret with caution.")

    print(f"VERDICT: {verdict}")
    print(f"  {explanation}")

    # Save CSV
    out_path = os.path.join(BASE, 'diagnostic_status_results.csv')
    rows = []
    for cat in categories:
        rows.append({'category': cat,
                     'R_AR_pct':  results[cat]['R_AR'],
                     'U_AR_pct':  results[cat]['U_AR'],
                     'diff_pp':   results[cat]['diff'],
                     'n_agents':  pop_composition.get(cat, 0)})
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")

    return results, verdict


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', type=int, default=10,
                        help='Number of paired replicates (default: 10)')
    parser.add_argument('--steps', type=int, default=TOTAL_STEPS,
                        help=f'Simulation steps (default: {TOTAL_STEPS})')
    args = parser.parse_args()

    run_diagnostic(n_seeds=args.seeds, total_steps=args.steps)
