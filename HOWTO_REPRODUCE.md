# How to Reproduce the Experiment

End-to-end instructions for regenerating every number, figure, and table in the manuscript from scratch. Follow the steps in order.

All commands are run from the project root (`GIS-paper-main/`) unless stated otherwise.

---

## Prerequisites

```bash
pip install geopandas shapely pandas numpy scipy matplotlib jupyter
```

You also need:
- `data/greece-260611-free.shp/` — Geofabrik Greece OSM extract (June 2026)
- `data/SCHOOLS/patras_schools_shifted.shp` — school locations
- `data/PATRAS_GIS_DATA/GEITONIES_PATRAS/` — 55 Patras district polygons
- `data/synthpop/ELSTAT_*.csv` — ELSTAT 2021 Census marginals

---

## Step 1 — Synthesize the Achaia household population (IPF)

**Script:** `Thesis_Synthpop-main/python_ipf/main_ipf_pipeline.py`

```bash
cd Thesis_Synthpop-main/python_ipf
python main_ipf_pipeline.py
```

**Runtime:** ~5 minutes.

**Output:** `Thesis_Synthpop-main/python_ipf/ipf_results/households.json`

Copy it to the data folder before the next step:

```bash
cp Thesis_Synthpop-main/python_ipf/ipf_results/households.json data/synthpop/households.json
cd ../..
```

**Expected:** 119,070 households / 306,021 individuals (full Achaia).

IPF convergence milestones (Table S1 in manuscript):
- Iteration 1: global marginal error 23.95%
- Iteration 5: global marginal error 2.71% (converged)

---

## Step 2 — Filter to Patras municipality

**Script:** `filter_patras.py`

```bash
python filter_patras.py
```

**Runtime:** < 1 minute.

**Output:** `data/synthpop/patras_households.json`

**Expected:** 82,507 households / 215,927 individuals.

SHA-256 of canonical file (post-education re-weighting):
```
48e4053c0ecd6daf5908c0e2eb5a764402d4b247c034e0157e54491551ded9ab
```

> **Do not use** `patras_households_new.json` — pre-band-14-fix file (84,359 HH).
> **Do not use** `patras_households_pre_edu_reweight.json` — pre-education-reweight backup.
> Both exist in `data/synthpop/` for reference only.

---

## Step 2b — Re-weight education to Patras B02 marginals

**Script:** `reweight_education.py`

```bash
python reweight_education.py
```

**Runtime:** < 1 minute.

**Output:** `data/synthpop/patras_households.json` (replaces in-place; pre-reweight backed up as `patras_households_pre_edu_reweight.json`)

**What it does:** For each ELSTAT age band (0–14, 15–29, 30–44, 45–59, 60–74, 75+), rescales education attributes to match B02 Patras municipality marginals exactly using largest-remainder rounding (seed 42). Education is not used in household matching or ABM contact layers, so downstream results are unchanged.

**Expected after re-weighting:**
- University+: 22.93% (was 19.6%)
- High school: 32.94% (was ~26%)
- Max residual vs B02: < 0.1 pp

---

## Step 3 — Validate the population

**Script:** `validation/verify_population.py`

```bash
python validation/verify_population.py data/synthpop/patras_households.json
```

**Runtime:** < 1 minute.

**Expected outputs** (Table 3 in manuscript):
- Max age-group marginal error ≤ 0.01 pp across five age groups
- Band-14 (age 70–74) solo rate: 13.5% (was 100% in the buggy pre-fix file)
- Mean household size: 2.617

If any gate fails, the population file is not canonical — go back to Step 1.

---

## Step 4 — Run the GIS pipeline

**Notebook:** `pipeline.ipynb` (Stages 1–10, run top-to-bottom)

```bash
jupyter notebook pipeline.ipynb
```

Run all cells in order. The notebook:
- Loads `data/synthpop/patras_households.json`
- Matches households to OSM residential building polygons, district by district
- Attaches school IDs to school-age members

**Runtime:** 15–30 minutes depending on hardware.

**Outputs:**
- `initial_state.geojson` — households with building coordinates
- `schools.geojson` — school catchment assignments
- `gis_district_statistics.csv` — per-district fill summary

