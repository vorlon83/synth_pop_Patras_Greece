import numpy as np
from ipfn import ipfn

np.set_printoptions(suppress=True)
# https://pypi.org/project/ipfn/


age_gender = np.genfromtxt('python_ipf/marginal_distributions/age_gender_western_greece_rebinned.csv', delimiter=',')
age_gender = age_gender[1:, 1:] # remove headers

age_gender_work = np.genfromtxt('marginal_distributions/work/age_gender_work.csv', delimiter=',')
age_gender_work = age_gender_work[1:, 1:] # remove headers
# remove last row of age_gender_work
age_gender_work_no_totals = age_gender_work[:-1, :]

#location_distribution = np.genfromtxt('marginal_distributions/people_per_achaia_municipality.csv', delimiter=',')
#location_distribution = location_distribution[1:, 1:] # remove headers

# TODO: Add constraints

# individual level
# Define a 3d array = 3 attributes
# 1st dim : 0 = male, 1 = female
# 2nd dim: 0...6 -> age groups
# 3rd dim: 0 = employed, 1 = unemployed
m = np.ones((2,6,2)) # how many categories for each attribute

m[0, :, :] = age_gender_work_no_totals[:, 1:3]
m[1, :, :] = age_gender_work_no_totals[:, 4:6]

# print(m[0])

# Define the target marginals/totals for each dimension
xipp = age_gender[-1, :2] # gender: male, women
xpjp = age_gender[:, -1] # age group: 0-9,10-19,20-29,30-39,40-49,50-59,60-69,70-79,80+
xppk = np.array([486165, 162055])  # sums to 648,220

xijp = np.ones((2,6)) # people who are gender and age group, regardless employment
xijp[0] = age_gender[:, 1].T
xijp[1] = age_gender[:, 2].T

xpjk = np.ones((6,2)) # people who are age group and employed (0) or not (1), regardless gender
xpjk[:, 0] = age_gender_work_no_totals[:, -2]
xpjk[:, 1] = age_gender_work_no_totals[:, -1]

xipk = np.ones((2,2)) # people who are male (0) or women (1) and employed or not, regardless age
xipk[0] = age_gender_work_no_totals[-1, 1]
xipk[1] = age_gender_work_no_totals[-1, 4]

aggregates = [xipp, xpjp, xppk, xijp, xpjk, xipk]
dimensions = [[0], [1], [2], [0, 1], [1, 2], [0, 2]]

# Perform IPF
IPF = ipfn.ipfn(m, aggregates, dimensions, convergence_rate=1e-12)
m = IPF.iteration()

print(age_gender_work[-1, 1:3])

# append target marginals under m for readability
# [] for converting to shape (1,2)
result = np.ones((2,7,2))

result[0] = np.append(m[0, :, :], [age_gender_work[-1, 1:3]], axis=0)
result[1] = np.append(m[1, :, :], [age_gender_work[-1, 4:6]], axis=0)

print(result[0])
