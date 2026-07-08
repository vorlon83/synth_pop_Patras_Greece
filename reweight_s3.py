"""Generate S3 templates: Italian compositions reweighted to WG size distribution.

Strategy: multiply each template's percentage by factor[size], where
factor[size] = WG_target[size] / S1_current[size].
Then renormalize.

Writes: Thesis_Synthpop-main/it_microdata_preprocess/household_compositions_s3.json
Run pipeline with this file to generate S3 population.
"""
import json
import numpy as np

TEMPLATE_PATH = 'Thesis_Synthpop-main/it_microdata_preprocess/household_compositions.json'
OUT_PATH      = 'Thesis_Synthpop-main/it_microdata_preprocess/household_compositions_s3.json'

# WG 2021 five-category distribution
WG = np.array([82783, 70859, 44848, 37766, 21083], dtype=float)
WG /= WG.sum()

with open(TEMPLATE_PATH) as f:
    templates = json.load(f)

# Current S1 size distribution
total_pct = sum(t['percentage'] for t in templates)
s1_by_size = {k: 0.0 for k in range(1, 6)}
for t in templates:
    sz = min(len(t['household']), 5)
    s1_by_size[sz] += t['percentage'] / total_pct

print('S1 size distribution:', {k: round(v, 4) for k, v in s1_by_size.items()})
print('WG target:           ', {k+1: round(v, 4) for k, v in enumerate(WG)})

# Compute reweighting factors
factors = {k+1: WG[k] / s1_by_size[k+1] for k in range(5)}
print('Reweighting factors: ', {k: round(v, 4) for k, v in factors.items()})

# Apply factors and renormalize
reweighted = []
for t in templates:
    sz = min(len(t['household']), 5)
    new_pct = t['percentage'] * factors[sz]
    reweighted.append({'household': t['household'], 'percentage': new_pct})

total_new = sum(t['percentage'] for t in reweighted)
for t in reweighted:
    t['percentage'] /= total_new

# Verify output size distribution
new_by_size = {k: 0.0 for k in range(1, 6)}
for t in reweighted:
    sz = min(len(t['household']), 5)
    new_by_size[sz] += t['percentage']

print('S3 size distribution:', {k: round(v, 4) for k, v in new_by_size.items()})
print('WG target:           ', {k+1: round(v, 4) for k, v in enumerate(WG)})
diff = {k: abs(new_by_size[k] - WG[k-1]) for k in range(1, 6)}
print('Absolute diff:       ', {k: round(v, 6) for k, v in diff.items()})

with open(OUT_PATH, 'w') as f:
    json.dump(reweighted, f)

print(f'\nSaved {len(reweighted)} reweighted templates to {OUT_PATH}')
print('Run the pipeline with: TEMPLATE_FILE = household_compositions_s3.json')
print('(Modify main_ipf_pipeline.py line 84 to point to s3 template file)')
