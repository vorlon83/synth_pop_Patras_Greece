"""
IPF + household synthesis pipeline for Achaia, Greece.

Pipeline stages run by this script:
  1. Build 4-D seed (gender × age × employment × education) with structural zeros
     for logically impossible combinations (e.g. working children, educated toddlers).
  2. Run IPF against ELSTAT 2021 Achaia regional marginals until convergence
     (rate 1e-5).  Output: a calibrated joint distribution over 4 attributes.
  3. Per municipality (level-5 location): extend to 5-D by adding employment_location,
     run a second location-specific IPF, then stochastically round to integer counts.
  4. Assemble synthetic individuals into households using ISTAT 2016 composition
     templates (household_compositions.json).  Unplaced children are attached to the
     smallest adult household with a plausible parent age; remaining singletons
     (adults/elderly only) receive solo households.

Output: python_ipf/ipf_results/households.json
  — list of household dicts keyed by household_id, location_id, members.
  — Downstream: filter_patras.py extracts Patras (location_id 2423701).

Run from the Thesis_Synthpop-main/ directory:
  python python_ipf/main_ipf_pipeline.py

Set PIPELINE_SEED env var to override seed 42 for stability runs.
"""
import bisect
import numpy as np
import pandas as pd
from ipfn import ipfn
import os
import json
import random
import matplotlib.pyplot as plt
from itertools import product
from collections import defaultdict
from visual_util import *
from dataset_loading import *
from scipy.stats import chisquare

CONVERGENCE_RATE = 1e-5
RATE_TOLERANCE = 1e-5
SHOW_METRICS = 1
SHOW_VISUAL_METRICS = 0
VERBOSE = 1
FILE_OUTPUT = 1
OUTPUT_DIR = 'python_ipf/ipf_results'
EXPERIMENTAL_HOUSEHOLD = 1

# Global seed — controls stochastic rounding (np.random.rand) and household
# assembly (random.random / random.choice). Record this value in the Data
# Availability statement so the released population is reproducible from a
# clean checkout.
# PIPELINE_SEED env var overrides SEED for multi-run stability tests; default 42.
SEED = int(os.environ.get('PIPELINE_SEED', 42))
np.random.seed(SEED)
random.seed(SEED)

np.set_printoptions(suppress=True)
# https://pypi.org/project/ipfn/

# !!!: [] for converting (,x) to (1,x)
# !!!: iloc = row by position
# !!!: loc = row by label

def get_invalid_people(df):
    '''
    Returns a dataframe of people with invalid combinations

    The combinations were searched manually
    '''
    invalid_people = df[
        (
            # working kids
            (df['age_group'] < 3) & (df['employment'] < 2)
        )
        |
        (
            # kids with higher education
            (df['age_group'] < 3) & (df['education'] < 8)
        )
        |
        (
            # unemployed people without correct employment location value
            (df['employment'] > 0) & (df['employment_location'] != 5)
        )
        # |
        # (
        #     (df[''])
        # )

    ]
    return invalid_people


def stochastic_round(array):
    """Stochastic rounding (Barthelemy & Toint 2013): round probabilistically
    so the expected value of the result equals the IPF cell value, preserving
    marginal totals on average across the population."""
    floor = np.floor(array)
    prob = array - floor
    result = int(floor + (np.random.rand(*array.shape) < prob).astype(int))
    if VERBOSE == 1:
        if result < 0:
            print("Negative value computed!")
    return max(result, 0) # handle negative values

