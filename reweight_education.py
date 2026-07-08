#!/usr/bin/env python3
"""
reweight_education.py
---------------------
Re-weight education codes in the Patras synthetic population so that
the education × age distribution matches ELSTAT B02 municipality-level
marginals for the Municipality of Patras (code 2423701).

Input:  data/synthpop/patras_households.json
Output: data/synthpop/patras_households_edu_reweighted.json
"""

import json
import os
import random
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))

# ── ELSTAT B02 marginals ─────────────────────────────────────────────────────
# Seven education columns per ELSTAT age band (cat index 0-6):
#   0: University+  (PhD/Masters/University/TEI/ASPAITE)
#   1: Post-secondary IEK / Colleges
#   2: High school diploma (Apolytirio Lykeio)
#   3: Vocational schools / 3-year Gymnasium
#   4: Elementary (Dimotiko)
#   5: No schooling / incomplete primary
#   6: Born post-2016 / too young
B02 = {
    "0-14":  [0,     0,    0,     387,   6702,  12842, 10653],
    "15-29": [8643,  1645, 24459, 6729,  713,   599,   0],
    "30-44": [17355, 3322, 15147, 3481,  1781,  536,   0],
    "45-59": [13711, 2494, 18273, 6355,  4889,  522,   0],
    "60-74": [7580,  1047, 9783,  4958,  11448, 919,   0],
    "75+":   [2211,  318,  3464,  2044,  8089,  2813,  0],
}

# ELSTAT age band → synthetic age_group indices (0-based, 5-year bands)
ELSTAT_AGE_MAP = {
    "0-14":  [0, 1, 2],
    "15-29": [3, 4, 5],
    "30-44": [6, 7, 8],
    "45-59": [9, 10, 11],
    "60-74": [12, 13, 14],
    "75+":   [15],
}

# ELSTAT cat index → valid ISTAT education codes for that category
# Two variants: one for children (0-14) and one for adults (15+)
ELSTAT_TO_ISTAT_ADULT = {
    0: [0, 1, 2, 3],   # University+
    1: [4],             # Post-secondary IEK
    2: [5, 6],          # High school
    3: [7, 8],          # Vocational/Gymnasium
    4: [9, 10],         # Elementary
    5: [11],            # No schooling
    # Category 6 ("born post-2016") is logically impossible for adults;
    # any adult with ISTAT code 13 is re-assigned via the excess pool.
}

ELSTAT_TO_ISTAT_CHILD = {
    0: [0, 1, 2, 3],
    1: [4],
    2: [5, 6],
    3: [7, 8],
    4: [9, 10],
    5: [11],
    6: [12, 13],        # too young (12) + born post-2016 (13) for children
}


def istat_to_elstat(istat_code: int, is_child: bool) -> int | None:
    """Map an ISTAT education code to an ELSTAT B02 category index (0-6).
    Returns None if the mapping is invalid (e.g. code 12 for an adult).
    """
    if istat_code in (0, 1, 2, 3):
        return 0
    if istat_code == 4:
        return 1
    if istat_code in (5, 6):
        return 2
    if istat_code in (7, 8):
        return 3
    if istat_code in (9, 10):
        return 4
    if istat_code == 11:
        return 5
    if istat_code == 12:
        return 6 if is_child else None   # "too young" only valid for children
    if istat_code == 13:
        return 6 if is_child else None   # "born post-2016" only valid for children
    return None


def largest_remainder_round(values: list[float], total: int) -> list[int]:
    """Round a list of floats to non-negative ints that sum exactly to *total*."""
    floored = [int(v) for v in values]
    remainders = sorted(
        range(len(values)), key=lambda i: -(values[i] - floored[i])
    )
    deficit = total - sum(floored)
    for i in range(deficit):
        floored[remainders[i]] += 1
    return floored


def reweight_band(
    households: list,
    member_refs: list[tuple[int, int]],
    b02_counts: list[int],
    is_child: bool,
    rng: random.Random,
) -> dict[int, list[int]]:
    """Reweight education for one ELSTAT age band in-place.

    Returns a dict with keys 'before' and 'after' — both are 7-element lists
    of per-ELSTAT-category member counts.
    """
    n = len(member_refs)
    b02_total = sum(b02_counts)
    if n == 0 or b02_total == 0:
        return {"before": [0] * 7, "after": [0] * 7}

    # ── current ELSTAT category for each member ──────────────────────────────
    current_cats = []
    for hi, mi in member_refs:
        edu = households[hi]["members"][mi]["education"]
        current_cats.append(istat_to_elstat(edu, is_child))

    before_counts = [
        sum(1 for c in current_cats if c == ci) for ci in range(7)
    ]

    # ── target counts from B02 proportions ───────────────────────────────────
    target_floats = [b02_counts[ci] / b02_total * n for ci in range(7)]
    target_counts = largest_remainder_round(target_floats, n)

    # ── group member refs by current ELSTAT category ─────────────────────────
    cat_members: dict[int | None, list[tuple[int, int]]] = defaultdict(list)
    for idx, ref in enumerate(member_refs):
        cat_members[current_cats[idx]].append(ref)

    # Shuffle each group so random selection is uniform
    for group in cat_members.values():
        rng.shuffle(group)

    # ── build excess pool (members that must change category) ─────────────────
    # Also include members with cat=None (invalid code — must be re-assigned)
    excess_pool: list[tuple[int, int]] = list(cat_members.get(None, []))

    for ci in range(7):
        members_here = cat_members[ci]
        target_n = target_counts[ci]
        if len(members_here) > target_n:
            excess_pool.extend(members_here[target_n:])
            cat_members[ci] = members_here[:target_n]
        # (under-represented cats are handled below)

    rng.shuffle(excess_pool)

    # ── assign excess pool to under-represented categories ────────────────────
    elstat_istat = ELSTAT_TO_ISTAT_CHILD if is_child else ELSTAT_TO_ISTAT_ADULT
    pool_ptr = 0

    for ci in range(7):
        need = target_counts[ci] - len(cat_members[ci])
        if need <= 0:
            continue
        new_istat_options = elstat_istat[ci]
        for _ in range(need):
            if pool_ptr >= len(excess_pool):
                break
            hi, mi = excess_pool[pool_ptr]
            pool_ptr += 1
            households[hi]["members"][mi]["education"] = rng.choice(
                new_istat_options
            )

    # ── compute after distribution ────────────────────────────────────────────
    after_counts = [0] * 7
    for hi, mi in member_refs:
        edu = households[hi]["members"][mi]["education"]
        cat = istat_to_elstat(edu, is_child)
        if cat is not None:
            after_counts[cat] += 1

    return {"before": before_counts, "after": after_counts}


