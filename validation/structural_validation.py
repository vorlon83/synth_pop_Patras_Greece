"""
Structural household-composition validation.
Canonical population: data/synthpop/patras_households.json (seed 42)
"""
import json
import os
import numpy as np
from collections import Counter, defaultdict

AGE_GROUP_LUT = {
    0:'0-4', 1:'5-9', 2:'10-14', 3:'15-19', 4:'20-24', 5:'25-29',
    6:'30-34', 7:'35-39', 8:'40-44', 9:'45-49', 10:'50-54',
    11:'55-59', 12:'60-64', 13:'65-69', 14:'70-74', 15:'75+'
}

CHILD   = set(range(0, 3))   # age bands 0-2  → ages 0-14
ADULT   = set(range(3, 13))  # age bands 3-12 → ages 15-64
ELDERLY = set(range(13, 16)) # age bands 13-15 → ages 65+

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, 'data', 'synthpop', 'patras_households.json')

with open(JSON_PATH) as f:
    data = json.load(f)

total_hh = len(data)
total_persons = sum(len(hh['members']) for hh in data)
print(f"Total households: {total_hh}")
print(f"Total persons:    {total_persons}")
print()

# ── 1. SINGLETON STATISTICS ─────────────────────────────────────────────────
singletons = [hh for hh in data if len(hh['members']) == 1]
n_singletons = len(singletons)
print(f"Singleton households: {n_singletons}  ({100*n_singletons/total_hh:.2f}%)")
print()

# Age distribution OF singletons
sing_age = Counter(hh['members'][0]['age_group'] for hh in singletons)
print("Age distribution of singleton occupants (synthetic):")
print(f"{'Band':4s}  {'Range':6s}  {'N':>6s}  {'%singl':>8s}")
for ag in range(16):
    n = sing_age.get(ag, 0)
    print(f"{ag:4d}  {AGE_GROUP_LUT[ag]:6s}  {n:6d}  {100*n/n_singletons:7.2f}%")
print()

# Singleton rate WITHIN each age band
band_total   = defaultdict(int)
band_single  = defaultdict(int)
for hh in data:
    is_single = len(hh['members']) == 1
    for m in hh['members']:
        ag = m['age_group']
        band_total[ag] += 1
        if is_single:
            band_single[ag] += 1

print("Singleton rate within each age band:")
print(f"{'Band':4s}  {'Range':6s}  {'Singles':>8s}  {'Total':>8s}  {'Rate':>7s}")
for ag in range(16):
    tot = band_total.get(ag, 0)
    s   = band_single.get(ag, 0)
    rate = 100*s/tot if tot else 0
    print(f"{ag:4d}  {AGE_GROUP_LUT[ag]:6s}  {s:8d}  {tot:8d}  {rate:6.1f}%")
print()

# ── 2. IMPLAUSIBLE HOUSEHOLDS ────────────────────────────────────────────────
# 2a. Child singletons (0-14 living alone)
child_singletons = [hh for hh in singletons if hh['members'][0]['age_group'] in CHILD]
print(f"Child singletons (sole member aged 0-14): {len(child_singletons)}")
cs_age = Counter(hh['members'][0]['age_group'] for hh in child_singletons)
for ag in sorted(cs_age):
    print(f"  band {ag} ({AGE_GROUP_LUT[ag]}): {cs_age[ag]}")
print()

# 2b. Households where ALL members are 0-14 (children-only, multi-member too)
children_only_hh = [hh for hh in data if all(m['age_group'] in CHILD for m in hh['members'])]
co_persons = sum(len(hh['members']) for hh in children_only_hh)
print(f"Children-only households (all members 0-14): {len(children_only_hh)}  ({100*len(children_only_hh)/total_hh:.3f}%)")
print(f"  Persons in children-only HH: {co_persons}  ({100*co_persons/total_persons:.3f}%)")
print()

# 2c. Households with child member but no adult present
child_hhs = [hh for hh in data if any(m['age_group'] in CHILD for m in hh['members'])]
no_adult_child_hhs = [hh for hh in child_hhs
                      if not any(m['age_group'] in ADULT | ELDERLY for m in hh['members'])]
print(f"Households with 0-14 member: {len(child_hhs)}")
print(f"  ...with at least one adult (15+): {len(child_hhs)-len(no_adult_child_hhs)}  ({100*(len(child_hhs)-len(no_adult_child_hhs))/len(child_hhs):.2f}%)")
print(f"  ...with NO adult present:         {len(no_adult_child_hhs)}  ({100*len(no_adult_child_hhs)/len(child_hhs):.2f}%)")
print()

