"""Loaders for ELSTAT 2021 Achaia marginal distributions used by main_ipf_pipeline.py.

Must be run (imported) from the Thesis_Synthpop-main/ directory because
DISTRIBUTION_DIR is a CWD-relative path — main_ipf_pipeline.py sets no chdir.
"""
import os
import pandas as pd

DISTRIBUTION_DIR = 'python_ipf/marginal_distributions/'


# to prevent wrong order of csv's in lists
DATASET_GENDER_ORDER = ['male', 'female', 'total']


ACHAIA_LEVEL = 4
LOCATION_LEVEL = 5 # controls granularity
# Levels other than 5 may not work. More configuring needs to be done
# Location level mapping:
# 4 = νομός (max)
# 5 = δήμος
# 6 = δημοτική ενότητα
# 7 = Δημοτική Κοινότητα
# 8 = χωριά, κοινότητες, οικισμοί (min)

def load_all_age_gender_data():
    age_gender = []
    
    for suffix in DATASET_GENDER_ORDER:
        file_path = os.path.join(DISTRIBUTION_DIR, 'age_gender', f'age_gender_achaia_{suffix}.csv')
        df = pd.read_csv(file_path, delimiter=',', encoding='utf-8')
        age_gender.append(df)
    return age_gender

def load_age_gender_data():
    """

    Load and filter age-gender distribution data.
    
    Contains: age, location (for each gender)

    Locality: 
    - country (0)
    - achaia (4)
    - municipality (5)
    - municipal unit (6)
    - municipal community (7) 
    - village/settlement (8)

    result_compare: Set to True to also load Achaia totals. 
    Used to compare with resulting synthetic population

    """
    age_gender = []
    
    for suffix in DATASET_GENDER_ORDER:
        file_path = os.path.join(DISTRIBUTION_DIR, 'age_gender', f'age_gender_achaia_{suffix}.csv')
        df = pd.read_csv(file_path, delimiter=',', encoding='utf-8')
        age_gender.append(df[df['level'].isin([ACHAIA_LEVEL, LOCATION_LEVEL])])
    return age_gender

def load_work_data():
    """

    Load and process work-related distribution data.

    Contains: work, age (for each gender)

    Locality:
    - achaia (4)

    """
    work = []
    for suffix in DATASET_GENDER_ORDER:
        file_path = os.path.join(DISTRIBUTION_DIR, 'work/local', f'achaia_work_{suffix}_expanded.csv')
        df = pd.read_csv(file_path, delimiter=',', encoding='utf-8')
        df = df.drop(df.index[0])  # Remove first row (sum)
        df = df.iloc[:, 1:]  # Remove first column
        for col in ['sum', 'active_sum', 'inactive_sum']:
            df = df.drop(columns=[col])
        work.append(df)
    return work

def load_work_location_data():
    """

    Load work location distribution data.
    
    Contains: work location, person location

    Locality:
    - achaia (4)
    - municipality (5)
    
    """
    file_path = os.path.join(DISTRIBUTION_DIR, 'work/local/work_location.csv')
    df = pd.read_csv(file_path, delimiter=',', encoding='utf-8')
    return df.drop(columns=['sum'])

def load_education_data():
    """
    
    Load and process education distribution data.
    
    Contains: education, employment (for each gender)
    
    Locality: 
    - achaia (4)
    
    """
    education = []
    gender_education_sums = []
    for suffix in DATASET_GENDER_ORDER:
        file_path = os.path.join(DISTRIBUTION_DIR, 'education', f'gender_education_employment_{suffix}.csv')
        df = pd.read_csv(file_path, delimiter=',', encoding='utf-8')
        df = df.iloc[:, 1:]  # Remove first column
        df = df.drop(df.index[0])  # Remove first row (sum)
        for col in ['sum', 'active_sum', 'inactive_sum']:
            if col == 'sum':
                gender_education_sums.append(df[col])
            df = df.drop(columns=[col])
        education.append(df)
    return education, gender_education_sums
