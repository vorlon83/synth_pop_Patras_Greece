# Synthetic Population Pipeline for Patras, Greece — Release Bundle

This repository reproduces every number in the manuscript
*"A Municipality-Level Synthetic Population for Epidemic ABMs in Greece"*
(submitted to JASSS 2026).

---

## What is in this bundle

| Path | Contents |
|---|---|
| `Thesis_Synthpop-main/` | Synthesizer: ELSTAT marginals → household population |
| `data/synthpop/patras_households.json` | Canonical Patras population (82,507 hh, 215,927 individuals) |
| `filter_patras.py` | Filter step: Achaia output → Patras-only canonical file |
| `validation/verify_population.py` | Population sanity checks (singleton rate, age distribution, marginal error) |
| `gis/assignment.py` | Spatial assignment: households → OSM residential buildings |
| `pipeline.ipynb` | Full GIS pipeline (Stages 1–10); primary reproduction path |
| `abm-patras-greece-main/` | ABM + sweep scripts |

---

## Requirements

```bash
pip install geopandas shapely pandas numpy scipy matplotlib
```

---

## Step 1: Synthesizer — ELSTAT marginals to household population

**Script:** `Thesis_Synthpop-main/python_ipf/main_ipf_pipeline.py`

The band-14 (age 70–74) synthesis bug — which forced this cohort into 100%
singleton households — is fixed in the current synthesis code. No separate
patch file is needed; `main_ipf_pipeline.py` produces the correct distribution
(band-14 solo rate: 13.5%). Seed used for the canonical run:

**Run:**

```bash
cd Thesis_Synthpop-main/python_ipf
python main_ipf_pipeline.py
```

**Output:** `Thesis_Synthpop-main/python_ipf/ipf_results/households.json`
(full Achaia synthesis: 119,070 HH / 306,021 individuals).
Copy to `data/synthpop/households.json` before running `pipeline.ipynb`.

**IPF convergence** (reproduced from manuscript Table S1):
- Iteration 1: global marginal error 23.95%
- Iteration 5: global marginal error 2.71% (converged)
- Patras 5D sub-IPF: 2 iterations to convergence

---

## Step 2: Filter to Patras municipality

**Script:** `filter_patras.py`

Selects households assigned to Patras municipality (location code 2423701–05).
Applies singleton-rate and age-distribution validation gates before writing
the accepted file.

```bash
python filter_patras.py
```

**Output:** `data/synthpop/patras_households.json`

**Accepted population statistics (canonical, seed=42):**
- Households: 82,507
- Individuals: 215,927
- Mean household size: 2.617
- Band-14 solo rate: 13.5% (was 100% in the buggy file)
- SHA-256: `d47d9df208c65300f7b796ec5c0fec70f05e77ee88476beccc79ea00053f1927`

---

## Step 3: Population validation

**Script:** `validation/verify_population.py`

Checks marginal accuracy, singleton rate by age band, and household size
distribution against ELSTAT 2021 Patras targets.

```bash
python validation/verify_population.py data/synthpop/patras_households.json
```

Key output: age-structure table comparing synthetic vs ELSTAT (max deviation
≤ 0.01 pp across five age groups; see manuscript Table 3).

---

## Step 4: Build agent CSV for ABM

**Script:** `abm-patras-greece-main/build_agents.py`

Converts `patras_households.json` to the agent CSV used by the ABM.

**Seed:**

```python
rng = np.random.default_rng(42)   # integer-age assignment within 5-year bands
```

**Run:**

```bash
cd abm-patras-greece-main
python build_agents.py
```

**Output:** `agents_patras.csv` (215,927 rows)

**Column schema:** Family_ID, Gender, Age (integer, randomised within 5-year
band), Work_ID (−1 if non-employed), School_ID (−1 if not school-attending),
Infection_Status.

Age bands mapped to uniform integer draws in [lo, hi]:

| Band | Range | Integer ages drawn |
|---|---|---|
| 0 | 0–4 | 0–4 |
| 1 | 5–9 | 5–9 |
| … | … | … |
| 14 | 70–74 | 70–74 |
| 15 | 75+ | 75–84 |

---

## Step 5: GIS spatial assignment

**Script:** `gis/assignment.py`

Assigns households to residential OSM building polygons,
district-by-district.

**Prerequisites:**
- `data/greece-260611-free.shp/` (Geofabrik Greece extract, June 2026)
- `data/SCHOOLS/patras_schools_shifted.shp`
- `data/PATRAS_GIS_DATA/GEITONIES_PATRAS/` (55 Patras district polygons)

**No centroid fallback path.** Households in peripheral zones without a
matched building polygon remain unplaced.

```bash
python gis/assignment.py
```

**Results (canonical run, patras_households.json):**
Results pending end-to-end `pipeline.ipynb` run on the fixed canonical file.
Previous results (from old buggy 84,359-HH file, for reference):
- Assigned: 182,179 / 215,927 individuals (84.4%)
- Unplaced (peripheral): 33,748 (15.6%)
- District fill rate: 100% by construction (every eligible footprint is filled — not an informative metric; the manuscript appendix table instead reports the per-district signed allocation error Δ% and households/building)
- Per-district allocation error Δ% = (assigned − pop2021)/pop2021: median |Δ|=0.6%, 43/55 districts within ±10%; districts 13 and 22 over-allocated (non-residential footprint misclassification)
- Households per occupied building: mean 2.17, median 2.0, max 5 (n=32,734)

---

## Step 6: ABM — 50-replicate SAR sensitivity sweep

### Parameter corrections applied

**Correction 1 — household transmission rate (β_family):**

