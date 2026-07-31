"""
verify_population.py — Hardened population verification.

Usage:
    python verify_population.py <population.json> [baseline.json]

<population.json>  : file to verify (repaired or regenerated)
[baseline.json]    : optional baseline to diff against (e.g. the buggy original)

Checks, in order:
  A. Structural integrity (counts, household_id uniqueness, attribute ranges)
  B. Band solo rates — ALL 16 bands, with collateral-movement detection
  C. Household size distribution (+ chi-square if WG_REF is filled in)
  D. Target-band co-residence profile vs. reference band
  E. Age-structure marginals
  F. Gender, employment, education marginals
  G. Repair-specific checks (only when baseline provided)

The script deliberately checks reference bands alongside the target band.
Collateral movement in any reference band is reported as a warning, not
silently dropped. This was the gap in the original verify_repair.py.

Fill WG_REF (Section C) with ELSTAT Western Greece 2021 proportions before
running chi-square. Until then that cell is clearly marked NOT RUN.
"""
import json
import sys
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

# -- Config --------------------------------------------------------------------
# Target band: the one the repair touched. Also used to parameterise checks.
TARGET_BAND   = 14       # 70-74, the band with the synthesis bug
REPAIR_BANDS  = {13, 14, 15}   # bands that should be checked for movement

# Expected total people for the canonical Patras file (215,927).
# The synthesis is stochastic and not bit-identical across Python/NumPy versions;
# a fresh run reproduces this to within ~0.02%, so the check below uses a tolerance
# band rather than exact equality. Set EXPECTED_TOTAL to None to skip it (e.g. the
# full-Achaia file).
EXPECTED_TOTAL = 215927
EXPECTED_TOTAL_TOL = 0.005  # +/-0.5% band around the canonical count

# Western Greece 2021 household-size proportions for chi-square (T3.1).
# Sizes 1, 2, 3, 4, 5+. Source: ELSTAT 2021 Population-Housing Census, release
# 31.08.2023, Western Greece region (Δυτική Ελλάδα).
# Raw counts: 82783, 70859, 44848, 37766, 21083 (total 257339 private households).
WG_REF = [82783/257339, 70859/257339, 44848/257339, 37766/257339, 21083/257339]

# Max plausible household size. Households above this are flagged.
MAX_HH_SIZE = 7

# Attribute ranges (for out-of-range detection)
ATTR_RANGES = {
    'gender':     (0, 1),
    'age_group':  (0, 15),
    'employment': (0, 6),
    'education':  (0, 13),
}

# Age band labels for display
BAND_AGES = [
    '0-4','5-9','10-14','15-19','20-24','25-29',
    '30-34','35-39','40-44','45-49','50-54','55-59',
    '60-64','65-69','70-74','75+',
]

# -- Helpers -------------------------------------------------------------------

def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def all_members(hh_list):
    return [m for h in hh_list for m in h['members']]

def solo_rate(hh_list, members, band):
    tot  = sum(1 for m in members if m['age_group'] == band)
    solo = sum(1 for h in hh_list
               if len(h['members']) == 1 and h['members'][0]['age_group'] == band)
    return (solo, tot, solo / tot if tot else float('nan'))

def cohab_profile(hh_list, band):
    """Return Counter of co-resident age_group values for households containing `band`."""
    c = Counter()
    for h in hh_list:
        if len(h['members']) < 2:
            continue
        bands = [m['age_group'] for m in h['members']]
        if band in bands:
            for x in bands:
                if x != band:
                    c[x] += 1
    return c

def size_distribution(hh_list):
    sizes = [len(h['members']) for h in hh_list]
    return Counter(sizes), sizes


# -- Load ----------------------------------------------------------------------

if len(sys.argv) < 2:
    sys.exit('Usage: python verify_population.py <population.json> [baseline.json]')

pop_path      = Path(sys.argv[1])
baseline_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None

print('=' * 70)
print(f'Population verification: {pop_path.name}')
if baseline_path:
    print(f'Baseline:               {baseline_path.name}')
print('=' * 70)

HH = load(pop_path)
members = all_members(HH)

HH_base     = load(baseline_path)    if baseline_path else None
members_base = all_members(HH_base)  if HH_base       else None

print(f'\n  Population:  {len(HH):,} households, {len(members):,} people')
if HH_base:
    print(f'  Baseline:    {len(HH_base):,} households, {len(members_base):,} people')

warnings = []
failures = []


# -- A. Structural integrity ---------------------------------------------------
print('\n' + '-' * 70)
print('A. STRUCTURAL INTEGRITY')

