# abm-patras-greece

SEIR agent-based model for simulating infectious disease dynamics in Patras,
Greece, using the synthetic household population from the parent pipeline.

---

## Scripts

| Script | Purpose |
|---|---|
| `build_agents.py` | Convert `patras_households.json` → `agents_patras.csv` |
| `run_experiment.py` | 50-replicate R vs. U comparison (single SAR level, S1 households; `BETA_FAMILY` default now 0.0221, the SAR=20% primary value — was a stale 0.8 until 2026-07-03, see `RUN_LOG.md`) |
| `full_sweep_50rep.py` | SAR sensitivity sweep: 15/20/25/30%, 50 seeds each (S1 households; canonical script for the manuscript's Section 7 sweep) |
| `build_agents_s3.py` | Convert the S3 (WG-reweighted) household population → `agents_patras_s3.csv` (added 2026-07-03) |
| `run_experiment_S3.py` | R vs. U comparison on S3 households instead of S1, same design as `run_experiment.py`; robustness check for the manuscript's `s3-vs-shuffle-robustness` subsection. Defaults to `N_SEEDS=50`; only a 5-seed smoke test (`s3_vs_shuffle_smoketest_5rep*.csv`) has been run so far — see `S3_SMOKETEST_RUN_LOG.md` |
| `beta_family_sweep.py` | β_family sensitivity scan |
| `diagnostics/diagnostic_saturation.py` | Isolate which contact layers drive saturation |
| `diagnostics/diagnostic_status.py` | Per-employment-status attack rates |
| `diagnostics/quick_corrected_diag.py` | Fast 5-seed sanity check |

## Usage

```bash
# Step 1 — build agent CSV (run once per population)
python build_agents.py

# Step 2 — full SAR sweep (50 replicates × 4 SAR levels, ~90 min)
python full_sweep_50rep.py 2>&1 | tee full_sweep_50rep.log
```

## Key parameters (do not change without updating manuscript)

| Parameter | Value | Meaning |
|---|---|---|
| `BETA_FAMILY` | calibrated per SAR | household transmission probability |
| `BETA_WORK` | 0.1 | per-contact workplace transmission |
| `BETA_SCHOOL` | 0.04 | per-contact school transmission |
| `BETA_RANDOM` | 0.01 | per-contact random transmission |
| `BETA_SAME_AGE` | 0.0005 | per-contact same-age transmission |
| `GAMMA` | 0.1 | recovery rate (mean infectious period = 10 days) |
| `SIGMA` | 0.2 | incubation rate (mean latent period = 5 days) |
| `TOTAL_STEPS` | 180 | simulation duration (days) |
| `INITIAL_INFECTED` | 5 | initial seed size |

## Outputs

| File | Contents |
|---|---|
| `agents_patras.csv` | 215,927-row agent table (Family_ID, Gender, Age, Work_ID, School_ID) |
| `full_sweep_50rep_summary.csv` | 4-row sweep summary (means, SDs, Wilcoxon p) |
| `full_sweep_50rep_curves.csv` | Mean daily incidence curves per SAR × scenario |
| `full_sweep_50rep_perrun.csv` | Per-seed data (400 rows) |
