"""Build agents_patras_s3.csv from patras_households_s3.json (S3 = WG-reweighted
household population; robustness experiment for the S3-vs-shuffle contrast).

Identical schema/logic to build_agents.py, adapted to:
  (a) read the S3 household population instead of the S1 canonical one, and
  (b) NOT hard-assert the S1 exact row/household counts (215927 / 82507), since
      the S3 household-size distribution differs by construction (more, smaller
      households -> different household count for the same underlying
      individual-level population).

Output schema matches build_agents.py / the old df_88225.csv:
  Family_ID, Gender, Age, Work_ID, School_ID, Infection_Status

See build_agents.py for full column/ID documentation (age-band midpoints,
Work_ID / School_ID construction). Logic is copied verbatim from there.
"""
import json
import pandas as pd
import numpy as np
import os

AGE_BOUNDS = {
    0: (0,  4),  1: (5,  9),  2: (10, 14),  3: (15, 19),
    4: (20, 24), 5: (25, 29), 6: (30, 34),  7: (35, 39),
    8: (40, 44), 9: (45, 49), 10:(50, 54), 11: (55, 59),
   12: (60, 64), 13:(65, 69), 14:(70, 74), 15: (75, 84),
}

WORK_GROUP_SIZE   = 30
SCHOOL_GROUP_SIZE = 30

BASE  = os.path.dirname(os.path.abspath(__file__))
HH_PATH = os.path.join(BASE, '..', 'data', 'synthpop', 'patras_households_s3.json')
OUT_CSV = os.path.join(BASE, 'agents_patras_s3.csv')

rng = np.random.default_rng(42)   # seeded for reproducibility of integer ages (matches build_agents.py)

print(f"Loading {HH_PATH} ...")
with open(HH_PATH) as f:
    households = json.load(f)

print(f"  {len(households):,} households")

rows = []
work_counter  = {loc: 0 for loc in range(5)}
school_counter = {}

for hh in households:
    hh_id = int(hh['household_id'])
    for m in hh['members']:
        gender     = int(m['gender'])
        age_group  = int(m['age_group'])
        employment = int(m['employment'])
        emp_loc    = int(m['employment_location'])
        lo, hi = AGE_BOUNDS[age_group]
        age = int(rng.integers(lo, hi + 1))

        if employment == 0 and emp_loc < 5:
            idx = work_counter[emp_loc]
            work_id = emp_loc * 10000 + (idx // WORK_GROUP_SIZE)
            work_counter[emp_loc] += 1
        else:
            work_id = -1

        if age_group <= 2:
            key = age_group
            school_counter.setdefault(key, 0)
            idx = school_counter[key]
            school_id = key * 10000 + (idx // SCHOOL_GROUP_SIZE)
            school_counter[key] += 1
        elif employment == 2:
            key = 100 + age_group
            school_counter.setdefault(key, 0)
            idx = school_counter[key]
            school_id = key * 10000 + (idx // SCHOOL_GROUP_SIZE)
            school_counter[key] += 1
        else:
            school_id = -1

        rows.append({
            'Family_ID':        hh_id,
            'Gender':           gender,
            'Age':              age,
            'Work_ID':          work_id,
            'School_ID':        school_id,
            'Infection_Status': 'S',
        })

df = pd.DataFrame(rows)

n_hh = df['Family_ID'].nunique()
mean_sz = len(df) / n_hh
assert (df['Infection_Status'] == 'S').all(), "Not all agents start as S"
print(f"S3 population: {len(df):,} agents, {n_hh:,} households, mean size {mean_sz:.4f}")
print(f"Work groups:   {df['Work_ID'].nunique() - 1} (plus -1 sentinel)")
print(f"School groups: {df['School_ID'].nunique() - 1} (plus -1 sentinel)")

df.to_csv(OUT_CSV, index=False)
print(f"Saved: {OUT_CSV}")
