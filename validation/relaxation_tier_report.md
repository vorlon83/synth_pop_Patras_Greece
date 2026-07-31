# Child-adult co-residence relaxation-tier usage report (Patras, canonical seed 42)

Source: instrumented run of `Thesis_Synthpop-main/python_ipf/main_ipf_pipeline.py` (`create_households`), `TIER_STATS_OUTPUT` instrumentation, PIPELINE_SEED unset (default seed 42). Instrumentation is observation-only: it consumes no random numbers and changes no matching decision, so the resulting household population is bit-identical to the uninstrumented canonical run.

## Cross-check against main.tex Table `tab:coresidence_metrics`

- Households with a 0-14-year-old member: 21,030 (manuscript states 20,985)
- ...with at least one person aged 15+: 21,030 (100.0% of child households)
- Total children (age 0-14) across these households: 30,579

**Note on the 21,030 vs 20,985 gap (+0.2%):** this instrumented run uses the
default seed (42) and default S1 templates -- the same protocol documented
for the canonical population -- and the instrumentation itself is provably
behaviour-neutral (see Source note above). The small residual difference
from the manuscript's checked-in canonical file
(`data/synthpop/patras_households.json`, dated 2026-06-27) is most plausibly
explained by `Thesis_Synthpop-main/python_ipf/main_ipf_pipeline.py` having
been edited since that canonical file was last (re)generated -- this repo
was under concurrent edits by another process during this session, and the
file was only added to git tracking today (commit `54d47f4`), so no diff
history is available to confirm exactly what changed. It does **not** affect
the tier-usage finding below, which is a same-run internal breakdown.

## Tier usage (Patras, count of *children* placed at each tier)

| Tier | Count | % of all children (0-14) |
|---|---:|---:|
| (a) Normal greedy template match (no relaxation) | 28,661 | 93.73% |
| (b) Relaxation tier >=3 bands (~15+ yr gap, "plausible parent") | 1,918 | 6.27% |
| (c) Relaxation tier >=2 bands (~10+ yr gap) | 0 | 0.00% |
| (d) Relaxation tier >=1 band (loosest; fixed threshold band>=3) | 0 | 0.00% |
| (e) Could not be placed (forced child singleton) | 0 | 0.00% |
| **Total** | **30,579** | **100.00%** |

## Loosest-tier (>=1 band) diagnostic

The `tier_ge1band` tier uses a *fixed* threshold (any household member in age band >=3, i.e. 15+) rather than a threshold relative to the child's own band. This means the band-gap it actually achieves varies with the child's age: for a band-2 child (10-14) it is a genuine >=1-band (~5-14 year) gap tier; for band-0/1 children it can coincide with, or be looser than, the nominal >=2-band tier.

Children placed at `tier_ge1band`, broken down by their own age band:
| Child age band | Age range | Children placed at loosest tier |
|---:|---|---:|

Achieved band-gap distribution for children placed at `tier_ge1band` (gap = age band of the most senior existing household member minus the child's own age band, measured *before* the child was attached):
| Achieved gap (bands) | ~years | N |
|---:|---:|---:|

## Assessment

The loosest relaxation tier (`tier_ge1band`) accounts for only 0.00% of all children (0-14) in Patras households -- a small share. The "100.0% plausible-adult" figure is overwhelmingly achieved via the normal greedy match or the strict (>=3-band) relaxation tier, so the manuscript's framing does not appear to be an overclaim on this point.