The original model used `BETA_FAMILY = 0.8`, which implies a household
secondary attack rate (SAR) ≈ 100% — epidemiologically indefensible.

The corrected value is derived from:

```
β_family = 1 − (1 − SAR)^γ
```

where `γ = GAMMA = 0.1` day⁻¹ (mean infectious period = 1/γ = 10 days).

Literature anchor: Madewell et al. (2020), JAMA Network Open 3(12):e2031756.
Pooled COVID-19 household SAR = 18.8% (95% CI 15.4–22.2%).

SAR targets and derived β_family values:

| SAR | β_family |
|---|---|
| 15% | 0.0161 |
| 20% | 0.0221  ← primary (Madewell anchor) |
| 25% | 0.0284 |
| 30% | 0.0347 |

**Correction 2 — same-age contact normalisation:**

The original `_do_step()` swept the entire integer-age cohort (~2,150 agents
per integer age), making force-of-infection proportional to cohort size.
The corrected implementation samples exactly `round(c_pd)` peers uniformly
at random (POLYMOD contacts_per_day, Mossong et al. 2008), giving
≤ 18 contacts per step regardless of cohort size.

### Seeds

```python
SEEDS_ABM       = range(50)          # 0 to 49 (paired R and U)
U_SHUFFLE_SEED  = 999                 # household membership randomisation for U
AGE_MAP_SEED    = 42                  # integer-age draws in build_agents.py
```

### Run the sweep

```bash
cd abm-patras-greece-main
python full_sweep_50rep.py 2>&1 | tee full_sweep_50rep.log
```

Runtime: **~2 hours** on a single CPU core (4 SAR × 50 seeds × 2 scenarios) with the performance fix applied. The same-age contact layer now uses O(cpd ≈ 18) rejection sampling instead of the previous O(cohort ≈ 2,700) list comprehension, giving a ~9× speedup. The original unpatched code took ~12 hours.

### Outputs

| File | Contents |
|---|---|
| `full_sweep_50rep_summary.csv` | 4-row summary: means, SDs, Wilcoxon p |
| `full_sweep_50rep_curves.csv` | Mean daily incidence curves per SAR and scenario |
| `full_sweep_50rep_perrun.csv` | Per-seed data (400 rows) |

---

## Step 7: Per-scenario diagnostics

```bash
cd abm-patras-greece-main
python diagnostics/diagnostic_status.py
```

Reports per-employment-status attack rates (employed / student / inactive)
for R and U populations. These are also produced during the sweep
(`full_sweep_50rep.py`) but `diagnostics/diagnostic_status.py` provides a
standalone single-SAR check.

---

## Reproducing Table 4 (ABM sensitivity sweep)

Run `full_sweep_50rep.py` as above. The four-row sensitivity table in the
manuscript (SAR 15/20/25/30%) is populated from
`full_sweep_50rep_summary.csv`. Columns reported:

- SAR (%), β_family, R AR (%), U AR (%), ΔAR (pp)
- Inactive ΔAR (pp), R peak incidence, U peak incidence
- R day of peak, U day of peak, Wilcoxon p (paired, n=50)

The SAR 20% row (β_family = 0.0221) is the primary comparison row,
anchored to the Madewell et al. (2020) pooled household SAR estimate.

---

## Data provenance

| Dataset | Source | Version / date |
|---|---|---|
| ELSTAT household-size marginals (Patras, Achaia) | ELSTAT 2021 Census | Downloaded 2024 |
| ISTAT household templates | ISTAT 2016 microcensus (24,753 hh) | Downloaded 2024 |
| OSM building + landuse polygons | Geofabrik Greece extract | `greece-260611-free.shp` (June 2026) |
| Patras district polygons | Municipal GIS layer | `GEITONIES_PATRAS` |
| POLYMOD contact rates | Mossong et al. (2008) PLOS Med 5(3):e74 | contacts_per_day by age group |
| Household SAR anchor | Madewell et al. (2020) JAMA Netw Open 3(12):e2031756 | SAR = 18.8% |

---

## Checklist for independent reproduction

- [ ] Install dependencies (`pip install geopandas shapely pandas numpy scipy`)
- [ ] Download Greece OSM extract → `data/greece-260611-free.shp/`
- [ ] Run `main_ipf_pipeline.py` → `households.json`
- [ ] Run `filter_patras.py` → `patras_households.json`
  - Gate (Stage 2 of `pipeline.ipynb`): band-14 solo rate < 99% — passes at 13.5%
- [ ] Run `validation/verify_population.py data/synthpop/patras_households.json` → confirm max marginal error ≤ 0.05 pp
- [ ] Run `pipeline.ipynb` end-to-end → `initial_state.geojson`, `schools.geojson`
  - Or run `python gis/assignment.py` standalone → `gis_assignment_results.txt`
  - GIS numbers pending fresh run on canonical (82,507-HH) file
- [ ] Run `build_agents.py` → `agents_patras.csv` (215,927 rows)
- [x] Run `full_sweep_50rep.py` → `full_sweep_50rep_summary.csv`
  - Run 4 completed 2026-06-22 (PID 105712, 103.6 min, performance-fixed) ← canonical
  - SAR=20% anchor: R AR=70.85% (SD 0.09), U AR=73.28% (SD 0.07), ΔAR=+2.43pp, inactive gap=+6.02pp, peak delay=9.5d, peak higher=17.3%
  - SAR=15%: inactive gap 4.62pp; SAR=25%: 7.23pp; SAR=30%: 8.34pp (monotone)
  - n=50 everywhere (no stochastic-extinction replicates)
