"""Child-adult co-residence relaxation-tier usage report (canonical seed 42).

main.tex reports "Plausible-adult present (child HH): 100.0%" for the child-
adult co-residence fallback (see Thesis_Synthpop-main/python_ipf/main_ipf_pipeline.py,
function create_households, the tiered parental-age relaxation loop). A
reviewer pointed out that a 100% figure is unambiguously reassuring only if it
is not achieved mostly through the loosest relaxation tier (>=1 band gap,
e.g. a 14-year-old paired with a 15-year-old "guardian").

This script re-runs the canonical seed-42 pipeline with lightweight, read-only
instrumentation enabled (TIER_STATS_OUTPUT env var; see main_ipf_pipeline.py)
that records, for every child (age 0-14) placed into a household, which tier
placed them:
  (a) greedy_no_relaxation -- normal greedy template match, no relaxation needed
  (b) tier_ge3band         -- attached via the >=3-band-gap tier (~15+ years)
  (c) tier_ge2band         -- attached via the >=2-band-gap tier (~10+ years)
  (d) tier_ge1band         -- attached via the loosest tier (fixed adult-band
                               threshold of 3, i.e. >=15y/o present; for a
                               band-2 child (10-14) this is a genuine >=1-band
                               (~5 year) gap tier)
  (e) forced_singleton     -- no compatible household found at any tier

The instrumentation does not consume random numbers and does not alter any
matching decision, so the resulting households.json is bit-identical to the
canonical (uninstrumented) run for the same seed.

IMPORTANT -- isolation: this repo lives in an actively-synced cloud folder
and is also used by other concurrent processes that independently invoke the
same pipeline script against the same shared output path
(Thesis_Synthpop-main/python_ipf/ipf_results/households.json). Empirically
confirmed to cause write races (a single-seed test's own stdout logged
correct seed-specific counts, but the file on disk read immediately
afterwards held different, unrelated counts). To get a trustworthy
instrumented run, this script executes the pipeline inside a private,
single-use copy of Thesis_Synthpop-main under the system temp dir (see
make_isolated_pipeline_copy, reused from household_composition_stability.py).

Run from GIS-paper-main/:
    python validation/relaxation_tier_report.py
"""
import json
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from household_composition_stability import make_isolated_pipeline_copy  # noqa: E402

PATRAS_ID = '2423701'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join('python_ipf', 'main_ipf_pipeline.py')
TIER_STATS_PATH_NAME = '_tier_stats_raw.json'

CHILD_BANDS = {0, 1, 2}
ADULT_OR_ELDERLY = set(range(3, 16))

TIER_ORDER = ['greedy_no_relaxation', 'tier_ge3band', 'tier_ge2band', 'tier_ge1band', 'forced_singleton']
TIER_LABEL = {
    'greedy_no_relaxation': '(a) Normal greedy template match (no relaxation)',
    'tier_ge3band': '(b) Relaxation tier >=3 bands (~15+ yr gap, "plausible parent")',
    'tier_ge2band': '(c) Relaxation tier >=2 bands (~10+ yr gap)',
    'tier_ge1band': '(d) Relaxation tier >=1 band (loosest; fixed threshold band>=3)',
    'forced_singleton': '(e) Could not be placed (forced child singleton)',
}


def run_instrumented_canonical(pipe_dir, tier_stats_path):
    print('Running canonical seed-42 pipeline with relaxation-tier instrumentation enabled...')
    env = os.environ.copy()
    env.pop('PIPELINE_SEED', None)  # use default SEED=42
    env['TIER_STATS_OUTPUT'] = tier_stats_path
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        cwd=pipe_dir,
        env=env,
        capture_output=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f'Pipeline exited with code {proc.returncode}')


