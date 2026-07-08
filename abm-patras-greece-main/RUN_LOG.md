# ABM Experiment Run Log

> **STALE — 2026-07-03**: The run below used the OLD, incorrect `run_experiment.py`
> default `BETA_FAMILY=0.8` (a reproducibility bug — see `reviewers_comments/grave_errors_audit.md`
> GRAVE-3). It does **not** reproduce any manuscript number. `run_experiment.py`'s default has
> since been fixed to `BETA_FAMILY=0.0221` (the primary calibrated value at SAR=20%). This log
> will be regenerated with correct numbers the next time `run_experiment.py` is run to completion
> (50 replicates). The manuscript's Section 7 numbers (Table `tab:abm_design`, R AR=70.85%,
> U AR=73.28%) were produced by the canonical multi-SAR script `full_sweep_50rep.py`, whose output
> (`full_sweep_50rep_summary.csv`, SAR=20% row) is unaffected by this bug and remains authoritative.
> A quick 3-seed / 180-step spot check with the fixed default (2026-07-03) confirmed the corrected
> script now lands in the correct regime: R AR ≈ 0.708–0.709, U AR ≈ 0.732–0.733 (seeds 0–2),
> matching the SAR-20% row (R=70.85%, U=73.28%) rather than the old β=0.8 near-total-attack rate.

- **Mesa version**: not used for scheduler (pure Python active-agent loop)
- **Seeds**: 0 to 49 (paired R/U)
- **Initial seeding rule**: 5 random agents set to I, chosen with np.random.default_rng(seed)
- **U definition**: size-matched shuffle (u_seed=999); household membership randomised, work/school/age unchanged
- **Total steps**: 180
- **Wall-clock**: 1915.9s (38.3s per pair)
- **SEIR params (STALE, this run only)**: BETA_FAMILY=0.8, BETA_WORK=0.1, BETA_SCHOOL=0.04, BETA_RANDOM=0.01, BETA_SAME_AGE=0.0005, GAMMA=0.1, SIGMA=0.2
- **Population**: agents_patras.csv, 215,927 agents, 82,507 households