if EXPECTED_TOTAL is not None:
    lo = int(EXPECTED_TOTAL * (1 - EXPECTED_TOTAL_TOL))
    hi = int(EXPECTED_TOTAL * (1 + EXPECTED_TOTAL_TOL))
    if lo <= len(members) <= hi:
        print(f'  [PASS] Total people: {len(members):,} '
              f'(within {EXPECTED_TOTAL_TOL:.1%} of canonical {EXPECTED_TOTAL:,})')
    else:
        msg = (f'Total people {len(members):,} outside +/-{EXPECTED_TOTAL_TOL:.1%} '
               f'of expected {EXPECTED_TOTAL:,}')
        failures.append(f'A1: {msg}')
        print(f'  [FAIL] {msg}')

# Unique household_id
ids = [h.get('household_id') for h in HH]
dupes = len(ids) - len(set(ids))
if dupes == 0:
    print(f'  [PASS] household_id unique ({len(ids):,} distinct)')
else:
    failures.append(f'A2: {dupes} duplicate household_id values')
    print(f'  [FAIL] {dupes} duplicate household_id values')

# Households over size cap
oversized = [h for h in HH if len(h['members']) > MAX_HH_SIZE]
if not oversized:
    print(f'  [PASS] No household exceeds size cap ({MAX_HH_SIZE})')
else:
    msg = f'{len(oversized)} household(s) exceed size cap {MAX_HH_SIZE}'
    warnings.append(f'A3: {msg}')
    print(f'  [WARN] {msg}')

# Empty households
empty = sum(1 for h in HH if len(h['members']) == 0)
if empty == 0:
    print(f'  [PASS] No empty households')
else:
    failures.append(f'A4: {empty} empty household(s)')
    print(f'  [FAIL] {empty} empty household(s)')

# Attribute ranges
out_of_range = defaultdict(list)
for attr, (lo, hi) in ATTR_RANGES.items():
    for m in members:
        v = m.get(attr)
        if v is None or not (lo <= v <= hi):
            out_of_range[attr].append(v)
if not out_of_range:
    print(f'  [PASS] All member attributes within expected ranges')
else:
    for attr, vals in out_of_range.items():
        msg = f'{len(vals)} out-of-range values for {attr}: {sorted(set(vals))}'
        failures.append(f'A5: {msg}')
        print(f'  [FAIL] {msg}')


# -- B. Band solo rates ---------------------------------------------------------
print('\n' + '-' * 70)
print('B. BAND SOLO RATES')
print()

if HH_base:
    print(f'  {"band":>5}  {"age":>7}  {"base solo":>10}  {"pop solo":>10}  '
          f'{"delta pp":>9}  {"flag"}')
else:
    print(f'  {"band":>5}  {"age":>7}  {"solo rate":>10}  {"flag"}')

b14_rate_pop = None
collateral = []

for b in range(16):
    solo_n, tot, rate = solo_rate(HH, members, b)

    if HH_base:
        solo_n_b, tot_b, rate_b = solo_rate(HH_base, members_base, b)
        delta = rate - rate_b
        delta_str = f'{delta:>+9.1%}'

        # Classify: is this band expected to move, or collateral?
        if b == TARGET_BAND:
            flag = '  << TARGET (repaired)'
        elif b in REPAIR_BANDS and abs(delta) > 0.005:
            flag = f'  ** COLLATERAL MOVEMENT ({delta:+.1%})'
            collateral.append((b, rate_b, rate, delta))
        elif abs(delta) > 0.01:
            flag = f'  !! UNEXPECTED MOVEMENT ({delta:+.1%})'
            warnings.append(f'B: band {b} ({BAND_AGES[b]}) moved {delta:+.1%} unexpectedly')
        else:
            flag = ''

        print(f'  {b:>5}  {BAND_AGES[b]:>7}  {rate_b:>10.1%}  {rate:>10.1%}  '
              f'{delta_str}  {flag}')
    else:
        if b == TARGET_BAND:
            flag = '  << TARGET'
        elif b in REPAIR_BANDS:
            flag = '  (reference band)'
        else:
            flag = ''
        print(f'  {b:>5}  {BAND_AGES[b]:>7}  {rate:>10.1%}  {flag}')

    if b == TARGET_BAND:
        b14_rate_pop = rate

