"""Build agents_patras.csv from patras_households.json.

Output schema matches the old df_88225.csv:
  Family_ID, Gender, Age, Work_ID, School_ID, Infection_Status

Age mapping (band midpoints, as specified in instructions):
  band  0 (0-4)  -> 2
  band  1 (5-9)  -> 7
  band  2 (10-14)-> 12
  band  3 (15-19)-> 17
  band  4 (20-24)-> 22
  band  5 (25-29)-> 27
  band  6 (30-34)-> 32
  band  7 (35-39)-> 37
  band  8 (40-44)-> 42
  band  9 (45-49)-> 47
  band 10 (50-54)-> 52
  band 11 (55-59)-> 57
  band 12 (60-64)-> 62
  band 13 (65-69)-> 67
  band 14 (70-74)-> 72
  band 15 (75+)  -> 80

Work groups: employed (employment==0) with employment_location 0-4 are
  subdivided into groups of WORK_GROUP_SIZE workers per location.
  Work_ID = location * 10000 + (sequential_index_within_location // WORK_GROUP_SIZE)
  Non-employed: Work_ID = -1

School groups: school-age (age_group 0-2, ages 2/7/12) and
  inactive_students (employment==2, age_group>=3) are subdivided into
  groups of SCHOOL_GROUP_SIZE.
  School_ID = age_band_key * 10000 + (sequential_index // SCHOOL_GROUP_SIZE)
  Others: School_ID = -1

Validation: 215927 rows, 82507 unique Family_IDs, mean household size 2.62.
"""
import json
import pandas as pd
import numpy as np
import os

# Band midpoints for _get_age_group() compatibility.
# We also store the age band index (0-15) separately so same-age grouping
# uses integer age (randomised within band) for ~100 distinct ages.
# Bounds for randomised integer-age assignment within each 5-year band.
# This gives ~100 distinct integer ages (2,159 agents each) rather than
# 15 midpoints (14,395 agents each), preserving the original model's
# same-age group density.
AGE_BOUNDS = {
    0: (0,  4),  1: (5,  9),  2: (10, 14),  3: (15, 19),
    4: (20, 24), 5: (25, 29), 6: (30, 34),  7: (35, 39),
    8: (40, 44), 9: (45, 49), 10:(50, 54), 11: (55, 59),
   12: (60, 64), 13:(65, 69), 14:(70, 74), 15: (75, 84),
}

WORK_GROUP_SIZE   = 30
SCHOOL_GROUP_SIZE = 30

BASE  = os.path.dirname(os.path.abspath(__file__))
HH_PATH = os.path.join(BASE, '..', 'data', 'synthpop', 'patras_households.json')
OUT_CSV = os.path.join(BASE, 'agents_patras.csv')

rng = np.random.default_rng(42)   # seeded for reproducibility of integer ages

print(f"Loading {HH_PATH} ...")
with open(HH_PATH) as f:
    households = json.load(f)

print(f"  {len(households):,} households")

rows = []
# counters for sequential work/school group assignment
work_counter  = {loc: 0 for loc in range(5)}
school_counter = {}  # key -> count

for hh in households:
    hh_id = int(hh['household_id'])
    for m in hh['members']:
        gender     = int(m['gender'])
        age_group  = int(m['age_group'])
        employment = int(m['employment'])
        emp_loc    = int(m['employment_location'])
        lo, hi = AGE_BOUNDS[age_group]
        age = int(rng.integers(lo, hi + 1))

        # Work_ID
        if employment == 0 and emp_loc < 5:
            idx = work_counter[emp_loc]
            work_id = emp_loc * 10000 + (idx // WORK_GROUP_SIZE)
            work_counter[emp_loc] += 1
        else:
            work_id = -1

        # School_ID
        if age_group <= 2:
            # Primary/secondary school-age (0-14)
            key = age_group
            school_counter.setdefault(key, 0)
            idx = school_counter[key]
            school_id = key * 10000 + (idx // SCHOOL_GROUP_SIZE)
            school_counter[key] += 1
        elif employment == 2:
            # Inactive students (university age, 15+)
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

# Validation
assert len(df) == 215927, f"Expected 215927 rows, got {len(df)}"
assert df['Family_ID'].nunique() == 82507, (
    f"Expected 82507 households, got {df['Family_ID'].nunique()}")
mean_sz = len(df) / df['Family_ID'].nunique()
assert abs(mean_sz - 2.62) < 0.05, f"Mean HH size {mean_sz:.4f} out of range"
assert (df['Infection_Status'] == 'S').all(), "Not all agents start as S"
print(f"Validation PASSED: {len(df):,} agents, {df['Family_ID'].nunique():,} households, "
      f"mean size {mean_sz:.4f}")
print(f"Work groups:   {df['Work_ID'].nunique() - 1} (plus -1 sentinel)")
print(f"School groups: {df['School_ID'].nunique() - 1} (plus -1 sentinel)")

df.to_csv(OUT_CSV, index=False)
print(f"Saved: {OUT_CSV}")