def create_households(synthetic_population_df):
    """Create households based on household compositions from JSON file."""
    print("Starting household creation process...")

    # ── Child-adult relaxation-tier instrumentation (observation only; does not
    # consume randomness or alter matching behaviour). Enabled by setting
    # TIER_STATS_OUTPUT to a JSON output path; see validation/relaxation_tier_report.py.
    _tier_stats_output = os.environ.get('TIER_STATS_OUTPUT')
    tier_stats = defaultdict(lambda: defaultdict(int))  # {location_id: {tier_name: count}}
    tier_gap_records = []  # [(location_id, child_age_group, tier_name, actual_band_gap)]

    # Load household compositions (TEMPLATE_FILE env var overrides for sensitivity runs)
    print("Loading household compositions...")
    _template_file = os.environ.get(
        'TEMPLATE_FILE', 'it_microdata_preprocess/household_compositions.json')
    with open(_template_file, 'r') as f:
        household_compositions = json.load(f)
    print(f"Loaded {len(household_compositions)} household compositions from {_template_file}")
    
    # Initialize household tracking
    print("Initializing household tracking...")
    synthetic_population_df['household_id'] = -1
    households = []
    household_id = 0
    
    # Process each location
    total_locations = len(synthetic_population_df['location_id'].unique())
    print(f"\nProcessing {total_locations} locations...")
    
    for loc_idx, location_id in enumerate(synthetic_population_df['location_id'].unique(), 1):
        print(f"\nProcessing location {loc_idx}/{total_locations} (ID: {location_id})")
        
        # Get location population and initialize tracking
        location_mask = synthetic_population_df['location_id'] == location_id
        location_pop = synthetic_population_df[location_mask].copy()
        initial_pop_size = len(location_pop)
        print(f"Location population size: {initial_pop_size}")
        
        # Precompute pools of available indices for each (gender, age_group).
        # Stored as sorted lists so random.choice is O(1) and bisect removal is
        # O(log n) — avoids the O(n log n) sorted() call on every member pick.
        available_indices = {}
        for gender in location_pop['gender'].unique():
            for age_group in location_pop['age_group'].unique():
                available_indices[(gender, age_group)] = sorted(
                    location_pop[
                        (location_pop['gender'] == gender) &
                        (location_pop['age_group'] == age_group)
                    ].index.tolist()
                )
        assigned_indices = set()
        
        # Create households from compositions
        attempts = 0
        max_attempts = initial_pop_size * 2  # Prevent infinite loops

        # Initialize available compositions for this location
        # Exclude single-member child-band templates (they create demographically
        # impossible child-singleton households).
        _CHILD_BANDS_FILTER = {0, 1, 2}
        available_compositions = [
            c for c in household_compositions
            if not (len(c['household']) == 1 and c['household'][0][1] in _CHILD_BANDS_FILTER)
        ]
        successful_attempts = 0  # Track successful household creations in the last 100 attempts
        recompute_probabilities = True
        composition_probabilities = []
        location_hh_start = len(households)  # index into households list where this location's HHs begin

        while len(assigned_indices) < initial_pop_size and attempts < max_attempts and available_compositions:
            attempts += 1
            if attempts % 100 == 0:
                remaining = initial_pop_size - len(assigned_indices)
                print(f"[{attempts}]: {remaining} people unassigned")
                print(f"Available household compositions: {len(available_compositions)}")
                print(f"{successful_attempts} households in last 100 attempts")
                print('\n')
                successful_attempts = 0  # Reset counter for next 100 attempts
            
            # Update probabilities for available compositions only if needed
            if recompute_probabilities:
                total_prob = sum(comp['percentage'] for comp in available_compositions)
                cumulative_prob = 0
                composition_probabilities = []
                for comp in available_compositions:
                    cumulative_prob += comp['percentage'] / total_prob
                    comp['cumulative_prob'] = cumulative_prob
                    composition_probabilities.append(comp['cumulative_prob'])
                recompute_probabilities = False
            
            # Roll dice to select household composition
            roll = random.random()
            for idx, comp in enumerate(available_compositions):
                if comp['cumulative_prob'] >= roll:
                    selected_comp = comp
                    break
            
            # Try to select one random person for each member type from available pools.
            # within_attempt prevents the same person filling two slots in one household
            # (possible when a template has two slots with identical gender+age_group).
            member_indices = []
            member_keys = []
            can_assign = True
            within_attempt = set()
            for gender, age_group in selected_comp['household']:
                pool = available_indices.get((gender, age_group), [])
                # pool already contains only unassigned members; exclude within-attempt picks
                available = [i for i in pool if i not in within_attempt]
                if not available:
                    can_assign = False
                    break
                chosen = random.choice(available)
                member_indices.append(chosen)
                member_keys.append((gender, age_group))
                within_attempt.add(chosen)

            if can_assign:
                # Remove each chosen member from their pool via bisect (O(log n))
                for (g, ag), idx in zip(member_keys, member_indices):
                    pool = available_indices[(g, ag)]
                    pos = bisect.bisect_left(pool, idx)
                    del pool[pos]
                assigned_indices.update(member_indices)
                # Create household
                selected_members = location_pop.loc[member_indices]
                household = {
                    'household_id': str(household_id),
                    'location_id': str(location_id),
                    'members': [{
                        # Convert to int to avoid nonserializable int32 for JSON
                        'gender': int(row['gender']),
                        'age_group': int(row['age_group']),
                        'employment': int(row['employment']),
                        'employment_location': int(row['employment_location']),
                        'education': int(row['education'])
                    } for _, row in selected_members.iterrows()]
                }
                households.append(household)
                synthetic_population_df.loc[member_indices, 'household_id'] = household_id
                household_id += 1
                successful_attempts += 1  # Increment successful attempt counter
                # Instrumentation: count children (0-14) placed via the normal
                # greedy template match, i.e. no child-adult relaxation needed.
                if _tier_stats_output:
                    for (g, ag) in member_keys:
                        if ag in _CHILD_BANDS_FILTER:
                            tier_stats[location_id]['greedy_no_relaxation'] += 1
            else:
                # Remove this composition from available options
                available_compositions = [comp for comp in available_compositions 
                                       if comp['household'] != selected_comp['household']]
                recompute_probabilities = True
                if not available_compositions:
                    print("No more possible household compositions available")
                    break
        
        # Attach unassigned children (0-14) to an existing adult household rather than
        # creating demographically impossible child singletons. Adults/elderly that remain
        # unassigned receive singleton households as before.
        _CHILD_BANDS = {0, 1, 2}
        _SIZE_CAP = 10  # max household size AFTER attaching one child; generous to avoid child singletons
        unassigned = list(set(location_pop.index) - assigned_indices)
        children_to_attach = [idx for idx in unassigned
                              if int(location_pop.loc[idx]['age_group']) in _CHILD_BANDS]
        adult_unassigned = [idx for idx in unassigned
                            if int(location_pop.loc[idx]['age_group']) not in _CHILD_BANDS]

        local_households = households[location_hh_start:]  # only this location's HHs
        children_forced_singleton = []
        for idx in children_to_attach:
            child_ag = int(location_pop.loc[idx]['age_group'])
            member_dict = {
                'gender': int(location_pop.loc[idx]['gender']),
                'age_group': int(location_pop.loc[idx]['age_group']),
                'employment': int(location_pop.loc[idx]['employment']),
                'employment_location': int(location_pop.loc[idx]['employment_location']),
                'education': int(location_pop.loc[idx]['education'])
            }
            # Tiered parent-age relaxation: prefer strict (band+3 ~15yr older),
            # fall back to band+2 then any adult (band 3+) before creating singleton.
            placed = False
            _tier_names = ['tier_ge3band', 'tier_ge2band', 'tier_ge1band']
            for _tier_i, min_pb in enumerate([child_ag + 3, child_ag + 2, 3]):
                candidates = [
                    h for h in local_households
                    if len(h['members']) < _SIZE_CAP
                    and any(m['age_group'] >= min_pb for m in h['members'])
                ]
                if candidates:
                    min_size = min(len(h['members']) for h in candidates)
                    smallest = [h for h in candidates if len(h['members']) == min_size]
                    target = random.choice(smallest)
                    # Instrumentation: record which relaxation tier placed this
                    # child, plus the actual achieved band gap to the most
                    # "adult" (highest age-band) member already in the target
                    # household -- captured BEFORE the child is appended.
                    if _tier_stats_output:
                        tier_stats[location_id][_tier_names[_tier_i]] += 1
                        _max_band_present = max(m['age_group'] for m in target['members'])
                        tier_gap_records.append(
                            (str(location_id), child_ag, _tier_names[_tier_i],
                             _max_band_present - child_ag)
                        )
                    target['members'].append(member_dict)
                    synthetic_population_df.loc[idx, 'household_id'] = int(target['household_id'])
                    placed = True
                    break
            if not placed:
                children_forced_singleton.append(idx)
                if _tier_stats_output:
                    tier_stats[location_id]['forced_singleton'] += 1

        if children_forced_singleton:
            print(f"WARNING: {len(children_forced_singleton)} children could not be placed in a plausible-parent household")

        remaining_singletons = adult_unassigned + children_forced_singleton
        if remaining_singletons:
            print(f"Creating {len(remaining_singletons)} single-person households for remaining unassigned people")
            single_households = [{
                'household_id': str(household_id + i),
                'location_id': str(location_id),
                'members': [{
                    'gender': int(location_pop.loc[idx]['gender']),
                    'age_group': int(location_pop.loc[idx]['age_group']),
                    'employment': int(location_pop.loc[idx]['employment']),
                    'employment_location': int(location_pop.loc[idx]['employment_location']),
                    'education': int(location_pop.loc[idx]['education'])
                }]
            } for i, idx in enumerate(remaining_singletons)]
            households.extend(single_households)
            synthetic_population_df.loc[remaining_singletons, 'household_id'] = range(
                household_id, household_id + len(remaining_singletons))
            household_id += len(remaining_singletons)
        print(f"Completed location {location_id}: Created {len(households)} households so far")

    print(f"\nHousehold creation complete!")
    print(f"Total households created: {len(households)}")
    print(f"Total people assigned: {len(synthetic_population_df[synthetic_population_df['household_id'] != -1])}")
    print(f"People without households: {len(synthetic_population_df[synthetic_population_df['household_id'] == -1])}")

    if _tier_stats_output:
        with open(_tier_stats_output, 'w') as f:
            json.dump({
                'tier_stats_by_location': {str(k): dict(v) for k, v in tier_stats.items()},
                'tier_gap_records': tier_gap_records,
            }, f, indent=2)
        print(f"Saved child-adult relaxation-tier instrumentation to {_tier_stats_output}")

    return households, synthetic_population_df