**Expected GIS results** (Section 6.3):
- Assigned: 84.4% of individuals (182,179)
- Unplaced (peripheral zones, no matched building): 15.6% (33,748)
- District fill rate: 100% by construction (every eligible footprint filled — not an informative metric; the manuscript reports the per-district signed allocation error Δ% instead)
- Per-district allocation error Δ%: median |Δ|=0.6%, 43/55 within ±10%; 2 districts over-allocated (non-residential footprint misclassification)
- Households per occupied building: mean 2.17, median 2.0, max 5 (n = 32,734)
- Note: `gis/assignment.py` is now seeded (`PIPELINE_SEED`, default 42) for reproducible household-to-building placement

Alternatively, run the assignment standalone (skips school attachment):

```bash
python gis/assignment.py
```

---

## Step 5 — Build the agent CSV

**Script:** `abm-patras-greece-main/build_agents.py`

```bash
cd abm-patras-greece-main
python build_agents.py
```

**Runtime:** ~1 minute.

**Output:** `abm-patras-greece-main/agents_patras.csv` (215,927 rows)

**Expected columns:** `Family_ID`, `Gender`, `Age`, `Work_ID` (−1 if not employed), `School_ID` (−1 if not school-age), `Infection_Status`.

Seeds used:
```python
rng = np.random.default_rng(42)   # integer-age assignment within 5-year bands
```

---

## Step 6 — Run the ABM sensitivity sweep

**Script:** `abm-patras-greece-main/full_sweep_50rep.py`

```bash
python full_sweep_50rep.py 2>&1 | tee full_sweep_50rep.log
```

**Run from inside `abm-patras-greece-main/`:**

```bash
cd abm-patras-greece-main
python full_sweep_50rep.py 2>&1 | tee full_sweep_50rep.log
cd ..
```

**Runtime:** ~2 hours on a single CPU core (4 SAR levels × 50 seeds × 2 scenarios = 400 paired runs, ~31 s/pair with the performance fix applied).

**Sweep design:**

| SAR | β_family | Purpose |
|-----|----------|---------|
| 15% | 0.0161 | Lower bound |
| 20% | 0.0221 | **Primary anchor** (Madewell et al. 2020) |
| 25% | 0.0284 | Upper sensitivity |
| 30% | 0.0350 | Upper bound |

β_family formula: `β = 1 − (1 − SAR)^γ` where γ = GAMMA = 0.1

Seeds: 0–49 paired (R and U); U household-shuffle seed = 999.

**Outputs** (written to `abm-patras-greece-main/`):

| File | Contents |
|------|---------|
| `full_sweep_50rep_summary.csv` | 4-row summary: means, SDs, Wilcoxon p |
| `full_sweep_50rep_perrun.csv` | Per-seed data (400 rows) |
| `full_sweep_50rep_curves.csv` | Mean daily incidence curves per SAR and scenario |

**Expected results — canonical Run 4 (n = 50 everywhere, no stochastic extinctions):**

| SAR | β | R AR% (SD) | U AR% (SD) | ΔAR (pp) | Inactive ΔAR (pp) | R peak (SD) | U peak (SD) | R day (SD) | U day (SD) | Wilcoxon p |
|-----|---|-----------|-----------|----------|-----------------|------------|------------|-----------|-----------|----------|
| 15% | 0.0161 | 69.20 (0.07) | 71.09 (0.07) | +1.89 | +4.62 | 4432 (97) | 4973 (86) | 87.7 (8.1) | 78.7 (4.9) | < 10⁻⁴ |
| **20%** | **0.0221** | **70.85 (0.09)** | **73.28 (0.07)** | **+2.43** | **+6.02** | **4814 (85)** | **5647 (90)** | **81.1 (7.5)** | **71.6 (4.5)** | **< 10⁻⁴** |
| 25% | 0.0284 | 72.35 (0.08) | 75.26 (0.09) | +2.91 | +7.23 | 5183 (108) | 6246 (102) | 77.1 (7.0) | 66.9 (5.1) | < 10⁻⁴ |
| 30% | 0.0350 | 73.69 (0.07) | 77.04 (0.06) | +3.35 | +8.34 | 5475 (93) | 6765 (85) | 74.1 (7.3) | 62.4 (4.3) | < 10⁻⁴ |

Key SAR = 20% interpretation: Scenario U (shuffled households) peaks **17.3% higher** and **9.5 days earlier** than Scenario R (structured households). The inactive/elderly subpopulation attack-rate gap is **6.02 pp**.

---

