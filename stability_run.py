"""10-run cross-seed stability test for the Patras synthetic population.

Seeding protocol (per manuscript methods):
  AGE_MAP_SEED = 42  -- FIXED in age_group_mapping.py (template library prior)
  PIPELINE_SEED     -- VARIED (seeds 0–9): stochastic rounding + greedy matching

Run from GIS-paper-main/:
    python stability_run.py

Outputs mean, SD, CV for total individuals and households across the 10 runs.
"""
import subprocess
import json
import os
import sys
import numpy as np

PATRAS_ID = '2423701'
# Pipeline must be invoked with cwd = Thesis_Synthpop-main (dataset_loading.py
# uses relative paths starting with 'python_ipf/').
PIPE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Thesis_Synthpop-main')
SCRIPT = os.path.join('python_ipf', 'main_ipf_pipeline.py')
HH_PATH = os.path.join(PIPE_DIR, 'python_ipf', 'ipf_results', 'households.json')

results = []

for seed in range(10):
    print(f'\n{"="*60}')
    print(f'Run {seed + 1}/10  (PIPELINE_SEED={seed})')
    print('='*60)

    env = os.environ.copy()
    env['PIPELINE_SEED'] = str(seed)

    proc = subprocess.run(
        [sys.executable, SCRIPT],
        cwd=PIPE_DIR,
        env=env,
        capture_output=False,   # stream output so progress is visible
    )

    if proc.returncode != 0:
        print(f'  [ERROR] Pipeline exited with code {proc.returncode} for seed {seed}')
        results.append({'seed': seed, 'households': None, 'people': None})
        continue

    with open(HH_PATH) as f:
        hh_all = json.load(f)

    patras = [h for h in hh_all if h['location_id'] == PATRAS_ID]
    n_hh = len(patras)
    n_ppl = sum(len(h['members']) for h in patras)
    results.append({'seed': seed, 'households': n_hh, 'people': n_ppl})
    print(f'  Patras households: {n_hh:,}   people: {n_ppl:,}')

print('\n' + '='*60)
print('STABILITY SUMMARY (10 runs, seeds 0-9)')
print('='*60)

valid = [r for r in results if r['people'] is not None]
if valid:
    ppl = np.array([r['people'] for r in valid])
    hhs = np.array([r['households'] for r in valid])

    print(f'\nPeople (Patras):')
    print(f'  Mean  : {ppl.mean():,.1f}')
    print(f'  SD    : {ppl.std(ddof=1):,.1f}')
    print(f'  CV    : {ppl.std(ddof=1)/ppl.mean():.6f}  ({ppl.std(ddof=1)/ppl.mean()*100:.4f}%)')
    print(f'  Min   : {ppl.min():,}')
    print(f'  Max   : {ppl.max():,}')

    print(f'\nHouseholds (Patras):')
    print(f'  Mean  : {hhs.mean():,.1f}')
    print(f'  SD    : {hhs.std(ddof=1):,.1f}')
    print(f'  CV    : {hhs.std(ddof=1)/hhs.mean():.6f}  ({hhs.std(ddof=1)/hhs.mean()*100:.4f}%)')
    print(f'  Min   : {hhs.min():,}')
    print(f'  Max   : {hhs.max():,}')

    print(f'\nPer-run table:')
    print(f'  {"Seed":>4}  {"People":>8}  {"HH":>7}')
    for r in results:
        if r['people'] is not None:
            print(f'  {r["seed"]:>4}  {r["people"]:>8,}  {r["households"]:>7,}')
        else:
            print(f'  {r["seed"]:>4}  {"ERROR":>8}  {"ERROR":>7}')
else:
    print('No valid runs completed.')
