"""Section 5.2: joint-distribution TV distance and KL divergence.

Two cross-tabulations:
  1. Age (16 bands) x Employment (7 categories)
  2. Education (14 levels) x Employment (7 categories)

Reference: ELSTAT Achaia 2021 aggregates (achaia_work_total_expanded.csv,
           gender_education_employment_total.csv).
Synthetic: synthetic_population_with_households.csv (seed-42 canonical run)
           from Thesis_Synthpop-main/python_ipf/ipf_results/.

Employment encoding in synthetic CSV (same order as ELSTAT CSV columns):
  0 = active_employed
  1 = active_unemployed
  2 = inactive_students
  3 = inactive_pensioners
  4 = inactive_income_recip
  5 = inactive_homemakers
  6 = inactive_others
"""

import numpy as np
import pandas as pd
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(ROOT, 'Thesis_Synthpop-main', 'python_ipf', 'marginal_distributions')
SYNTH_CSV = os.path.join(ROOT, 'Thesis_Synthpop-main', 'python_ipf', 'ipf_results',
                         'synthetic_population_with_households.csv')

EPS = 1e-9  # Laplace smoothing for KL divergence


def tv_distance(p, q):
    p = np.array(p, dtype=float)
    q = np.array(q, dtype=float)
    p = p / p.sum()
    q = q / q.sum()
    return 0.5 * np.abs(p - q).sum()


def kl_divergence(p, q, eps=EPS):
    p = np.array(p, dtype=float)
    q = np.array(q, dtype=float)
    p = (p + eps) / (p + eps).sum()
    q = (q + eps) / (q + eps).sum()
    return float(np.sum(p * np.log(p / q)))


def load_elstat_age_emp():
    """Return ELSTAT Achaia age x employment matrix (16 x 7)."""
    path = os.path.join(DIST_DIR, 'work', 'local', 'achaia_work_total_expanded.csv')
    df = pd.read_csv(path)
    # Drop sum row and aggregate columns; keep employment category columns
    df = df[df['age_group'] != 'sum'].copy()
    emp_cols = ['active_employed', 'active_unemployed', 'inactive_students',
                'inactive_pensioners', 'inactive_income_recip',
                'inactive_homemakers', 'inactive_others']
    mat = df[emp_cols].values.astype(float)   # shape (16, 7) — 16 age rows, 7 emp cols
    return mat


def load_elstat_edu_emp():
    """Return ELSTAT Achaia education x employment matrix (13 x 7).
    First row is sum — skip it. Education rows 0..12 correspond to education levels 1..13
    (level 0 is missing/special)."""
    path = os.path.join(DIST_DIR, 'education', 'gender_education_employment_total.csv')
    df = pd.read_csv(path)
    # Drop the sum row (education == 'sum')
    df = df[df['education'] != 'sum'].copy()
    emp_cols = ['active_employed', 'active_unemployed', 'inactive_students',
                'inactive_pensioners', 'inactive_income_recip',
                'inactive_homemakers', 'inactive_others']
    mat = df[emp_cols].values.astype(float)
    return mat


def main():
    synth = pd.read_csv(SYNTH_CSV)
    # Use Achaia totals (all 5 locations) for comparison
    print(f'Synthetic population: {len(synth):,} individuals (all Achaia locations)')

    # ----------------------------------------------------------------
    # Table 1: Age x Employment
    # ----------------------------------------------------------------
    elstat_ae = load_elstat_age_emp()  # (16, 7)
    synth_ae = (
        synth.groupby(['age_group', 'employment'])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=range(7), fill_value=0)
        .values
        .astype(float)
    )  # (16, 7)

    ae_tv = tv_distance(synth_ae.flatten(), elstat_ae.flatten())
    ae_kl = kl_divergence(synth_ae.flatten(), elstat_ae.flatten())

    print('\n=== Table 1: Age x Employment ===')
    print(f'  Synthetic shape: {synth_ae.shape}, ELSTAT shape: {elstat_ae.shape}')
    print(f'  TV distance : {ae_tv:.4f}')
    print(f'  KL divergence (synth || ELSTAT): {ae_kl:.4f}')

    # Per-age-group TV
    print('\n  Per-age-group TV distance:')
    bands = ['0-4','5-9','10-14','15-19','20-24','25-29','30-34','35-39',
             '40-44','45-49','50-54','55-59','60-64','65-69','70-74','75+']
    for i, band in enumerate(bands):
        row_tv = tv_distance(synth_ae[i], elstat_ae[i])
        print(f'    {band:>6}:  TV={row_tv:.4f}')

    # ----------------------------------------------------------------
    # Table 2: Education x Employment
    # ----------------------------------------------------------------
    elstat_ee = load_elstat_edu_emp()  # (13, 7)
    # Map synthetic education values: use the education column directly
    # Education levels in synthetic: 0..13 (0-indexed). ELSTAT has 13 rows (education levels)
    max_edu = elstat_ee.shape[0]
    # Use only education levels that appear in ELSTAT (0..max_edu-1)
    synth_ee = (
        synth[synth['education'] < max_edu]
        .groupby(['education', 'employment'])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=range(7), fill_value=0)
    )
    # Reindex to include all education levels 0..max_edu-1
    synth_ee = synth_ee.reindex(index=range(max_edu), fill_value=0).values.astype(float)

    ee_tv = tv_distance(synth_ee.flatten(), elstat_ee.flatten())
    ee_kl = kl_divergence(synth_ee.flatten(), elstat_ee.flatten())

    print('\n=== Table 2: Education x Employment ===')
    print(f'  Synthetic shape: {synth_ee.shape}, ELSTAT shape: {elstat_ee.shape}')
    print(f'  TV distance : {ee_tv:.4f}')
    print(f'  KL divergence (synth || ELSTAT): {ee_kl:.4f}')

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    print('\n=== SUMMARY FOR MANUSCRIPT (Section 5.2) ===')
    print(f'  Age x Employment:   TV = {ae_tv:.4f},  KL = {ae_kl:.4f}')
    print(f'  Education x Employment: TV = {ee_tv:.4f},  KL = {ee_kl:.4f}')
    print()
    print('Fill [PLACEHOLDER] Section 5.2 with these values.')
    print('Note: Both comparisons use Achaia-scale reference (the IPF calibration target).')


if __name__ == '__main__':
    main()