def main():
    print('Creating isolated pipeline copy (immune to concurrent-process file races)...')
    pipe_dir = make_isolated_pipeline_copy()
    hh_path = os.path.join(pipe_dir, 'python_ipf', 'ipf_results', 'households.json')
    tier_stats_path = os.path.join(pipe_dir, TIER_STATS_PATH_NAME)
    print(f'Isolated copy: {pipe_dir}')

    if os.path.exists(hh_path):
        os.remove(hh_path)

    run_instrumented_canonical(pipe_dir, tier_stats_path)

    if not os.path.exists(hh_path):
        raise RuntimeError('households.json missing after instrumented run -- pipeline did not '
                            'complete successfully in the isolated copy.')

    with open(tier_stats_path) as f:
        raw = json.load(f)
    tier_stats_by_location = raw['tier_stats_by_location']
    tier_gap_records = raw['tier_gap_records']  # [location_id, child_ag, tier_name, gap]

    with open(hh_path) as f:
        hh_all = json.load(f)
    patras = [h for h in hh_all if h['location_id'] == PATRAS_ID]

    # Cross-check against the canonical structural metric (main.tex Table
    # tab:coresidence_metrics): "All 20,985 households with a 0-14-year-old
    # member ... contain at least one person aged 15 or over".
    child_hh = [h for h in patras if any(m['age_group'] in CHILD_BANDS for m in h['members'])]
    child_hh_with_adult = [
        h for h in child_hh if any(m['age_group'] in ADULT_OR_ELDERLY for m in h['members'])
    ]
    n_children_total = sum(
        1 for h in patras for m in h['members'] if m['age_group'] in CHILD_BANDS
    )

    # Patras-only tier counts
    patras_counts = tier_stats_by_location.get(PATRAS_ID, {})
    patras_counts = {k: patras_counts.get(k, 0) for k in TIER_ORDER}
    total_tiered = sum(patras_counts.values())

    # Gap diagnostic for the loosest tier, restricted to Patras
    patras_ge1_gaps = Counter(
        gap for loc, child_ag, tier, gap in tier_gap_records
        if loc == PATRAS_ID and tier == 'tier_ge1band'
    )
    patras_ge1_by_child_band = Counter(
        child_ag for loc, child_ag, tier, gap in tier_gap_records
        if loc == PATRAS_ID and tier == 'tier_ge1band'
    )

    lines = []
    lines.append('# Child-adult co-residence relaxation-tier usage report (Patras, canonical seed 42)\n')
    lines.append('Source: instrumented run of `Thesis_Synthpop-main/python_ipf/main_ipf_pipeline.py` '
                  '(`create_households`), `TIER_STATS_OUTPUT` instrumentation, PIPELINE_SEED unset '
                  '(default seed 42). Instrumentation is observation-only: it consumes no random '
                  'numbers and changes no matching decision, so the resulting household population '
                  'is bit-identical to the uninstrumented canonical run.\n')

    lines.append('## Cross-check against main.tex Table `tab:coresidence_metrics`\n')
    lines.append(f'- Households with a 0-14-year-old member: {len(child_hh):,} '
                  f'(manuscript states 20,985)')
    lines.append(f'- ...with at least one person aged 15+: {len(child_hh_with_adult):,} '
                  f'({100 * len(child_hh_with_adult) / len(child_hh):.1f}% of child households)')
    lines.append(f'- Total children (age 0-14) across these households: {n_children_total:,}\n')

    lines.append('## Tier usage (Patras, count of *children* placed at each tier)\n')
    lines.append('| Tier | Count | % of all children (0-14) |')
    lines.append('|---|---:|---:|')
    for key in TIER_ORDER:
        n = patras_counts[key]
        pct = 100 * n / total_tiered if total_tiered else 0.0
        lines.append(f'| {TIER_LABEL[key]} | {n:,} | {pct:.2f}% |')
    lines.append(f'| **Total** | **{total_tiered:,}** | **100.00%** |\n')

    lines.append('## Loosest-tier (>=1 band) diagnostic\n')
    lines.append('The `tier_ge1band` tier uses a *fixed* threshold (any household member in age '
                  'band >=3, i.e. 15+) rather than a threshold relative to the child\'s own band. '
                  'This means the band-gap it actually achieves varies with the child\'s age: for a '
                  'band-2 child (10-14) it is a genuine >=1-band (~5-14 year) gap tier; for band-0/1 '
                  'children it can coincide with, or be looser than, the nominal >=2-band tier.\n')
    lines.append('Children placed at `tier_ge1band`, broken down by their own age band:')
    lines.append('| Child age band | Age range | Children placed at loosest tier |')
    lines.append('|---:|---|---:|')
    _band_range = {0: '0-4', 1: '5-9', 2: '10-14'}
    for band in sorted(patras_ge1_by_child_band):
        lines.append(f'| {band} | {_band_range.get(band, "?")} | {patras_ge1_by_child_band[band]:,} |')
    lines.append('')
    lines.append('Achieved band-gap distribution for children placed at `tier_ge1band` '
                  '(gap = age band of the most senior existing household member minus the child\'s '
                  'own age band, measured *before* the child was attached):')
    lines.append('| Achieved gap (bands) | ~years | N |')
    lines.append('|---:|---:|---:|')
    for gap in sorted(patras_ge1_gaps):
        lines.append(f'| {gap} | ~{gap * 5} | {patras_ge1_gaps[gap]:,} |')
    lines.append('')

    pct_loosest = 100 * patras_counts['tier_ge1band'] / total_tiered if total_tiered else 0.0
    lines.append('## Assessment\n')
    if pct_loosest > 2.0:
        lines.append(
            f'**FLAG:** The loosest relaxation tier (`tier_ge1band`) accounts for '
            f'{pct_loosest:.2f}% of all children (0-14) in Patras households -- more than a '
            f'trivial share. The manuscript\'s "Plausible-adult present (child HH): 100.0%" framing '
            f'should be qualified: a non-trivial fraction of that 100% is achieved via the loosest '
            f'tier, which can admit gaps as small as ~1 band (~5 years, e.g. a 14-year-old with a '
            f'15-year-old co-resident) rather than the ~15-year "plausible parent" gap suggested by '
            f'the primary (>=3-band) tier.'
        )
    else:
        lines.append(
            f'The loosest relaxation tier (`tier_ge1band`) accounts for only {pct_loosest:.2f}% of '
            f'all children (0-14) in Patras households -- a small share. The "100.0% plausible-adult" '
            f'figure is overwhelmingly achieved via the normal greedy match or the strict (>=3-band) '
            f'relaxation tier, so the manuscript\'s framing does not appear to be an overclaim on this '
            f'point.'
        )

    report_path = os.path.join(ROOT, 'validation', 'relaxation_tier_report.md')
    with open(report_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    # Persist the raw instrumentation JSON alongside the report for provenance
    # before the isolated copy (which lives under /tmp) is cleaned up.
    persisted_raw_path = os.path.join(ROOT, 'validation', 'relaxation_tier_raw.json')
    shutil.copy(tier_stats_path, persisted_raw_path)

    print('\n'.join(lines))
    print(f'\nReport saved to {report_path}')
    print(f'Raw instrumentation JSON saved to {persisted_raw_path}')

    shutil.rmtree(os.path.dirname(pipe_dir), ignore_errors=True)


if __name__ == '__main__':
    main()
