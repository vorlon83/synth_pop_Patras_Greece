import numpy as np
from ipfn import ipfn
import pandas as pd
np.set_printoptions(suppress=True)

# https://pypi.org/project/ipfn/


age_gender_male = pd.read_csv('python_ipf/marginal_distributions/age_gender/age_gender_achaia_male.csv', delimiter=',', encoding='utf-8')
age_gender_female = pd.read_csv('python_ipf/marginal_distributions/age_gender/age_gender_achaia_female.csv', delimiter=',',encoding='utf-8')
age_gender_total = pd.read_csv('python_ipf/marginal_distributions/age_gender/age_gender_achaia_total.csv', delimiter=',',encoding='utf-8')

work = np.genfromtxt('python_ipf/marginal_distributions/work/age_gender_work_rebin.csv', delimiter=',')
work = work[1:, 1:] # remove headers


m = np.ones((13, 9)) # how many categories for each attribute

m = work # TODO: deep copy?
print("before", m)

# xip = row sum
# name,sum,0-4,5-9,10-14,15-19,20-24,25-29,30-34,35-39,40-44,45-49,50-54,55-59,60-64,65-69,70-74,75+
# ΣΥΝΟΛΟ ΧΩΡΑΣ,10482487,412752,465740,538490,529726,520619,532682,569596,686797,794315,801716,807125,736214,698206,626429,555556,1206521
xip = [529726,520619,532682,569596,686797,794315,801716,807125,736214,698206,626429,555556,1206521] #row sum = age group: 0-9,10-19,20-29,30-39,40-49,50-59,60-69,70-79,80+
# xpj = column sum
# xpj = [128100, 123388,128100-123388, 134852, 114583, 134852-114583]

aggregates = [xip, xpj]
dimensions = [[0], [1]] # TODO: [0,1]?


# Perform IPF
IPF = ipfn.ipfn(m, aggregates, dimensions, convergence_rate=1e-12)
m = IPF.iteration()

print("after", m)