## Step 7 — Compute conditional statistics

**Script:** `validation/abm_conditional_stats.py`

```bash
python validation/abm_conditional_stats.py
```

Reads `abm-patras-greece-main/full_sweep_50rep_perrun.csv`, excludes any replicate with attack rate < 1% (stochastic extinction), runs paired Wilcoxon tests, and prints per-SAR conditional statistics.

With Run 4 data, no replicates are excluded (n = 50 at all SAR levels).

---

## Step 8 — Regenerate figures

### Figures from sweep CSVs (fast, < 1 minute)

```bash
python figures/generate_abm_figures.py
```

Generates:
- `Synthetic_Population_manuscript/img/fig_epidemic_curves.png`
- `Synthetic_Population_manuscript/img/fig_peak_comparison.png`
- `Synthetic_Population_manuscript/img/fig_inactive_gap.png`
- `Synthetic_Population_manuscript/img/fig_ar_violin.png`

Also archives a timestamped copy of all three sweep CSVs to `data/abm_results/`.

### Fan curves figure (slow, ~25 minutes — re-runs 100 ABM simulations)

```bash
python figures/generate_fan_curves.py
```

Runs 50 paired seeds at SAR = 20% independently to capture full daily trajectories (the sweep CSVs store only means). Generates:
- `Synthetic_Population_manuscript/img/fig_fan_curves.png`
- `data/abm_results/fan_curves_perrun_SAR20.csv`

You can run this in the background while doing other things:

```bash
python figures/generate_fan_curves.py > /tmp/fan_curves.log 2>&1 &
```

---

## Step 9 — Compile the manuscript PDF

```bash
cd Synthetic_Population_manuscript
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex   # second pass for cross-references
```

**Expected:** 49-page PDF, no errors.

---

## Checklist

| Step | Script / command | Expected output | Time |
|------|-----------------|----------------|------|
| 1 — IPF synthesis | `Thesis_Synthpop-main/python_ipf/main_ipf_pipeline.py` | 119,070 HH / 306,021 ind. | ~5 min |
| 2 — Filter Patras | `filter_patras.py` | 82,507 HH / 215,927 ind. | < 1 min |
| 2b — Education reweight | `reweight_education.py` | Max B02 residual < 0.1 pp | < 1 min |
| 3 — Validate | `validation/verify_population.py` | Max error ≤ 0.01 pp | < 1 min |
| 4 — GIS pipeline | `pipeline.ipynb` | 84.4% placed, 100% district fill | 15–30 min |
| 5 — Build agents | `abm-patras-greece-main/build_agents.py` | `agents_patras.csv` 215,927 rows | ~1 min |
| 6 — ABM sweep | `abm-patras-greece-main/full_sweep_50rep.py` | 3 sweep CSVs; n=50 everywhere | ~2 hours |
| 7 — Conditional stats | `validation/abm_conditional_stats.py` | Wilcoxon p < 10⁻⁴ at all SAR levels | < 1 min |
| 8a — Main figures | `figures/generate_abm_figures.py` | 4 PNG figures | < 1 min |
| 8b — Fan curves | `figures/generate_fan_curves.py` | `fig_fan_curves.png` | ~25 min |
| 9 — PDF | `pdflatex main.tex` (×2) | `main.pdf` 49 pages | ~1 min |

---

## Notes

- **Do not skip Step 2 validation gates.** If `verify_population.py` fails, the synthesis output is not canonical and the ABM results will not match the manuscript.
- **Steps 6 and 8b are the two long-running steps.** Plan ~2.5 hours of uninterrupted compute. Both can be left running overnight.
- **The sweep uses paired seeds.** Each seed (0–49) runs both Scenario R and Scenario U from an identical initial state. Changing `U_SHUFFLE_SEED` (currently 999) breaks pairing and invalidates comparison statistics.
- **β_family is recomputed per SAR level** inside `full_sweep_50rep.py` using the formula above. Do not change `BETA_FAMILY` in `run_experiment.py` directly for the sweep — that constant is used only for standalone single-SAR runs.
- **GIS numbers in the manuscript** (84.4% placed, 32,734 occupied buildings) come from a previous run on the canonical 82,507-HH file. If your GIS run produces different numbers, check that `pipeline.ipynb` is reading `patras_households.json` (82,507 HH), not the old `patras_households_new.json` (84,359 HH).
