"""Compute S3 sensitivity metrics from the S3 pipeline output.

Reads: Thesis_Synthpop-main/python_ipf/ipf_results/households.json  (S3 run)
       Thesis_Synthpop-main/it_microdata_preprocess/household_compositions_s3.json (S3 templates)

Outputs:
  - Patras-subset HH count and people count
  - Mean HH size
  - Multigenerational household rate (>=3 generations)
  - Singleton rate
  - Chi-square test vs WG reference [82783, 70859, 44848, 37766, 21083]
  - JSD between S3 template library size distribution and S3 synthetic output size distribution
  - JSD between S3 template library and WG (should be 0 by construction)
"""
import json
import numpy as np
from scipy.stats import chi2_contingency
from scipy.special import rel_entr
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HH_PATH = os.path.join(ROOT, 'Thesis_Synthpop-main', 'python_ipf', 'ipf_results', 'households.json')
S3_TMPL_PATH = os.path.join(ROOT, 'Thesis_Synthpop-main', 'it_microdata_preprocess', 'household_compositions_s3.json')

PATRAS_ID = '2423701'

# WG 2021 reference distribution (5-category)
WG_COUNTS = np.array([82783, 70859, 44848, 37766, 21083], dtype=float)
WG = WG_COUNTS / WG_COUNTS.sum()

def jsd(p, q):
    """Jensen-Shannon divergence in bits (log base 2)."""
    p = np.array(p, dtype=float)
    q = np.array(q, dtype=float)
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)
    # rel_entr(x, y) = x * log(x/y), returns 0 when x=0
    jsd_nats = 0.5 * rel_entr(p, m).sum() + 0.5 * rel_entr(q, m).sum()
    return jsd_nats / np.log(2)  # convert to bits

def is_multigenerational(members):
    """Manuscript definition: co-residence of members from all three generations:
      0-17 (age_groups 0-2), 18-64 (age_groups 3-12), 65+ (age_groups 13-15).
    Returns True only when at least one member from each band is present."""
    has_child   = any(m.get('age_group', 0) <= 2 for m in members)
    has_adult   = any(3 <= m.get('age_group', 0) <= 12 for m in members)
    has_elderly = any(m.get('age_group', 0) >= 13 for m in members)
    return has_child and has_adult and has_elderly

# Load S3 run output
print("Loading S3 households.json ...")
with open(HH_PATH) as f:
    hh_all = json.load(f)

print(f"Total Achaia households: {len(hh_all):,}")
patras = [h for h in hh_all if str(h['location_id']) == PATRAS_ID]
print(f"Patras households (S3): {len(patras):,}")

n_hh = len(patras)
n_people = sum(len(h['members']) for h in patras)
print(f"Patras people (S3):     {n_people:,}")
print(f"Mean HH size (S3):      {n_people / n_hh:.4f}")

# Size distribution
size_counts = {k: 0 for k in range(1, 6)}
singleton_count = 0
multigen_count = 0

for h in patras:
    sz = min(len(h['members']), 5)
    size_counts[sz] += 1
    if len(h['members']) == 1:
        singleton_count += 1
    if is_multigenerational(h['members']):
        multigen_count += 1

total = sum(size_counts.values())
print(f"\nSize distribution (S3 Patras):")
for k in range(1, 6):
    print(f"  Size {k}: {size_counts[k]:,}  ({size_counts[k]/total*100:.2f}%)")

singleton_rate = singleton_count / total
multigen_rate = multigen_count / total
print(f"\nSingleton rate: {singleton_rate*100:.2f}%")
print(f"Multigenerational (>=3 gen) rate: {multigen_rate*100:.2f}%")

# Chi-square vs WG
obs = np.array([size_counts[k] for k in range(1, 6)], dtype=float)
exp = WG * total
chi2 = np.sum((obs - exp)**2 / exp)
print(f"\nChi-square vs WG (S3): {chi2:.3f}")
print(f"Expected (WG-proportional): {np.round(exp).astype(int)}")
print(f"Observed (S3 Patras):       {obs.astype(int)}")

# S3 template library size distribution
print("\nLoading S3 template file ...")
with open(S3_TMPL_PATH) as f:
    s3_templates = json.load(f)

total_pct = sum(t['percentage'] for t in s3_templates)
s3_tmpl_by_size = {k: 0.0 for k in range(1, 6)}
for t in s3_templates:
    sz = min(len(t['household']), 5)
    s3_tmpl_by_size[sz] += t['percentage'] / total_pct

s3_tmpl_dist = np.array([s3_tmpl_by_size[k] for k in range(1, 6)])
print(f"S3 template size dist: {np.round(s3_tmpl_dist, 4)}")
print(f"WG target:             {np.round(WG, 4)}")

# S3 synthetic output size distribution
s3_synth_dist = obs / obs.sum()
print(f"S3 synthetic output:   {np.round(s3_synth_dist, 4)}")

# JSD computations
jsd_tmpl_wg = jsd(s3_tmpl_dist, WG)
jsd_tmpl_output = jsd(s3_tmpl_dist, s3_synth_dist)
jsd_output_wg = jsd(s3_synth_dist, WG)

print(f"\n=== JSD values (bits) ===")
print(f"JSD(S3 template vs WG):          {jsd_tmpl_wg:.6f}  (should be ~0 by construction)")
print(f"JSD(S3 template vs S3 output):   {jsd_tmpl_output:.6f}")
print(f"JSD(S3 output vs WG):            {jsd_output_wg:.6f}")

print(f"\n=== SECTION 5.5 SUMMARY ===")
print(f"S3 mean HH size:          {n_people/n_hh:.4f}")
print(f"S3 multigenerational:     {multigen_rate*100:.2f}%")
print(f"S3 singleton rate:        {singleton_rate*100:.2f}%")
print(f"S3 chi-sq vs WG:          {chi2:.3f}")
print(f"S3 JSD(tmpl vs output):   {jsd_tmpl_output:.6f} bits")
print(f"S3 JSD(output vs WG):     {jsd_output_wg:.6f} bits")