# ── 3. MULTIGENERATIONAL ─────────────────────────────────────────────────────
multigenerational = sum(
    1 for hh in data
    if set(m['age_group'] for m in hh['members']) & CHILD
    and set(m['age_group'] for m in hh['members']) & ADULT
    and set(m['age_group'] for m in hh['members']) & ELDERLY
)
print(f"Multigenerational HH (0-14 + 15-64 + 65+): {multigenerational}  ({100*multigenerational/total_hh:.2f}%)")
print()

# ── 4. YOUNG-ADULT CO-RESIDENCE ──────────────────────────────────────────────
for label, bands in [("15-29 (bands 3-5)", {3,4,5}), ("20-29 (bands 4-5)", {4,5})]:
    ya_total      = sum(1 for hh in data for m in hh['members'] if m['age_group'] in bands)
    ya_not_alone  = sum(1 for hh in data for m in hh['members']
                        if m['age_group'] in bands and len(hh['members']) > 1)
    print(f"Young adults {label}: not living alone = {ya_not_alone}/{ya_total} = {100*ya_not_alone/ya_total:.1f}%")
print()

# ── 5. ELDERLY CO-RESIDENCE ──────────────────────────────────────────────────
eld_total    = sum(1 for hh in data for m in hh['members'] if m['age_group'] in ELDERLY)
eld_alone    = sum(1 for hh in data for m in hh['members']
                   if m['age_group'] in ELDERLY and len(hh['members']) == 1)
eld_not_alone = eld_total - eld_alone
print(f"Elderly (65+): total persons = {eld_total}")
print(f"  Living alone:     {eld_alone}  ({100*eld_alone/eld_total:.1f}%)")
print(f"  Living with others: {eld_not_alone}  ({100*eld_not_alone/eld_total:.1f}%)")
print()

# Elderly singleton rate by fine band
for ag in [13, 14, 15]:
    tot = band_total.get(ag, 0)
    s   = band_single.get(ag, 0)
    print(f"  {AGE_GROUP_LUT[ag]:5s}: {s}/{tot} = {100*s/tot:.1f}% living alone")
print()

# ── 6. WITHIN-HOUSEHOLD AGE SPAN ─────────────────────────────────────────────
spans = []
for hh in data:
    if len(hh['members']) > 1:
        ages = [m['age_group'] for m in hh['members']]
        spans.append(max(ages) - min(ages))

spans = np.array(spans)
print(f"Age span in multi-person HH (in 5-year band units, N={len(spans)}):")
print(f"  Mean:   {spans.mean():.2f} bands (~{spans.mean()*5:.0f} years)")
print(f"  Median: {np.median(spans):.1f} bands (~{np.median(spans)*5:.0f} years)")
print(f"  Span=0 (all same band): {np.sum(spans==0)} ({100*np.mean(spans==0):.1f}%)")
print(f"  Span>=3 bands (>=15yr): {np.sum(spans>=3)} ({100*np.mean(spans>=3):.1f}%)")
print(f"  Span>=6 bands (>=30yr): {np.sum(spans>=6)} ({100*np.mean(spans>=6):.1f}%)")
print()

# ── 7. COARSE 5-BAND ELSTAT GROUPINGS ────────────────────────────────────────
ELSTAT5 = {
    '0-14' : set(range(0, 3)),
    '15-29': set(range(3, 6)),
    '30-44': set(range(6, 9)),
    '45-64': set(range(9, 13)),
    '65+'  : set(range(13, 16)),
}

print("Singleton age distribution by ELSTAT 5-band grouping:")
sing_elstat = defaultdict(int)
for hh in singletons:
    ag = hh['members'][0]['age_group']
    for label, bands in ELSTAT5.items():
        if ag in bands:
            sing_elstat[label] += 1
            break
for label in ELSTAT5:
    n = sing_elstat[label]
    print(f"  {label:5s}: {n:5d}  ({100*n/n_singletons:.2f}%)")
print()

# Also print singleton RATE by ELSTAT 5-band
print("Singleton rate by ELSTAT 5-band grouping:")
for label, bands in ELSTAT5.items():
    tot = sum(band_total.get(ag, 0) for ag in bands)
    s   = sum(band_single.get(ag, 0) for ag in bands)
    print(f"  {label:5s}: {s}/{tot} = {100*s/tot:.1f}%")

print()
print("Done.")
