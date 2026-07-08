"""Recompute JSD and household-size distribution for corrected population."""
import json
import os
import numpy as np
from collections import Counter
from scipy.spatial.distance import jensenshannon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(ROOT, 'data', 'synthpop', 'patras_households.json')) as f:
    data = json.load(f)

sizes = Counter(len(hh['members']) for hh in data)
total_hh = len(data)
print(f"Total households: {total_hh:,}")
print(f"Size distribution:")
for s in sorted(sizes):
    pct = 100 * sizes[s] / total_hh
    print(f"  size {s}: {sizes[s]:6d}  ({pct:.2f}%)")

# 5-category: 1, 2, 3, 4, 5+ (as used in WG validation)
cats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
for s, n in sizes.items():
    key = min(s, 5)
    cats[key] += n

synth_dist = np.array([cats[k] for k in [1,2,3,4,5]], dtype=float)
synth_dist /= synth_dist.sum()

# WG reference from people_per_household_western_greece.csv (ELSTAT 2021)
# 1P:82783  2P:70859  3P:44848  4P:37766  5+:21083  Total:257339
wg_counts = np.array([82783, 70859, 44848, 37766, 21083], dtype=float)
wg_ref = wg_counts / wg_counts.sum()

jsd = jensenshannon(synth_dist, wg_ref, base=2)**2  # in bits
print(f"\n5-category synthetic distribution: {synth_dist}")
print(f"WG reference distribution:         {wg_ref}")
print(f"JSD (bits): {jsd:.4f}")
print(f"Synthetic mean HH size: {sum(k*n for k,n in sizes.items())/total_hh:.3f}")
print(f"Synthetic singleton rate: {100*sizes[1]/total_hh:.1f}%")

# Chi-square against WG 5-cat distribution
from scipy.stats import chisquare
expected = wg_ref * total_hh
observed = synth_dist * total_hh
chi2, p = chisquare(f_obs=observed, f_exp=expected)
print(f"\nChi-square: {chi2:.1f} (df=4, p~0)")
