import numpy as np
import pandas as pd
from ipfn import ipfn


# !!!: iloc = row by position
# !!!: loc = row by label
np.set_printoptions(suppress=True)
# https://pypi.org/project/ipfn/

# 5 = δήμος
# 6 = δημοτική ενότητα
# 7 = Δημοτική Κοινότητα
# 8 = χωριά, κοινότητες, οικισμοί
LOCATION_LEVEL = 5 # controls granularity

age_gender_male = pd.read_csv('python_ipf/marginal_distributions/age_gender/age_gender_achaia_male.csv', delimiter=',', encoding='utf-8')
age_gender_female = pd.read_csv('python_ipf/marginal_distributions/age_gender/age_gender_achaia_female.csv', delimiter=',',encoding='utf-8')
age_gender_total = pd.read_csv('python_ipf/marginal_distributions/age_gender/age_gender_achaia_total.csv', delimiter=',',encoding='utf-8')

# keep rows of specific level only
age_gender_male = age_gender_male[age_gender_male['level'] == LOCATION_LEVEL]
age_gender_female = age_gender_female[age_gender_female['level'] == LOCATION_LEVEL]
age_gender_total = age_gender_total[age_gender_total['level'] == LOCATION_LEVEL]

age_gender_work = pd.read_csv('python_ipf/marginal_distributions/work/country/age_gender_work_percentages.csv', delimiter=',')
age_gender_work = age_gender_work.to_numpy()
age_gender_work = age_gender_work[:, 1:] # remove headers

# TODO: Add constraints

# ASSUMING: employment is same for all locations
# we use the same marginal distribution for all location ipfs

# np.zeros((3,1)) kids dont work (0% employment)
male_employed_percent = np.vstack([np.zeros((3,1)), age_gender_work[:,9:10]])
female_employed_percent = np.vstack([np.zeros((3,1)), age_gender_work[:,10:11]])
# TODO: Does this skew when used in xpjk since it doesnt account for weights?
sum_employed_percent = np.vstack([np.zeros((3,1)), age_gender_work[:,11:12]])

# ipf on each location
indexes = list(age_gender_male.index.values)
# 3, 101, 317, 469, 596

print("Sections to IPF:\n", age_gender_total)


location_matrix_dict = {}
for index in indexes:
    # individual level
    # Define a 3d array = 3 attributes
    # 1st dim : 0 = male, 1 = female
    # 2nd dim: 0...16 -> age groups
    # 3rd dim: 0 = employed, 1 = unemployed
    m = np.ones((2,16,2)) # how many categories for each attribute
    
    # Define the target marginals/totals for each dimension
    print("current location id:", index)
    current_loc_male = age_gender_male.loc[index]
    male_sum = current_loc_male['sum']
    current_loc_female = age_gender_female.loc[index]
    female_sum = current_loc_female['sum']
    current_loc_total = age_gender_total.loc[index]

    m[0, :, 0] = ((current_loc_male.iloc[-16:].to_numpy().reshape(-1,1))*male_employed_percent)[:,0].astype(int)
    m[0, :, 1] = ((current_loc_male.iloc[-16:].to_numpy().reshape(-1,1))*(1-male_employed_percent))[:,0].astype(int)
    m[1, :, 0] = ((current_loc_female.iloc[-16:].to_numpy().reshape(-1,1))*female_employed_percent)[:,0].astype(int)
    m[1, :, 1] = ((current_loc_female.iloc[-16:].to_numpy().reshape(-1,1))*(1-female_employed_percent))[:,0].astype(int)

    xipp = np.hstack([male_sum, female_sum]) # gender: male, women
    xpjp = current_loc_total[4:].to_numpy().astype(int) # age group: 0-5, ...
    of_working_age = current_loc_total[-13:].sum() # 15+
    of_non_working_age = current_loc_total[-16:].sum() - of_working_age

    # west greece unemployment is 9.4% (2021)
    # print(type(of_working_age*(0.094)))

    xppk = np.hstack((of_working_age*(1-0.094), of_working_age*(0.094)+of_non_working_age)) # employed ((9.4%)*15+), unemployed (100%*(0-15)+(100%-9.4%)*15+)
    xijp = np.ones((2,16)) # people who are gender and age group, regardless employment
    xijp[0] = current_loc_male.iloc[-16:].to_numpy().reshape(16,).astype(int)
    xijp[1] = current_loc_female.iloc[-16:].to_numpy().reshape(16,).astype(int)

    xpjk = np.ones((16,2)) # people who are age group and employed (0) or not (1), regardless gender
    xpjk[:, 0] = ((current_loc_total.iloc[-16:].to_numpy().reshape(-1,1))*sum_employed_percent)[:,0].astype(int)
    xpjk[:, 1] = ((current_loc_total.iloc[-16:].to_numpy().reshape(-1,1))*(100-sum_employed_percent))[:,0].astype(int)

    xipk = np.ones((2,2)) # people who are male (0) or women (1) and employed or not, regardless age
    male_total_employment_percent = 0.547962899
    female_total_employment_percent = 0.382306947

    xipk[0] = np.hstack((current_loc_male.iloc[3]*male_total_employment_percent, current_loc_male.iloc[3]*(1-male_total_employment_percent))) # male
    xipk[1] = np.hstack((current_loc_female.iloc[3]*female_total_employment_percent, current_loc_female.iloc[3]*(1-female_total_employment_percent))) # female

    aggregates = [xipp, xpjp, xppk, xijp, xpjk, xipk]
    dimensions = [[0], [1], [2], [0, 1], [1, 2], [0, 2]]

    # DEBUGGING: print aggregates
    # for agg in aggregates: print(agg), print('\n\n')

    # Perform IPF
    IPF = ipfn.ipfn(m, aggregates, dimensions, convergence_rate=1e-12)
    m = IPF.iteration()
    # TODO: sanity check totals are same with marginals
    m = m.round() # remove decimals

    # location_id has contingency table m
    location_matrix_dict[current_loc_total["location_id"]] = m



# merge citizens from each IPF iteration to form the whole population
synthetic_people = []
for location_id, m in location_matrix_dict.items():
    for gender in range(2):  # 0=male, 1=female
        for age_group in range(16):  # age groups
            for employment in range(2):  # 0=employed, 1=unemployed
                count = int(round(m[gender, age_group, employment])) # ensure it's integer
                if count > 0:
                        person_data = {
                            'gender': 'male' if gender == 0 else 'female',
                            'age_group': age_group,
                            'employment': 'employed' if employment == 0 else 'unemployed',
                            # "attach" location id to each citizen
                            'location_id': location_id
                        }
                        # generate citizens by multiplying
                        synthetic_people.extend([person_data]*count)

# Convert to DataFrame
synthetic_population_df = pd.DataFrame(synthetic_people)
print(synthetic_population_df.shape)
# [] for converting to shape (1,2)