# ── pretty-print helpers ─────────────────────────────────────────────────────

CAT_NAMES = [
    "University+",
    "Post-secondary IEK",
    "High school",
    "Vocational/Gymnasium",
    "Elementary",
    "No schooling",
    "Born post-2016",
]


def print_band_table(band: str, n: int, before: list, after: list, b02: list):
    b02_total = sum(b02)
    print(f"  Age band {band}  (synth n={n:,}  B02 total={b02_total:,})")
    hdr = f"  {'Category':<22} {'Before':>8} {'After':>8} {'B02':>8}  {'Δ%':>7}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for ci, name in enumerate(CAT_NAMES):
        b = before[ci]
        a = after[ci]
        t = b02[ci]
        t_prop = t / b02_total if b02_total else 0
        a_prop = a / n if n else 0
        delta = (a_prop - t_prop) * 100
        print(
            f"  {name:<22} {b:>8,} {a:>8,} {t:>8,}  {delta:>+6.2f}%"
        )
    print()


def main():
    rng = random.Random(42)

    input_path = os.path.join(ROOT, "data", "synthpop", "patras_households.json")
    output_path = os.path.join(
        ROOT, "data", "synthpop", "patras_households_edu_reweighted.json"
    )

    print(f"Loading {input_path} …")
    with open(input_path) as f:
        households = json.load(f)

    total_members = sum(len(h["members"]) for h in households)
    print(f"Households: {len(households):,}   Members: {total_members:,}\n")

    # Index all members by age_group for fast lookup
    age_to_refs: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for hi, hh in enumerate(households):
        for mi, member in enumerate(hh["members"]):
            age_to_refs[member["age_group"]].append((hi, mi))

    print("=" * 65)
    print("  Per-band education distribution (ELSTAT B02 categories)")
    print("=" * 65 + "\n")

    overall_before = [0] * 7
    overall_after  = [0] * 7
    overall_b02    = [0] * 7

    for band, age_groups in ELSTAT_AGE_MAP.items():
        is_child = (band == "0-14")
        member_refs = []
        for ag in age_groups:
            member_refs.extend(age_to_refs[ag])

        b02_counts = B02[band]
        result = reweight_band(
            households, member_refs, b02_counts, is_child, rng
        )

        print_band_table(
            band, len(member_refs),
            result["before"], result["after"], b02_counts
        )

        for ci in range(7):
            overall_before[ci] += result["before"][ci]
            overall_after[ci]  += result["after"][ci]
            overall_b02[ci]    += b02_counts[ci]

    # ── overall summary ───────────────────────────────────────────────────────
    print("=" * 65)
    print("  OVERALL (all age bands combined)")
    print("=" * 65)
    overall_b02_total = sum(overall_b02)
    print(
        f"  {'Category':<22} {'Before':>9} {'After':>9} {'B02':>9}  "
        f"{'Aft%':>6}  {'B02%':>6}"
    )
    print("  " + "-" * 62)
    for ci, name in enumerate(CAT_NAMES):
        b = overall_before[ci]
        a = overall_after[ci]
        t = overall_b02[ci]
        a_pct = 100 * a / total_members if total_members else 0
        t_pct = 100 * t / overall_b02_total if overall_b02_total else 0
        print(
            f"  {name:<22} {b:>9,} {a:>9,} {t:>9,}  "
            f"{a_pct:>5.2f}%  {t_pct:>5.2f}%"
        )
    print("  " + "-" * 62)
    print(
        f"  {'TOTAL':<22} {sum(overall_before):>9,} {sum(overall_after):>9,} "
        f"{overall_b02_total:>9,}"
    )

    # ── save ─────────────────────────────────────────────────────────────────
    print(f"\nSaving to {output_path} …")
    with open(output_path, "w") as f:
        json.dump(households, f, separators=(",", ":"))
    print("Done.")


if __name__ == "__main__":
    main()
