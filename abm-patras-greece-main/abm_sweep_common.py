"""Shared helpers for the ABM sweep scripts (full_sweep_50rep.py, beta_family_sweep.py,
age_betawork_sweep.py, run_experiment_S3.py).

These were previously duplicated verbatim across all four scripts because
full_sweep_50rep.py had no `if __name__ == '__main__':` guard, so importing it
would trigger its own ~30-100 minute sweep as a side effect. That guard now
exists, so the duplication is no longer necessary.
"""
import random
from collections import defaultdict

import numpy as np
from scipy.stats import wilcoxon


def sar_to_beta(sar, gamma):
    """Household transmission probability implied by a target secondary attack
    rate, under geometric escape: SAR = 1 - (1-beta)^(1/gamma)."""
    return 1.0 - (1.0 - sar) ** gamma


def activity_category(work_id, school_id):
    if work_id != -1:
        return 'employed'
    if school_id != -1:
        return 'student'
    return 'inactive'


def per_status_ar(agents):
    counts = defaultdict(lambda: [0, 0])
    for a in agents:
        cat = activity_category(a.work_id, a.school_id)
        counts[cat][1] += 1
        if a.status != 'S':
            counts[cat][0] += 1
    return {cat: (v[0] / v[1] if v[1] > 0 else 0.0) for cat, v in counts.items()}


def elderly65_ar(agents):
    """Fraction of agents aged 65+ not in status 'S'."""
    inf = tot = 0
    for a in agents:
        if a.age >= 65:
            tot += 1
            if a.status != 'S':
                inf += 1
    return inf / tot if tot else 0.0


def count_major_peaks(daily_new, threshold=0.15):
    """Local maxima at or above threshold x global max. >1 means multi-peak."""
    arr = np.array(daily_new, dtype=float)
    pmax = arr.max()
    if pmax == 0:
        return 0
    min_h = threshold * pmax
    n = 0
    for i in range(1, len(arr) - 1):
        if arr[i] > arr[i - 1] and arr[i] > arr[i + 1] and arr[i] >= min_h:
            n += 1
    return n


def wpval(a, b):
    diff = np.asarray(a) - np.asarray(b)
    if np.all(diff == 0):
        return 1.0
    _, p = wilcoxon(a, b)
    return float(p)


def run_once_tracked(run_exp, agents_df, seed, total_steps=None,
                      beta_family=None, beta_work=None):
    """Run one replicate, returning (metrics_dict, agents_list).

    `run_exp` is the run_experiment module (each caller already imports it as
    `run_exp` or `re`). beta_family/beta_work default to run_exp's published
    constants when not given explicitly -- always pass them explicitly rather
    than mutating run_exp's module attributes, since beta_family is a default
    argument bound at _do_step's definition time and a later attribute
    mutation would silently have no effect (see bugs_to_fix.md BUG-A/BUG-E).
    """
    if total_steps is None:
        total_steps = run_exp.TOTAL_STEPS
    bf = beta_family if beta_family is not None else run_exp.BETA_FAMILY
    bw = beta_work if beta_work is not None else run_exp.BETA_WORK

    random.seed(seed)
    np.random.seed(seed)
    agents, by_fam, by_work, by_school, by_age, s_in_work, s_in_school = \
        run_exp._build_model(agents_df)
    N = len(agents)

    rng = np.random.default_rng(seed)
    init_ids = rng.choice(N, size=run_exp.INITIAL_INFECTED, replace=False)
    active = []
    for idx in init_ids:
        agents[idx].status = 'I'
        agents[idx].next_status = 'I'
        active.append(agents[idx])
        a = agents[idx]
        if a.work_id != -1:
            s_in_work[a.work_id] -= 1
        if a.school_id != -1:
            s_in_school[a.school_id] -= 1

    daily_new = []
    for step in range(total_steps):
        active, new_exp = run_exp._do_step(active, agents, by_fam, by_work,
                                            by_school, by_age, s_in_work,
                                            s_in_school, beta_family=bf,
                                            beta_work=bw)
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