# Gate: pipeline.ipynb asserts solo_rate < 0.99
print()
if b14_rate_pop is not None:
    if b14_rate_pop < 0.99:
        print(f'  [PASS] Pipeline gate: band {TARGET_BAND} solo rate '
              f'{b14_rate_pop:.1%} < 99%')
    else:
        failures.append(f'B-gate: band {TARGET_BAND} solo rate {b14_rate_pop:.1%} >= 99%')
        print(f'  [FAIL] Pipeline gate: band {TARGET_BAND} solo rate '
              f'{b14_rate_pop:.1%} >= 99%')

# Solo-rate target range (informational — 0% passes the gate but is anomalous)
if b14_rate_pop is not None and HH_base:
    _, _, r13 = solo_rate(HH, members, 13)
    _, _, r15 = solo_rate(HH, members, 15)
    target = (r13 + r15) / 2
    print(f'  [INFO] Neighbour-interpolated target: ~{target:.1%}  '
          f'(avg of band 13={r13:.1%} and band 15={r15:.1%})')
    print(f'  [INFO] Band {TARGET_BAND} achieves: {b14_rate_pop:.1%}  '
          f'(delta from target: {b14_rate_pop - target:+.1%})')

# Collateral-movement summary
if collateral:
    print()
    print(f'  [WARN] Collateral movement in {len(collateral)} reference band(s):')
    for b, before, after, delta in collateral:
        print(f'         band {b} ({BAND_AGES[b]}): {before:.1%} -> {after:.1%}  ({delta:+.1%})')
    print()
    print('         These bands moved because some of their singletons were used as')
    print('         couple donors in the repair. This violates the "surgical, target-')
    print('         band-only" design claim. Movements are demographically plausible')
    print('         but mean the repair touched more than the defective households.')
    for b, before, after, delta in collateral:
        warnings.append(
            f'B-collateral: band {b} ({BAND_AGES[b]}) solo rate moved '
            f'{before:.1%} -> {after:.1%} ({delta:+.1%})'
        )


# -- C. Household size distribution --------------------------------------------
print('\n' + '-' * 70)
print('C. HOUSEHOLD SIZE DISTRIBUTION')
print()

sc, sizes = size_distribution(HH)
n_hh = len(HH)

# 5-category observed vector
cats  = ['1', '2', '3', '4', '5+']
obs   = np.array([
    sc.get(1, 0), sc.get(2, 0), sc.get(3, 0), sc.get(4, 0),
    sum(sc.get(s, 0) for s in sc if s >= 5),
], dtype=float)
obs_p = obs / obs.sum()

if HH_base:
    sc_b, sizes_b = size_distribution(HH_base)
    n_hh_b = len(HH_base)
    obs_b  = np.array([
        sc_b.get(1,0), sc_b.get(2,0), sc_b.get(3,0), sc_b.get(4,0),
        sum(sc_b.get(s,0) for s in sc_b if s >= 5),
    ], dtype=float)
    obs_bp = obs_b / obs_b.sum()
    print(f'  {"size":>5}  {"base n":>8}  {"base %":>8}  '
          f'{"pop n":>8}  {"pop %":>8}  {"delta pp":>9}')
    for c, on, op, bn, bp in zip(cats, obs.astype(int), obs_p,
                                  obs_b.astype(int), obs_bp):
        print(f'  {c:>5}  {int(bn):>8,}  {bp:>8.2%}  '
              f'{on:>8,}  {op:>8.2%}  {op-bp:>+9.2%}')
    print(f'  {"mean":>5}  {sum(sizes_b)/n_hh_b:>8.4f}           '
          f'{sum(sizes)/n_hh:>8.4f}')
else:
    print(f'  {"size":>5}  {"n":>8}  {"share":>8}')
    for c, on, op in zip(cats, obs.astype(int), obs_p):
        print(f'  {c:>5}  {on:>8,}  {op:>8.2%}')
    print(f'  mean: {sum(sizes)/n_hh:.4f}')

print()
if WG_REF is None:
    print('  [NOT RUN] Chi-square vs WG reference: fill WG_REF at top of script.')
    print('  Observed 5-category vector (paste into notes):')
    vec = ', '.join(f'{p:.4f}' for p in obs_p)
    print(f'    obs proportions = [{vec}]')
else:
    from scipy.stats import chisquare
    assert abs(sum(WG_REF) - 1.0) < 1e-6, 'WG_REF must sum to 1'
    chi2, p = chisquare(f_obs=obs, f_exp=np.array(WG_REF) * obs.sum())
    print(f'  Chi-square = {chi2:.3f},  p = {p:.4f}  (df=4)')


