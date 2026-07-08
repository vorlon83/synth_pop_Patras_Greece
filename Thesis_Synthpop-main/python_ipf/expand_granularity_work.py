# we want bigger granularity on P(employment| age,gender), so using another dataset
# we split existing age groups into smaller ones  
import pandas as pd
import os
# from age_gender_achaia_total.csv
age_groups = {
    "0-4": 12766,
    "5-9": 14058,
    "10-14": 16210,
}
age_groups["total"] = age_groups["0-4"]+age_groups["5-9"]+age_groups["10-14"]

# get work dataframe
folder = 'python_ipf/marginal_distributions/work/local/'
file_names = [f"achaia_work_{suffix}" for suffix in ['male', 'female', 'total']]

for file in file_names:
    path = os.path.join(folder, file+'.csv')
    df = pd.read_csv(path, delimiter=',', encoding='utf-8')

    # Initialize new bins
    rebinned = {
        'sum': df.loc[0, df.columns[1:]],
        '0-4': df.loc[1, df.columns[1:]]*(age_groups["0-4"]/age_groups["total"]),
        '5-9': df.loc[1, df.columns[1:]]*(age_groups["5-9"]/age_groups["total"]),
        '10-14': df.loc[1, df.columns[1:]]*(age_groups["10-14"]/age_groups["total"]),
    }

    # Convert to DataFrame
    rebinned_df = pd.DataFrame(rebinned).T

    rebinned_df = rebinned_df.reset_index().rename(columns={'index': 'age_group'})

    rebinned_df = pd.concat([rebinned_df, df[2:]])


    rebinned_df = pd.concat([rebinned_df], ignore_index=True)

    # Round all numeric columns to integers
    rebinned_df.iloc[:, 1:] = rebinned_df.iloc[:, 1:].round(0).astype(int)
    print(rebinned_df)

    # save to csv
    save_path = os.path.join(folder, file+'_expanded.csv')
    rebinned_df.to_csv(save_path, index=False)