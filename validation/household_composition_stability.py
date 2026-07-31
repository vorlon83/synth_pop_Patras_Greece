"""Household-type composition stability across 10 seeds (PIPELINE_SEED 0-9).

Extends the existing total-population stability check (stability_run.py) to the
household-*composition* metrics that actually matter for the paper's household-
structure claims. Total population is fixed by IPF marginals almost by
definition; household composition is produced by a path-dependent greedy
matcher processing agents in random order, so seed-to-seed variance there is
the open question this script answers (raised by a reviewer).

Seeding protocol (same as stability_run.py):
  AGE_MAP_SEED = 42  -- FIXED in age_group_mapping.py (template library prior)
  PIPELINE_SEED       -- VARIED (seeds 0-9): stochastic rounding + greedy matching

For each seed's resulting Patras household population, computes:
  - Singleton rate (% households with exactly 1 member)
  - Mean household size
  - Multigenerational share (% households with members from all three
    generation bands: 0-14, 15-64, 65+) -- same definition as
    validation/structural_validation.py and main.tex Table tab:coresidence_metrics
  - JSD (base-2, bits) of the 5-category household-size distribution against
    the Western Greece reference, computed with the *exact* method used in
    validation/compute_jsd.py (same WG reference counts, same scipy call).

Run from GIS-paper-main/:
    python validation/household_composition_stability.py

Outputs:
    validation/household_composition_stability.csv          (per-seed raw values)
    validation/household_composition_stability_summary.csv   (mean/SD/CV per metric)

IMPORTANT -- isolation: main_ipf_pipeline.py writes its output to a FIXED,
non-seed-specific relative path (python_ipf/ipf_results/households.json)
inside Thesis_Synthpop-main/. This repository lives in an actively-synced
cloud folder and is also used by other concurrent processes/agents that
independently invoke the same pipeline script against the same shared path
(confirmed empirically: a direct single-seed test run's own stdout logged the
correct seed-specific counts, but the *file on disk* read immediately
afterwards held different, canonical-seed-42 counts -- a write race, not a
seeding bug). To get trustworthy per-seed results this script therefore runs
every pipeline invocation inside a private, single-use copy of
Thesis_Synthpop-main under the system temp directory (outside the synced
repo tree), so no other process can ever clobber the output between write
and read.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from scipy.spatial.distance import jensenshannon

PATRAS_ID = '2423701'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_PIPE_DIR = os.path.join(ROOT, 'Thesis_Synthpop-main')
SCRIPT = os.path.join('python_ipf', 'main_ipf_pipeline.py')


def make_isolated_pipeline_copy():
    """Copy Thesis_Synthpop-main into a private temp dir so concurrent
    processes touching the real repo path cannot race with our reads/writes.
    Excludes the large pre-existing ipf_results/ output dir (regenerated
    fresh by each run) and __pycache__."""
    tmp_root = tempfile.mkdtemp(prefix='hh_stability_isolated_')
    dest = os.path.join(tmp_root, 'Thesis_Synthpop-main')

    def _ignore(dir_, names):
        ignored = set()
        if os.path.basename(dir_) == 'python_ipf' and 'ipf_results' in names:
            ignored.add('ipf_results')
        if '__pycache__' in names:
            ignored.add('__pycache__')
        return ignored

    shutil.copytree(REAL_PIPE_DIR, dest, ignore=_ignore)
    os.makedirs(os.path.join(dest, 'python_ipf', 'ipf_results'), exist_ok=True)
    return dest

CHILD = set(range(0, 3))    # age bands 0-2  -> ages 0-14
ADULT = set(range(3, 13))   # age bands 3-12 -> ages 15-64
ELDERLY = set(range(13, 16))  # age bands 13-15 -> ages 65+

# WG reference — exact same counts as validation/compute_jsd.py
# (people_per_household_western_greece.csv, ELSTAT 2021):
#   1P:82783  2P:70859  3P:44848  4P:37766  5+:21083  Total:257339
_WG_COUNTS = np.array([82783, 70859, 44848, 37766, 21083], dtype=float)
_WG_REF = _WG_COUNTS / _WG_COUNTS.sum()


def compute_jsd_bits(synth_dist):
    """Exact JSD computation reused from validation/compute_jsd.py (base-2, bits)."""
    return jensenshannon(synth_dist, _WG_REF, base=2) ** 2


def compute_metrics(patras_households):
    total_hh = len(patras_households)
    sizes = np.array([len(hh['members']) for hh in patras_households])

    n_singleton = int(np.sum(sizes == 1))
    singleton_rate = 100 * n_singleton / total_hh
    mean_hh_size = sizes.mean()

    multigen = 0
    for hh in patras_households:
        bands = set(m['age_group'] for m in hh['members'])
        if (bands & CHILD) and (bands & ADULT) and (bands & ELDERLY):
            multigen += 1
    multigen_share = 100 * multigen / total_hh

    cats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for s in sizes:
        cats[min(int(s), 5)] += 1
    synth_dist = np.array([cats[k] for k in [1, 2, 3, 4, 5]], dtype=float)
    synth_dist /= synth_dist.sum()
    jsd = compute_jsd_bits(synth_dist)

    return {
        'total_hh': total_hh,
        'total_people': int(sizes.sum()),
        'singleton_rate_pct': singleton_rate,
        'mean_hh_size': mean_hh_size,
        'multigen_share_pct': multigen_share,
        'jsd_bits': jsd,
    }


def main():
    # Optional CLI args: list of seeds to run, e.g.
    #   python validation/household_composition_stability.py 0 1
    # Defaults to the full seeds 0-9 sweep. A partial seed list is treated as
    # a smoke test (bug-verification check) and written to separate,
    # clearly-labeled output files rather than the full-sweep CSV names, so a
    # partial run can never be mistaken for the publication-grade 10-seed
    # stability statistic.
    if len(sys.argv) > 1:
        seeds = [int(s) for s in sys.argv[1:]]
    else:
        seeds = list(range(10))
    is_smoke_test = len(seeds) < 10
    n_total = len(seeds)

    print('Creating isolated pipeline copy (immune to concurrent-process file races)...')
    pipe_dir = make_isolated_pipeline_copy()
    hh_path = os.path.join(pipe_dir, 'python_ipf', 'ipf_results', 'households.json')
    print(f'Isolated copy: {pipe_dir}')
    if is_smoke_test:
        print(f'*** SMOKE TEST MODE *** running only seeds {seeds} (not the full 10-seed sweep)')

    results = []
    for i, seed in enumerate(seeds):
        print(f'\n{"=" * 60}')
        print(f'Run {i + 1}/{n_total}  (PIPELINE_SEED={seed})')
        print('=' * 60)

        env = os.environ.copy()
        env['PIPELINE_SEED'] = str(seed)
        # Ensure instrumentation from Task 2 is OFF for these runs (default
        # behaviour; TIER_STATS_OUTPUT unset means zero behavioural change).
        env.pop('TIER_STATS_OUTPUT', None)

        # Remove any stale output before this run so a silent no-write failure
        # cannot be misread as this seed's result.
        if os.path.exists(hh_path):
            os.remove(hh_path)

        proc = subprocess.run(
            [sys.executable, SCRIPT],
            cwd=pipe_dir,
            env=env,
            capture_output=False,
        )

        if proc.returncode != 0:
            print(f'  [ERROR] Pipeline exited with code {proc.returncode} for seed {seed}')
            results.append({'seed': seed, 'error': True})
            continue

        if not os.path.exists(hh_path):
            print(f'  [ERROR] households.json missing after run for seed {seed}')
            results.append({'seed': seed, 'error': True})
            continue

        with open(hh_path) as f:
            hh_all = json.load(f)
        patras = [h for h in hh_all if h['location_id'] == PATRAS_ID]

        m = compute_metrics(patras)
        m['seed'] = seed
        m['error'] = False
        results.append(m)
        print(f"  Patras households: {m['total_hh']:,}   people: {m['total_people']:,}")
        print(f"  Singleton rate: {m['singleton_rate_pct']:.3f}%   "
              f"Mean HH size: {m['mean_hh_size']:.4f}   "
              f"Multigen share: {m['multigen_share_pct']:.3f}%   "
              f"JSD: {m['jsd_bits']:.5f} bits")

    shutil.rmtree(os.path.dirname(pipe_dir), ignore_errors=True)

    valid = [r for r in results if not r['error']]

    _suffix = '_SMOKETEST' if is_smoke_test else ''
    per_seed_path = os.path.join(ROOT, 'validation', f'household_composition_stability{_suffix}.csv')
    with open(per_seed_path, 'w', newline='') as f:
        writer = csv.writer(f)
        if is_smoke_test:
            writer.writerow([f'# SMOKE TEST ONLY -- seeds {seeds} -- bug-verification check for the '
                              f'concurrent-write-race fix, NOT a publication-grade stability statistic'])
        writer.writerow(['seed', 'total_hh', 'total_people', 'singleton_rate_pct',
                          'mean_hh_size', 'multigen_share_pct', 'jsd_bits'])
        for r in results:
            if r['error']:
                writer.writerow([r['seed'], 'ERROR', 'ERROR', 'ERROR', 'ERROR', 'ERROR', 'ERROR'])
            else:
                writer.writerow([r['seed'], r['total_hh'], r['total_people'],
                                  f"{r['singleton_rate_pct']:.6f}", f"{r['mean_hh_size']:.6f}",
                                  f"{r['multigen_share_pct']:.6f}", f"{r['jsd_bits']:.6f}"])
    print(f'\nPer-seed raw values saved to {per_seed_path}')

    summary_path = os.path.join(ROOT, 'validation', f'household_composition_stability_summary{_suffix}.csv')
    metric_keys = ['singleton_rate_pct', 'mean_hh_size', 'multigen_share_pct', 'jsd_bits']
    metric_labels = {
        'singleton_rate_pct': 'Singleton rate (%)',
        'mean_hh_size': 'Mean household size',
        'multigen_share_pct': 'Multigenerational share (%)',
        'jsd_bits': 'JSD household-size vs WG (bits)',
    }

    print('\n' + '=' * 60)
    label = f'SMOKE TEST (seeds {seeds})' if is_smoke_test else 'seeds 0-9'
    print(f'HOUSEHOLD COMPOSITION {"SMOKE-TEST" if is_smoke_test else "STABILITY"} '
          f'SUMMARY (n={len(valid)} valid runs, {label})')
    print('=' * 60)

    with open(summary_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['metric', 'n', 'mean', 'sd', 'cv_pct', 'min', 'max'])
        for key in metric_keys:
            vals = np.array([r[key] for r in valid])
            mean = vals.mean()
            sd = vals.std(ddof=1)
            cv = 100 * sd / mean
            writer.writerow([metric_labels[key], len(vals), f'{mean:.6f}', f'{sd:.6f}',
                              f'{cv:.6f}', f'{vals.min():.6f}', f'{vals.max():.6f}'])
            print(f'\n{metric_labels[key]}:')
            print(f'  Mean : {mean:.4f}')
            print(f'  SD   : {sd:.4f}')
            print(f'  CV   : {cv:.4f}%')
            print(f'  Min  : {vals.min():.4f}   Max: {vals.max():.4f}')

    print(f'\nSummary statistics saved to {summary_path}')


if __name__ == '__main__':
    main()
