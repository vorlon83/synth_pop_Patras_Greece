import numpy as np

# Seed used when stochastically splitting straddling Italian age buckets.
# Record this value in any publication that uses these templates.
AGE_MAP_SEED = 42

# Lookup tables for age groups
AGE_GROUP_LUT = {
    0: '0-4',
    1: '5-9',
    2: '10-14',
    3: '15-19',
    4: '20-24',
    5: '25-29',
    6: '30-34',
    7: '35-39',
    8: '40-44',
    9: '45-49',
    10: '50-54',
    11: '55-59',
    12: '60-64',
    13: '65-69',
    14: '70-74',
    15: '75+'
}

IT_LUT = {
    1: '0-2',
    2: '3-5',
    3: '6-10',
    4: '11-13',
    5: '14-15',
    6: '16-17',
    7: '18-19',
    8: '20-24',
    9: '25-29',
    10: '30-34',
    11: '35-39',
    12: '40-44',
    13: '45-49',
    14: '50-54',
    15: '55-59',
    16: '60-64',
    17: '65-74',
    18: '75+'
}

# Four Italian buckets straddle a Greek 5-year boundary and cannot be mapped
# deterministically to a single Greek band.  Each entry maps the IT bucket
# index to a list of (greek_band, weight) pairs whose weights sum to 1.
# Weights are proportional to the overlap width in years between the Italian
# bucket and each Greek band it touches.
#
#   IT bucket 2  (3–5):  ages 3–4 -> Greek band 0 (0–4),  age 5  -> band 1 (5–9)
#   IT bucket 3  (6–10): ages 6–9 -> Greek band 1 (5–9),  age 10 -> band 2 (10–14)
#   IT bucket 5  (14–15): age 14  -> Greek band 2 (10–14), age 15 -> band 3 (15–19)
#   IT bucket 17 (65–74): ages 65–69 -> band 13 (65–69), ages 70–74 -> band 14 (70–74)
#
# Bucket 17 is the critical one: it previously collapsed entirely into band 13,
# leaving band 14 (70–74) absent from all templates.
IT_TO_GREEK_SPLITS = {
    2:  [(0, 2/3), (1, 1/3)],
    3:  [(1, 4/5), (2, 1/5)],
    5:  [(2, 1/2), (3, 1/2)],
    # Bucket 17 (65-74) split weighted by the ELSTAT Achaia 2021 band-13:band-14
    # population ratio (12,033 : 10,451 = 0.535 : 0.465).  This grounds the
    # split in Greek census data rather than the uniform overlap width.
    17: [(13, 0.535), (14, 0.465)],
}


def sample_age_group(it_bucket, rng):
    """Return a Greek ELSTAT 5-year band for a single person with ISTAT
    age bucket *it_bucket*.

    For the 14 non-straddling buckets the mapping is deterministic and
    identical to it_to_age_group().  For the four straddling buckets
    (2, 3, 5, 17) the assignment is sampled from the two overlapping Greek
    bands with probability proportional to the overlap width in years.

    Parameters
    ----------
    it_bucket : int
        ISTAT age bucket index (key in IT_LUT, 1–18).
    rng : numpy.random.Generator
        Seeded generator, e.g. ``numpy.random.default_rng(AGE_MAP_SEED)``.

    Returns
    -------
    int or None
        Greek age group index 0–15, or None if *it_bucket* is unknown.
    """
    if it_bucket in IT_TO_GREEK_SPLITS:
        bands, weights = zip(*IT_TO_GREEK_SPLITS[it_bucket])
        return int(rng.choice(list(bands), p=list(weights)))
    return it_to_age_group(it_bucket)


def it_to_age_group(it_age_group):
    """Deterministic fallback mapping for non-straddling buckets.

    Straddling buckets (2, 3, 5, 17) return the *lower* overlapping band
    here; use sample_age_group() for correct per-member stochastic
    assignment.
    """
    it_range = IT_LUT.get(it_age_group)
    if it_range is None:
        return None

    if it_range == '75+':
        return 15

    start_age, end_age = map(int, it_range.split('-'))

    for age_group_idx, age_group in AGE_GROUP_LUT.items():
        if age_group == '75+':
            continue
        group_start, group_end = map(int, age_group.split('-'))
        if start_age >= group_start and end_age <= group_end:
            return age_group_idx

    for age_group_idx, age_group in AGE_GROUP_LUT.items():
        if age_group == '75+':
            continue
        group_start, group_end = map(int, age_group.split('-'))
        if start_age <= group_end and end_age >= group_start:
            return age_group_idx

    return 15


def get_conversion_mapping():
    """Deterministic mapping for inspection.  Straddling buckets show only
    the lower-band default; for per-member assignment use sample_age_group().
    """
    return {it_idx: it_to_age_group(it_idx) for it_idx in IT_LUT.keys()}


if __name__ == "__main__":
    rng = np.random.default_rng(AGE_MAP_SEED)
    mapping = get_conversion_mapping()
    for it_idx, age_group_idx in mapping.items():
        split = IT_TO_GREEK_SPLITS.get(it_idx)
        note = f"  ** STRADDLES -> {split}" if split else ""
        print(f"IT {it_idx:>2} ({IT_LUT[it_idx]:>5}) -> band {age_group_idx:>2} ({AGE_GROUP_LUT[age_group_idx]}){note}")