# -- D. Co-residence profile ---------------------------------------------------
print('\n' + '-' * 70)
print(f'D. CO-RESIDENCE PROFILE — target band {TARGET_BAND} '
      f'({BAND_AGES[TARGET_BAND]}) vs. reference bands')
print()

cohab_target = cohab_profile(HH, TARGET_BAND)
total_target = sum(cohab_target.values())

# Reference bands for comparison
ref_bands = sorted(REPAIR_BANDS - {TARGET_BAND})
cohab_refs = {b: cohab_profile(HH, b) for b in ref_bands}
total_refs  = {b: sum(cohab_refs[b].values()) for b in ref_bands}

ref_hdrs = '  '.join(f'band {b} share' for b in ref_bands)
print(f'  {"band":>5}  {"age":>7}  {"target n":>10}  {"target %":>10}  '
      f'  {ref_hdrs}')

all_cohab_bands = sorted(
    set(cohab_target.keys()) | set().union(*[c.keys() for c in cohab_refs.values()])
)
for b in all_cohab_bands:
    tn = cohab_target.get(b, 0)
    tp = tn / total_target if total_target else 0
    ref_parts = '  '.join(
        f'{cohab_refs[rb].get(b,0)/total_refs[rb]:>13.1%}' if total_refs[rb] else '         N/A'
        for rb in ref_bands
    )
    print(f'  {b:>5}  {BAND_AGES[b]:>7}  {tn:>10,}  {tp:>10.1%}    {ref_parts}')

print()
# Top 5 co-residents for target band
top5 = cohab_target.most_common(5)
print(f'  Top co-residents of band {TARGET_BAND}:')
for b, n in top5:
    print(f'    band {b} ({BAND_AGES[b]}): {n:,}  ({n/total_target:.1%})')

# Check: are same-generation bands the plurality?
same_gen_share = sum(cohab_target.get(b, 0) for b in (12, 13, 15)) / total_target if total_target else 0
print(f'  Same-generation share (bands 12/13/15): {same_gen_share:.1%}  '
      f'({"OK > 40%" if same_gen_share > 0.40 else "LOW — check scoring"})')


# -- E. Age structure ----------------------------------------------------------
print('\n' + '-' * 70)
print('E. AGE STRUCTURE MARGINALS')

COLLAPSE = {
    '0-14':  [0, 1, 2],
    '15-29': [3, 4, 5],
    '30-44': [6, 7, 8],
    '45-64': [9, 10, 11, 12],
    '65+':   [13, 14, 15],
}
age_counts = Counter(m['age_group'] for m in members)
total_p = len(members)
print()
for band_label, ks in COLLAPSE.items():
    n = sum(age_counts[k] for k in ks)
    print(f'  {band_label:>6}: {n:>7,}  ({n/total_p:.2%})')
if HH_base:
    print()
    print('  [NOTE] Marginals should be identical to baseline.')
    age_counts_b = Counter(m['age_group'] for m in members_base)
    total_pb = len(members_base)
    changed = [(b, age_counts_b[b], age_counts[b])
               for b in range(16) if age_counts_b[b] != age_counts[b]]
    if not changed:
        print('  [PASS] All 16 age-group counts identical to baseline.')
    else:
        for b, before, after in changed:
            msg = f'age_group {b} count changed: {before} -> {after}'
            failures.append(f'E: {msg}')
            print(f'  [FAIL] {msg}')


# -- F. Attribute marginals ----------------------------------------------------
print('\n' + '-' * 70)
print('F. ATTRIBUTE MARGINALS (gender, employment, education)')
print()

for attr in ('gender', 'employment', 'education'):
    counts = Counter(m[attr] for m in members)
    print(f'  {attr}:')
    for k in sorted(counts):
        print(f'    {k}: {counts[k]:>7,}  ({counts[k]/total_p:.2%})')

if HH_base:
    print()
    print('  [NOTE] All marginals must be identical to baseline (repair moves people, '
          'never alters attributes).')
    for attr in ('gender', 'employment', 'education'):
        c = Counter(m[attr] for m in members)
        cb = Counter(m[attr] for m in members_base)
        diffs = [(k, cb[k], c[k]) for k in set(c) | set(cb) if c[k] != cb[k]]
        if diffs:
            for k, before, after in diffs:
                msg = f'{attr}={k} count changed: {before} -> {after}'
                failures.append(f'F: {msg}')
                print(f'  [FAIL] {msg}')
    if not any(
        Counter(m[attr] for m in members) != Counter(m[attr] for m in members_base)
        for attr in ('gender', 'employment', 'education')
    ):
        print('  [PASS] gender, employment, education marginals unchanged.')


