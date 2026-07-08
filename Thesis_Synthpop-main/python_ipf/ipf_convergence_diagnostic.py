"""IPF convergence trajectory diagnostic for Section 5.3.1.

Runs the global 4D IPF (gender x age x employment x education, Achaia scale)
with verbose=2 to extract per-iteration max deviation.
Also runs the per-location 5D IPF for location 2423701 (Patras).

Run from Thesis_Synthpop-main/:
    python python_ipf/ipf_convergence_diagnostic.py
"""
import numpy as np
import pandas as pd
from ipfn import ipfn
from dataset_loading import (load_age_gender_data, load_work_data,
                             load_work_location_data, load_education_data,
                             load_all_age_gender_data)

CONVERGENCE_RATE = 1e-5
RATE_TOLERANCE   = 1e-5
LOCATION_LEVEL   = 5   # matches dataset_loading.py
PATRAS_ID        = 2423701

age_gender  = load_age_gender_data()
work        = load_work_data()
work_location = load_work_location_data()
education_employment, gender_education_sums = load_education_data()
age_gender_all = load_all_age_gender_data()

# ── Global 4D IPF (Achaia scale) ─────────────────────────────────────────────
seed_4d = np.ones((2, 16, 7, 14), dtype=float)
seed_4d[:, :3, [0, 1, 3, 4], :] = 0   # no working kids
seed_4d[:, :3, :7, :8] = 0             # no kids with degrees

ag_all = [df[df['location_id'] == 24237] for df in age_gender_all]

xijkp = np.ones((2, 16, 7))
xipkl = np.ones((2, 7, 14))
for i in range(2):
    xijkp[i] = work[i]
    xipkl[i] = education_employment[i].T

aggregates = [xijkp, xipkl]
dimensions  = [[0, 1, 2], [0, 2, 3]]

IPF_global = ipfn.ipfn(seed_4d, aggregates, dimensions,
                        convergence_rate=CONVERGENCE_RATE,
                        rate_tolerance=RATE_TOLERANCE,
                        verbose=2)
seed_4d_out, converged_g, conv_df_g = IPF_global.iteration()

print("\n=== Global 4D IPF (Achaia) — convergence trajectory ===")
print(f"Converged: {'YES' if converged_g else 'NO'}  |  Iterations: {len(conv_df_g)}")
print(conv_df_g.to_string())
print(f"\nFinal max deviation: {conv_df_g['conv'].iloc[-1]:.2e}")
print(f"Initial max deviation: {conv_df_g['conv'].iloc[0]:.4f}")

# ── Per-location 5D IPF (Patras) ─────────────────────────────────────────────
print("\n=== Per-location 5D IPF (Patras 2423701) — convergence trajectory ===")

location_ids = age_gender[2][age_gender[2]['level'] == LOCATION_LEVEL]['location_id'].to_numpy().astype(int)
if PATRAS_ID not in location_ids:
    print(f"Location {PATRAS_ID} not found in level-{LOCATION_LEVEL} locations.")
else:
    loc_male   = age_gender[0].loc[age_gender[0]['location_id'] == PATRAS_ID]
    loc_female = age_gender[1].loc[age_gender[1]['location_id'] == PATRAS_ID]
    loc_total  = age_gender[2].loc[age_gender[2]['location_id'] == PATRAS_ID]
    loc_wl = work_location.loc[work_location['location_id'] == PATRAS_ID].iloc[0, 3:]
    loc_wl_dist = (loc_wl / loc_wl.sum()).to_numpy().astype(float)

    xijppp = np.ones((2, 16))
    xijppp[0] = loc_male.iloc[0].iloc[-16:].to_numpy().reshape(16,).astype(int)
    xijppp[1] = loc_female.iloc[0].iloc[-16:].to_numpy().reshape(16,).astype(int)
    xipppp = np.hstack([loc_male['sum'], loc_female['sum']])
    xpjppp = loc_total.iloc[0][4:].to_numpy().astype(int)

    # Build 5D seed exactly as the pipeline does
    seed_5d = np.zeros((2, 16, 7, 14, 6))
    seed_5d[:, 3:16, 0, :, :5] = seed_4d_out[:, 3:16, 0, :, np.newaxis] * loc_wl_dist
    seed_5d[:, :, 1:, :, 5]    = seed_4d_out[:, :, 1:, :]

    aggregates_5 = [xipppp, xpjppp, xijppp]
    dimensions_5  = [[0], [1], [0, 1]]

    IPF_loc = ipfn.ipfn(seed_5d, aggregates_5, dimensions_5,
                         convergence_rate=CONVERGENCE_RATE,
                         rate_tolerance=RATE_TOLERANCE,
                         verbose=2)
    try:
        seed_5d_out, converged_l, conv_df_l = IPF_loc.iteration()
        print(f"Converged: {'YES' if converged_l else 'NO'}  |  Iterations: {len(conv_df_l)}")
        print(conv_df_l.to_string())
        print(f"\nFinal max deviation: {conv_df_l['conv'].iloc[-1]:.2e}")
        print(f"Initial max deviation: {conv_df_l['conv'].iloc[0]:.4f}")
    except Exception as e:
        print(f"5D IPF failed: {e}")

print("\n=== MANUSCRIPT VALUES (Section 5.3.1) ===")
n_global = len(conv_df_g)
init_g   = conv_df_g['conv'].iloc[0]
final_g  = conv_df_g['conv'].iloc[-1]
print(f"Global 4D IPF: {n_global} iterations, initial deviation {init_g:.4f}, final {final_g:.2e}")
