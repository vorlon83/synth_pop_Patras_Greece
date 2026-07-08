import pandas as pd

df = pd.read_csv('marginal_distributions/age_gender/age_gender_western_greece.csv')
print(df)

# Initialize new bins
rebinned = {
    '<19': df.loc[0:1, ['men', 'women']].sum(),
    '19-24': df.loc[2, ['men', 'women']] * (5/10),
    '25-29': df.loc[2, ['men', 'women']] * (5/10),
    '30-44': df.loc[3, ['men', 'women']] + df.loc[4, ['men', 'women']] * (5/10),
    '45-64': df.loc[4, ['men', 'women']] * (5/10) + df.loc[5, ['men', 'women']].sum() + df.loc[6, ['men', 'women']] * (5/10),
    '>64': df.loc[6, ['men', 'women']] * (5/10) + df.loc[7:8, ['men', 'women']].sum(),
}

# Convert to DataFrame
rebinned_df = pd.DataFrame(rebinned).T
rebinned_df['sum'] = rebinned_df['men'] + rebinned_df['women']

rebinned_df = rebinned_df.reset_index().rename(columns={'index': 'age_group'})
# Add total sum row
total_sum = rebinned_df[['men', 'women', 'sum']].sum()
total_sum['age_group'] = 'Total'
rebinned_df = pd.concat([rebinned_df, pd.DataFrame([total_sum])], ignore_index=True)
print(rebinned_df)

# save to csv
rebinned_df.to_csv('marginal_distributions/age_gender/age_gender_western_greece_rebinned.csv', index=False)