def main():
    # Load all distribution data
    age_gender = load_age_gender_data()
    work = load_work_data()
    work_location = load_work_location_data()
    education_employment, gender_education_sums = load_education_data()

    age_gender_all = load_all_age_gender_data()
    # 4-D seed: axes = (gender[2], age_band[16], employment[7], education[14])
    # All-ones start lets IPF fit marginals freely; structural zeros enforce
    # logical impossibilities so IPF never allocates mass to them.
    seed_4d = np.ones((2,16,7,14))

    # Structural zeros: 0 = impossible, 1 = allowed
    # slicing and broadcasting is cleaner than nested for loops

    # Children (bands 0-2, ages 0-14) cannot be employed or pensioners
    seed_4d[:, :3, [0,1,3,4], :] = 0

    # Children cannot hold post-primary qualifications (education levels 0-7)
    seed_4d[:, :3, :7, :8] = 0

    age_gender_all = [df[df['location_id'] == 24237] for df in age_gender_all]
    
    xippp = np.hstack([age_gender_all[0]['sum'], age_gender_all[1]['sum']]) # gender totals, regardless age 
    xpjpp = age_gender_all[2].iloc[0][4:].to_numpy().astype(int) # age totals, regardless gender
    
    xijpp = np.ones((2, 16)) # people who are gender and age group, regardless employment status
    xijpp[0] = age_gender_all[0].iloc[0].iloc[-16:].to_numpy().reshape(16,).astype(int)
    xijpp[1] = age_gender_all[1].iloc[0].iloc[-16:].to_numpy().reshape(16,).astype(int)
    
    xppkl = np.ones((7,14))
    xppkl = education_employment[2].T # total, employment status, education 
    xijkp = np.ones((2,16,7))# people who are gender, age group, on each employment status
    xipkl = np.ones((2,7,14)) # gender, employment status, education
    xippl = np.ones((2,14)) # gender, education
    for i in range(2):
        xijkp[i] = work[i]
        xipkl[i] = education_employment[i].T
        xippl[i] = gender_education_sums[i]
    
    xpjkp = np.ones((16, 7)) # age group and employment status total
    xpjkp = work[2]
    xipkp = np.ones((2, 7)) # gender and employment status total

    ### Perform regional IPF (Achaia level-4) ###
    # Two marginals are used: age×gender×employment (3-D) and gender×employment×education (3-D).
    # IPF alternates between them until max cell relative change < CONVERGENCE_RATE.
    aggregates = [xijkp, xipkl]
    dimensions = [
        [0, 1, 2],  # gender × age × employment
        [0, 2, 3],  # gender × employment × education
    ]
    IPF = ipfn.ipfn(seed_4d, aggregates, dimensions, convergence_rate=CONVERGENCE_RATE, rate_tolerance=RATE_TOLERANCE)
    seed_4d = IPF.iteration()  # result: calibrated 4-D joint distribution for Achaia

    # Process each location of appropriate level
    location_ids = age_gender[2][age_gender[2]['level'] == LOCATION_LEVEL]['location_id'].to_numpy().astype(int)
    location_matrix_dict = {}

    for location_id in location_ids:
        ### Get location-specific person data ###
        current_loc_male = age_gender[0].loc[age_gender[0]['location_id'] == location_id]
        current_loc_female = age_gender[1].loc[age_gender[1]['location_id'] == location_id]
        current_loc_total = age_gender[2].loc[age_gender[2]['location_id'] == location_id]
        
        print(f"Processing location ID: {location_id}, name: {current_loc_male['name'].iloc[0]}")

        ### Process work location data ###
        # Use marginal distribution of the location as probability
        current_loc_work_location = work_location.loc[work_location['location_id'] == location_id]
        current_loc_work_location = current_loc_work_location.iloc[0, 3:]
        current_loc_work_location_distribution = current_loc_work_location / current_loc_work_location.sum()
        current_loc_work_location_distribution = current_loc_work_location_distribution.to_numpy().astype(float)
        
        # ASSUMING: work location is independent (don't have information not to make this assumption)

        # Add work location. last value of work location is for unemployed people
        # 5-D seed adds employment_location axis [0-4 = location bins, 5 = not applicable].
        # Employment_location is treated as conditionally independent of education given
        # employment status — the only available ELSTAT cross-tab is a location × location
        # flow matrix, not a full 5-way table.
        seed_5d = np.zeros((2,16,7,14,6))

        # Employed adults (band 3+, employment 0): distribute across 5 location bins
        # using the municipality-specific work-location flow distribution.
        seed_5d[:, 3:16, 0, :, :5] = (
            seed_4d[:, 3:16, 0, :, np.newaxis] * current_loc_work_location_distribution
        )

        # Non-employed (employment 1-6): employment_location fixed to 5 (not applicable)
        seed_5d[:, :, 1:, :, 5] = seed_4d[:, :, 1:, :]

        if VERBOSE==1:
            print(current_loc_work_location_distribution)
            filtered = seed_5d[:, 3:15, 0, :, :]  # gender: all, age_group: 3-14, employment: 0, education: all, work_location: all

            # Now sum across gender, age_group, education
            work_location_totals_filtered = filtered.sum(axis=(0, 1, 2))
            print(work_location_totals_filtered / work_location_totals_filtered.sum())

        # no scaling needed, ipf scales by itself
        # seed_5d = seed_5d * current_loc_total['sum'].iloc[0] # scale seed for current location

        ### Constraints for IPF ###
        xipppp = np.hstack([current_loc_male['sum'], current_loc_female['sum']]) # gender totals, regardless age 
        xpjppp = current_loc_total.iloc[0][4:].to_numpy().astype(int) # age totals, regardless gender
        
        xijppp = np.ones((2, 16)) # people who are gender and age group, regardless employment
        xijppp[0] = current_loc_male.iloc[0].iloc[-16:].to_numpy().reshape(16,).astype(int)
        xijppp[1] = current_loc_female.iloc[0].iloc[-16:].to_numpy().reshape(16,).astype(int)

        ### Perform IPF ###
        aggregates = [
            xipppp, 
            xpjppp, 
            xijppp
            ]
        dimensions = [
            [0], 
            [1], 
            [0, 1]]
        
        # seed_5d = np.ones((2,16,7,14,6))
        
        IPF = ipfn.ipfn(seed_5d, aggregates, dimensions, convergence_rate=CONVERGENCE_RATE, rate_tolerance=RATE_TOLERANCE)
        seed_5d = IPF.iteration()
              
        location_matrix_dict[location_id] = seed_5d # location_id has contingency table m
    
    ### Generate synthetic population ###
    synthetic_people = []
    for location_id, m in location_matrix_dict.items():
        for idx in np.ndindex(m.shape):
            # Iterates over every possible cell (internal numpy logic)
            count = stochastic_round(m[idx])
            if count > 0:
                # Get the actual indexes back from the iterator object
                gender, age_group, employment, education, employment_location = idx
                person_data = {
                    'gender': gender,
                    'age_group': age_group,
                    'employment': employment,
                    'employment_location': employment_location,
                    'education': education,
                    'location_id': location_id
                }
                synthetic_people.extend([person_data] * count)
    ### Convert to DataFrame ###
    synthetic_population_df = pd.DataFrame(synthetic_people)
    print(f"Generated population size: {synthetic_population_df.shape}")

    ### Household creation using italian microdataset ###
    if EXPERIMENTAL_HOUSEHOLD == 1:
        # Create households
        print("\nCreating households...")
        households, synthetic_population_df = create_households(synthetic_population_df)
        print(f"Created {len(households)} households")
        
        if FILE_OUTPUT:
            # Save households to JSON
            households_output = os.path.join(OUTPUT_DIR, 'households.json')
            with open(households_output, 'w') as f:
                json.dump(households, f, indent=2)
            print(f"Saved households to {households_output}")
            
            # Save updated synthetic population to CSV
            sp_output = os.path.join(OUTPUT_DIR, 'synthetic_population_with_households.csv')
            synthetic_population_df.to_csv(sp_output, index=False)
            print(f"Saved synthetic population with household IDs to {sp_output}")

        
    # --------------------- RESULT QUALITY ASSURANCE

    ### Compare result's distributions with input distributions ###
    
    # 1D Metrics
    invalid_people = get_invalid_people(synthetic_population_df)
    print('Number of invalid people', invalid_people.shape[0])
    print('% of invalid people', (invalid_people.shape[0]/synthetic_population_df.shape[0])*100)

    if SHOW_METRICS == 1:
        # Ensure output directory exists
        plot_dir = os.path.join(OUTPUT_DIR, 'plots')
        os.makedirs(plot_dir, exist_ok=True)

        # Age distribution
        fig, axes = plt.subplots(3,1,figsize=(10,15), sharex=True)
        for index, gender in enumerate(DATASET_GENDER_ORDER):
            input_age_dist = age_gender[index].iloc[0][4:]

            if gender == 'total':
                synthetic_df_to_compare = synthetic_population_df
            else:
                synthetic_df_to_compare = synthetic_population_df[synthetic_population_df['gender'] == index]

            chi2_stat, p_value = dataframe_chisquare_proportions_manual(
                synthetic_df_to_compare['age_group'],
                input_age_dist,
                debug=False
            )
            print(chi2_stat, p_value)
            
            _, ax = compare_marginals(
                synthetic_df_to_compare,
                input_age_dist,
                groupby_cols='age_group',
                input_label=f'Input age Distribution',
                output_label=f'Synthetic age Distribution',
                title=f'Age Distribution Comparison among {gender} of Achaia',
                normalize=False,
                ax=axes[index]
            )
        plt.tight_layout()
        if FILE_OUTPUT == 1:
            plt.savefig(os.path.join(plot_dir, 'age_distribution_achaia_all_genders.png'))
        if SHOW_VISUAL_METRICS: plt.show()
        # Age distribution per gender per location
        for location_id in location_ids:
            fig, axes = plt.subplots(3,1,figsize=(10,15), sharex=True)
            for index, gender in enumerate(DATASET_GENDER_ORDER):
                input_df = age_gender[index].loc[age_gender[index]['location_id'] == location_id]
                input_df = input_df.iloc[0][4:]
                # .to_numpy().astype(float) # redundant

                # Filter synthetic population for this location (and gender if not totals)
                if gender == 'total':
                    synthetic_df_to_compare = synthetic_population_df[synthetic_population_df['location_id'] == location_id]
                else:
                    synthetic_df_to_compare = synthetic_population_df[
                        (synthetic_population_df['location_id'] == location_id) &
                        (synthetic_population_df['gender'] == index)
                    ]

                chi2_stat, p_value = dataframe_chisquare_proportions_manual(
                    synthetic_df_to_compare['age_group'],
                    input_df,
                    debug=False
                )
                print(chi2_stat, p_value)

                compare_marginals(
                    synthetic_df_to_compare,
                    input_df,
                    groupby_cols='age_group',
                    input_label=f'Input age distribution',
                    output_label=f'Synthetic age distribution',
                    title=f'Age distribution comparison for {gender} population in location {location_id}',
                    normalize=False,
                    ax=axes[index]
                )
            plt.tight_layout()
            if FILE_OUTPUT == 1:
                plt.savefig(os.path.join(plot_dir, f'age_distribution_location_{location_id}.png'))
            if SHOW_VISUAL_METRICS: plt.show()

        # Age and employment per gender
        for index, gender in enumerate(DATASET_GENDER_ORDER):
            fig, axs = plt.subplots(1, 2, figsize=(12, 5))
        
            if gender == 'total':
                synthetic_df_to_compare = synthetic_population_df
            else:
                synthetic_df_to_compare = synthetic_population_df[
                (synthetic_population_df['gender'] == index)
                ]

            fig, axs = compare_2d_marginals_heatmap(
                synthetic_df=synthetic_df_to_compare,
                input_joint=work[index],
                groupby_cols=["employment", "age_group"],
                title=f"Age and employment joint distribution among {gender} population of Achaia",
                normalize=True,
                ax=axs
            )
            plt.tight_layout()
            if FILE_OUTPUT == 1:
                plt.savefig(os.path.join(plot_dir, f'age_employment_joint_{gender}.png'))
            if SHOW_VISUAL_METRICS: plt.show()
        
        # Education and employment per gender
        for index, gender in enumerate(DATASET_GENDER_ORDER):
            fig, axs = plt.subplots(1, 2, figsize=(12, 5))
            if gender == 'total':
                synthetic_df_to_compare = synthetic_population_df
            else:
                synthetic_df_to_compare = synthetic_population_df[
                    (synthetic_population_df['gender'] == index)
                    # TODO: this, even if logical, makes graph not similar/identical
                    # TODO: check the Μη κατατασσόμενοι (άτομα γεννηθέντα μετά την 1/1/2016)
                    # TODO: find the invalid people who skew 2d heatmap in the invalid func
                    # TODO: added more aggregates: employment and education joint still not perfect

                    # meaning, assigns work and higher(?) education to <3 age_group
                    & (synthetic_population_df['age_group'].isin(range(3,15)))
                ]
            fig, axs = compare_2d_marginals_heatmap(
                synthetic_df=synthetic_df_to_compare,
                input_joint=education_employment[index],
                groupby_cols=["employment", "education"],
                title=f"Employment and education joint distribution among {gender} population of Achaia",
                normalize=True,
                ax=axs
            )
            plt.tight_layout()
            if FILE_OUTPUT == 1:
                plt.savefig(os.path.join(plot_dir, f'education_employment_joint_{gender}.png'))
            if SHOW_VISUAL_METRICS: plt.show()

        # Work location in total
        for location_id in location_ids:
            current_loc_work_location = work_location.loc[work_location['location_id'] == location_id]
            current_loc_work_location = current_loc_work_location.iloc[0, 3:]
            input_df = current_loc_work_location

            # Filter WORKING OF AGE synthetic population for this location
            synthetic_df_to_compare = synthetic_population_df[
                    (synthetic_population_df['location_id'] == location_id)
                    & (synthetic_population_df['employment'] == 0)
                    & (synthetic_population_df['age_group'].isin(range(3,15)))
            ]

            chi2_stat, p_value = dataframe_chisquare_proportions_manual(
                synthetic_df_to_compare['employment_location'],
                current_loc_work_location,
                debug=False
            )
            print(chi2_stat, p_value)

            fig, ax = compare_marginals(
                synthetic_df_to_compare,
                input_df,
                groupby_cols='employment_location',
                input_label=f'Input work location distribution',
                output_label=f'Synthetic work location distribution',
                title=f'Work location comparison for population in location {location_id}',
                normalize=False,
            )
            plt.tight_layout()
            if FILE_OUTPUT == 1:
                plt.savefig(os.path.join(plot_dir, f'work_location_distribution_location_{location_id}.png'))
            if SHOW_VISUAL_METRICS: plt.show()

if __name__ == "__main__":
    np.set_printoptions(suppress=True)
    main()


