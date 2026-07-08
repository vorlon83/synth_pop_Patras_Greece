"""Compute ablation MAE for corrected population."""
import json
import os
import numpy as np
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load corrected S1 population
with open(os.path.join(ROOT, 'data', 'synthpop', 'patras_households.json')) as f:
    s1 = json.load(f)

sizes_s1 = Counter(len(h['members']) for h in s1)
total_s1 = len(s1)

# 5-category distribution: 1, 2, 3, 4, 5+
def five_cat(sizes, total):
    cats = {k: 0 for k in range(1, 6)}
    for s, n in sizes.items():
        cats[min(s, 5)] += n
    return np.array([cats[k]/total for k in [1,2,3,4,5]])

s1_dist = five_cat(sizes_s1, total_s1)
print(f"S1 5-cat distribution: {s1_dist}")

# Italian template distribution (from household_compositions.json)
with open(os.path.join(ROOT, 'Thesis_Synthpop-main', 'it_microdata_preprocess', 'household_compositions.json')) as f:
    templates = json.load(f)

template_cats = {k: 0.0 for k in range(1, 6)}
for t in templates:
    size = min(len(t['household']), 5)
    template_cats[size] += t['percentage']
template_dist = np.array([template_cats[k] for k in [1, 2, 3, 4, 5]])
template_dist /= template_dist.sum()
print(f"Template 5-cat distribution: {template_dist}")

mae_b = np.mean(np.abs(s1_dist - template_dist)) * 100
print(f"MAE (variant B, corrected S1 vs template): {mae_b:.1f} pp")

# For reference: variant A (unconstrained) would have template-identical dist → MAE=0
# Variant A singleton rate ≈ template inherent rate
template_singleton_rate = template_cats[1] / sum(template_cats.values()) * 100
print(f"Template inherent singleton rate: {template_singleton_rate:.1f}%")
print(f"S1 corrected singleton rate: {100*sizes_s1[1]/total_s1:.1f}%")

# S3 distribution
from scipy.spatial.distance import jensenshannon
wg = np.array([82783, 70859, 44848, 37766, 21083], dtype=float)
wg /= wg.sum()
print(f"\nWG reference: {wg}")
print(f"S1 JSD vs WG: {jensenshannon(s1_dist, wg, base=2)**2:.4f} bits")
