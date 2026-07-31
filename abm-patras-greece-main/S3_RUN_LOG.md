# S3-vs-shuffle robustness experiment run log

Reviewer rebuttal: repeats the published S1 R-vs-U 50-replicate paired SEIR
contrast at SAR=20% on the S3 (WG-reweighted) household population instead of S1,
to test whether the S1 segregation effect is an artifact of S1's under-produced
singleton rate (23.6% vs WG 32.2%) or a robust finding (S3 singleton rate 33.3%).

- **Population**: agents_patras_s3.csv, 215,920 agents, 92,261 households (S3, WG-reweighted templates, PIPELINE_SEED=42, same seed as S1 canonical)
- **Seeds**: 0 to 49 (paired R/U)
- **Initial seeding rule**: 5 random agents set to I, chosen with np.random.default_rng(seed)
- **U definition**: size-matched shuffle (u_seed=999); household membership randomised, work/school/age unchanged -- identical methodology to published S1 Scenario U
- **Total steps**: 180
- **SAR**: 20% (primary manuscript anchor)  beta_family=0.0221
- **SEIR params**: BETA_WORK=0.1, BETA_SCHOOL=0.04, BETA_RANDOM=0.01, BETA_SAME_AGE=0.0005, GAMMA=0.1, SIGMA=0.2
- **Wall-clock**: 2252.6s (45.1s per pair)