# -- G. Repair-specific checks (baseline required) ----------------------------
if HH_base:
    print('\n' + '-' * 70)
    print(f'G. REPAIR-SPECIFIC CHECKS (target band: {TARGET_BAND})')
    print()

    # Identify defective households in baseline
    def is_target_singleton(h):
        return len(h['members']) == 1 and h['members'][0]['age_group'] == TARGET_BAND

    n_defective_base = sum(1 for h in HH_base if is_target_singleton(h))
    n_defective_pop  = sum(1 for h in HH      if is_target_singleton(h))
    print(f'  Target-band singletons: {n_defective_base:,} (baseline) -> '
          f'{n_defective_pop:,} (repaired)')

    # Check population count: must stay exactly the same
    if len(members) == len(members_base):
        print(f'  [PASS] Population count preserved: {len(members):,}')
    else:
        delta = len(members) - len(members_base)
        failures.append(f'G1: population changed by {delta:+,}')
        print(f'  [FAIL] Population changed by {delta:+,}')

    # Households not in the target-singleton class: how many changed size?
    # Build lookup: orig households by id
    base_by_id = {h['household_id']: h for h in HH_base
                  if not is_target_singleton(h)}
    rep_by_id  = {h['household_id']: h for h in HH
                  if not is_target_singleton(h)}
    shared_ids = set(base_by_id) & set(rep_by_id)

    grown = [(hid, len(base_by_id[hid]['members']), len(rep_by_id[hid]['members']))
             for hid in shared_ids
             if len(rep_by_id[hid]['members']) != len(base_by_id[hid]['members'])]

    print(f'  Valid households that changed size: {len(grown):,}  '
          f'(expected: augmented donors)')

    if grown:
        delta_counts = Counter(after - before for _, before, after in grown)
        for d in sorted(delta_counts):
            print(f'    +{d} member(s): {delta_counts[d]:,} household(s)')

        # Check which bands are represented among the "donors"
        # (households that grew by exactly 1 and received a target-band member)
        absorbed_bands = Counter()
        for hid, _, _ in grown:
            if hid in rep_by_id:
                new_members = rep_by_id[hid]['members']
                old_members = base_by_id[hid]['members']
                added = [m for m in new_members if m not in old_members]
                for m in added:
                    absorbed_bands[m['age_group']] += 1
        if absorbed_bands:
            print(f'  Bands absorbed into growing households:')
            for b in sorted(absorbed_bands):
                print(f'    band {b} ({BAND_AGES[b]}): {absorbed_bands[b]:,}')
            non_target = {b: n for b, n in absorbed_bands.items() if b != TARGET_BAND}
            if non_target:
                msg = (f'Households absorbed non-target-band members: '
                       f'{dict(non_target)}')
                warnings.append(f'G2: {msg}')
                print(f'  [WARN] {msg}')
            else:
                print(f'  [PASS] All absorbed members are band {TARGET_BAND}')

    # Collateral-singleton consumption: how many band-13/15 singletons became multi-person?
    print()
    print('  Collateral singleton consumption by band:')
    for b in sorted(REPAIR_BANDS - {TARGET_BAND}):
        singletons_base = {h['household_id'] for h in HH_base
                           if is_target_singleton(h) is False
                           and len(h['members']) == 1
                           and h['members'][0]['age_group'] == b}
        singletons_rep  = {h['household_id'] for h in HH
                           if len(h['members']) == 1
                           and h['members'][0]['age_group'] == b}
        consumed = len(singletons_base - singletons_rep)
        pct = consumed / len(singletons_base) if singletons_base else 0
        flag = '  ** collateral' if consumed > 0 else ''
        print(f'    band {b} ({BAND_AGES[b]}): {len(singletons_base):,} singletons '
              f'-> {consumed:,} consumed ({pct:.1%} of that band\'s singletons){flag}')


# -- Summary -------------------------------------------------------------------
print('\n' + '=' * 70)
print('SUMMARY')
print()

if failures:
    print(f'  FAILURES ({len(failures)}):')
    for f in failures:
        print(f'    [FAIL] {f}')
else:
    print('  No failures.')

if warnings:
    print(f'\n  WARNINGS ({len(warnings)}):')
    for w in warnings:
        print(f'    [WARN] {w}')
else:
    print('  No warnings.')

print()
if not failures:
    print('  Result: PASS (gate conditions met)')
    if warnings:
        print('          See warnings above before treating as a publishable population.')
else:
    print('  Result: FAIL')
    sys.exit(1)
