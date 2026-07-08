import numpy as np
import pandas as pd
from collections import Counter
import json
import age_group_mapping as agm

WRITE_TXT = True
WRITE_JSON = True

# Seeded RNG for stochastic age-bucket splitting.
# Must match AGE_MAP_SEED in age_group_mapping.py for reproducibility.
_rng = np.random.default_rng(agm.AGE_MAP_SEED)

# define row-wise function
def extract_people(row):
    '''
    Returns a list of object persons from a row of the dataframe.

    Age mapping uses sample_age_group() so that Italian buckets that
    straddle a Greek 5-year boundary are split stochastically rather than
    collapsed entirely into the lower band.  The seeded _rng makes results
    reproducible given the same AGE_MAP_SEED.
    '''
    # cap household capacity to 7
    ncomp = min(row["NCOMP"], 7)

    current_household = []

    # all people have 8 columns, with first being family id
    for i in range(1,ncomp+1): # offset by 1 (_1)
        # if POSIND_i==0 (absent from household), skip this person
        if row["POSIND_{}".format(i)] == 0:
            continue

        # if rpnuc2_i==0 (isolated member) and not single-person family, skip this person
        if ncomp > 1 and row["rpnuc2_{}".format(i)] == 0:
            continue

        sex = int(row["SESSO_{}".format(i)])
        age_bucket = int(row["ETAM_{}".format(i)])

        age = agm.sample_age_group(age_bucket, _rng)

        if age is None or sex is None: # redundant check
            continue

        current_household.append((sex-1, age))

    return current_household


if __name__ == "__main__":

    # Read from csv, delimiter is tab
    df = pd.read_csv("it_microdata_preprocess/SOG_Microdati_2016.txt", delimiter="\t")
    
    # use profammfr column as id
    df.set_index("profamMFR", inplace=True)

    household_compositions = []

    # https://stackoverflow.com/questions/70227908/iterating-over-rows-in-a-dataframe-in-pandas-is-there-a-difference-between-usin

    for index,row in df.iterrows():
        # append to a bigger list of tuples (so it's hashable)
        people_row = extract_people(row)
        household_compositions.append(people_row)


    print('Households recorded:', len(household_compositions))

    '''
    # Dataframe method
    # Convert the list of household compositions to a DataFrame
    #composition_df = pd.DataFrame(household_compositions, columns=['composition'])

    # Count occurrences of each unique household composition
    #composition_counts = composition_df['composition'].value_counts()
    '''
    # Sort each list by sex first, then age (less unique combinations and consistency in counting)
    household_compositions = [tuple(sorted(sublist, key=lambda x: (x[0], x[1]))) for sublist in household_compositions]

    # frequency of each household compisition
    # dict-like structure: "(2, 3), (1,3)": 4 (frequency)
    frequency = Counter(household_compositions)

    # sort by frequency
    frequency = dict(sorted(frequency.items(), key=lambda x: x[1], reverse=True))

    # at this point, trimming list is possible
    '''
    # trim all with frequency == 1
    frequency = {k: v for k, v in frequency.items() if v > 1}
    '''

    # get total frequency (sum)
    total_frequency = sum(frequency.values())

    print('Number of different household combinations:', len(frequency))

    # blank file
    open("it_microdata_preprocess/household_compositions.txt", "w").close()

    if WRITE_TXT:
        for unique_list, count in frequency.items():
            # write to file
            with open("it_microdata_preprocess/household_compositions.txt", "a") as f:
                f.write(f"{unique_list}: {count/total_frequency}\n")

    if WRITE_JSON:
        # serialize: list of ((tuples), float)
        # there might be a better way to do this
        serialized_list = []
        for unique_list, count in frequency.items():
            serialized_list.append((unique_list, count/total_frequency))


        # give name "household" to the tuples and "percentage" to the float
        serialized_list = [{"household": x[0], "percentage": x[1]} for x in serialized_list]

        # dump but dont add newlines inside brackets
        with open("it_microdata_preprocess/household_compositions.json", "w") as f:
            json.dump(serialized_list, f, indent=2)