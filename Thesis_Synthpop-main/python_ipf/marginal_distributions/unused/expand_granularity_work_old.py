# we want bigger granularity on P(employment| age,gender), so using another dataset
# we split existing age groups into smaller ones  
import pandas as pd

age_groups = {
    "30-34": 0.289204392, # of 30-44
    "35-39": 0.328568804, # of 30-44
    "40-44": 0.382226804, # of 30-44
    "45-49": 0.358909016, # of 45-64
    "50-54": 0.324791526, # of 45-64
    "55-59": 0.2097395, # of 45-64
    "60-64": 0.106559957, # of 45-64
    "65-69": 0.886333195, # of 65+
    "70-74": 0.080132966, # of 65+
    "75+": 0.033533838 # of 65+
}

# get dataframe from file "age.csv"
df = pd.read_csv("python_ipf/marginal_distributions/work/age_gender_work_small_granularity.csv")

print(df)

# Initialize new bins
rebinned = {
    # do all 0 (no employment) but find the unemployed sum
    # '0-4': df.loc[0, df.columns[1:]] * 0,
    # '5-9': df.loc[0, df.columns[1:]] * 0,
    # '10-14': df.loc[0, df.columns[1:]] * 0,
    # keep 15-19 as is
    '15-19': df.loc[0, df.columns[1:]],
    # keep 20-24 as is
    '20-24': df.loc[1, df.columns[1:]],
    # keep 25-29 as is
    '25-29': df.loc[2, df.columns[1:]],
    # split 30-44
    '30-34': df.loc[3, df.columns[1:]] * age_groups['30-34'],
    '35-39': df.loc[3, df.columns[1:]] * age_groups['35-39'],
    '40-44': df.loc[3, df.columns[1:]] * age_groups['40-44'],
    # split 45-64
    '45-49': df.loc[4, df.columns[1:]] * age_groups['45-49'],
    '50-54': df.loc[4, df.columns[1:]] * age_groups['50-54'],
    '55-59': df.loc[4, df.columns[1:]] * age_groups['55-59'],
    '60-64': df.loc[4, df.columns[1:]] * age_groups['60-64'],
    # split 65+
    '65-69': df.loc[5, df.columns[1:]] * age_groups['65-69'],
    '70-74': df.loc[5, df.columns[1:]] * age_groups['70-74'],
    '75+': df.loc[5, df.columns[1:]] * age_groups['75+']
}

# Convert to DataFrame
rebinned_df = pd.DataFrame(rebinned).T

rebinned_df = rebinned_df.reset_index().rename(columns={'index': 'age_group'})

rebinned_df = pd.concat([rebinned_df], ignore_index=True)

# Round all numeric columns to integers
rebinned_df.iloc[:, 1:] = rebinned_df.iloc[:, 1:].round(0).astype(int)
# save to csv
rebinned_df.to_csv('python_ipf/marginal_distributions/work/age_gender_work_rebin.csv', index=False)