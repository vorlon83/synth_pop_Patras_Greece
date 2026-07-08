"""Filter Patras households from full Achaia synthesis output. Pipeline step 2."""
import json
import os

ROOT   = os.path.dirname(os.path.abspath(__file__))
INPUT  = os.path.join(ROOT, 'Thesis_Synthpop-main', 'python_ipf', 'ipf_results', 'households.json')
OUTPUT = os.path.join(ROOT, 'data', 'synthpop', 'patras_households.json')
PATRAS_ID = '2423701'

print('Loading households.json...')
with open(INPUT) as f:
    hh_all = json.load(f)

patras = [h for h in hh_all if h['location_id'] == PATRAS_ID]
total_people = sum(len(h['members']) for h in patras)
print(f'Patras households: {len(patras):,}')
print(f'Patras people: {total_people:,}')

with open(OUTPUT, 'w') as f:
    json.dump(patras, f)
print(f'Saved to {OUTPUT}')
