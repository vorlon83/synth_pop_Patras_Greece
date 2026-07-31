import json
import numpy as np
from collections import Counter
import random

def household_rmse(
        synthetic_households, 
        input_compositions, 
        verbose=0, 
        random_observed=False, 
        top_percent=100,
        do_srmse=False):
    
    # Helper to convert household member list to a tuple of sorted (gender, age_group) pairs
    # Consistent comparison regardless of member order
    def household_signature(members):
        return tuple(sorted((m['gender'], m['age_group']) for m in members))

    # Count observed frequencies in synthetic households
    observed_counter = Counter()
    for h in synthetic_households:
        sig = household_signature(h['members'])
        observed_counter[sig] += 1

    if random_observed:
        for key in list(observed_counter.keys()):
            observed_counter[key] = random.randint(0, 30000)


    total_observed = sum(observed_counter.values())
    observed_freq = {k: v / total_observed for k, v in observed_counter.items()}

    # Expected frequencies from input compositions
    input_signatures = [tuple(sorted(tuple(member) for member in comp['household'])) for comp in input_compositions]
    input_percentages = [comp['percentage'] for comp in input_compositions]
    expected_freq = dict(zip(input_signatures, input_percentages))

    # 3. Align keys (all unique household types in either set)
    all_keys = set(observed_freq.keys()).union(expected_freq.keys())

    obs = np.array([observed_freq.get(k, 0.0) for k in all_keys])
    exp = np.array([expected_freq.get(k, 0.0) for k in all_keys])

    rmse = np.sqrt(np.mean((obs - exp) ** 2))

    # Compute RMSE for top_percent of expected types if requested
    rmse_top = None
    srmse_top = None

    # top%
    if top_percent != 100:
        top_percent = min(top_percent, 100)
        
        # Sort expected types by expected frequency
        sorted_types = sorted(expected_freq.items(), key=lambda x: -x[1])
        n_top = max(1, int(len(sorted_types) * top_percent / 100))
        top_keys = [sig for sig, _ in sorted_types[:n_top]]
        obs_top = np.array([observed_freq.get(k, 0.0) for k in top_keys])
        exp_top = np.array([expected_freq.get(k, 0.0) for k in top_keys])
        # Normalize so they sum to 1
        exp_top_sum = exp_top.sum()
        obs_top_sum = obs_top.sum()
        if exp_top_sum > 0:
            exp_top = exp_top / exp_top_sum
        if obs_top_sum > 0:
            obs_top = obs_top / obs_top_sum
        rmse_top = np.sqrt(np.mean((obs_top - exp_top) ** 2))
        mean_exp_top = np.mean(exp_top)
        
        if mean_exp_top > 0:
            srmse_top = rmse_top / mean_exp_top
        else:
            srmse_top = float('nan')

        # top% srmse
        if do_srmse:
            rmse = srmse_top
        
        # top% rmse
        else: 
            rmse = rmse_top

    # 100% srmse
    elif top_percent == 100 and do_srmse:
            mean_exp = np.mean(exp)
            srmse = rmse / mean_exp
            rmse = srmse

    if verbose >= 1:
        print(f"Total households in synthetic: {sum(observed_counter.values())}")
        print(f"Total household types in synthetic: {len(observed_counter)}")
        print(f"Total household types in input compositions: {len(expected_freq)}")
        if top_percent is not None and top_percent != 100:
            print(f"Top {top_percent}% covers {n_top} household types out of {len(expected_freq)}")
    
        # Print the distributions for inspection
        print("\nTop 10 observed household types (synthetic):")
        for sig, freq in sorted(observed_freq.items(), key=lambda x: -x[1])[:10]:
            print(f"{sig}: {freq:.4f}")

        print("\nTop 10 expected household types (input):")
        top_expected = sorted(expected_freq.items(), key=lambda x: -x[1])[:10]
        for sig, freq in top_expected:
            print(f"{sig}: {freq:.4f}")
        print("\nObserved frequencies for top 10 expected household types:")
        for sig, _ in top_expected:
            obs_freq = observed_freq.get(sig, 0.0)
            print(f"{sig}: {obs_freq:.4f}")

    return rmse

if __name__ == "__main__":
    # Load synthetic households (output)
    with open('python_ipf/ipf_results/households.json', 'r') as f:
        synthetic_households = json.load(f)

    # Load input household compositions (input)
    with open('it_microdata_preprocess/household_compositions.json', 'r') as f:
        input_compositions = json.load(f)

    n_iter = 10
    top_percents = [100, 50, 20, 10, 5]
    print(f"Running {n_iter} iterations for each top_percent value...")
    print(f"{'Top%':>6} | {'Case':>12} | {'Mean RMSE':>12} | {'Mean sRMSE':>12}")
    print('-'*52)
    for top_percent in top_percents:
        rmse_obs_list = []
        srmse_obs_list = []
        rmse_rand_list = []
        srmse_rand_list = []
        for _ in range(n_iter):
            # Observed
            rmse = household_rmse(
                synthetic_households, 
                input_compositions, 
                verbose=0,
                random_observed=False,
                top_percent=top_percent,
                do_srmse=False)
            srmse = household_rmse(
                synthetic_households, 
                input_compositions, 
                verbose=0,
                random_observed=False,
                top_percent=top_percent,
                do_srmse=True)
            rmse_obs_list.append(rmse)
            srmse_obs_list.append(srmse)
            # Randomized
            rmse = household_rmse(
                synthetic_households, 
                input_compositions, 
                verbose=0,
                random_observed=True,
                top_percent=top_percent,
                do_srmse=False)
            srmse = household_rmse(
                synthetic_households, 
                input_compositions, 
                verbose=0,
                random_observed=True,
                top_percent=top_percent,
                do_srmse=True)
            rmse_rand_list.append(rmse)
            srmse_rand_list.append(srmse)
        print(f"{top_percent:>6} | {'Observed':>12} | {np.mean(rmse_obs_list):12.6f} | {np.mean(srmse_obs_list):12.6f}")
        print(f"{top_percent:>6} | {'Randomized':>12} | {np.mean(rmse_rand_list):12.6f} | {np.mean(srmse_rand_list):12.6f}")
    print('-'*52)
