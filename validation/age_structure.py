"""Age structure: synthetic Patras vs ELSTAT Patras and ELSTAT Achaia."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ELSTAT Patras (level 5, 2423701) from age_gender_achaia_total.csv:
elstat_patras = [9080, 9944, 11562, 14463, 16693, 11634, 11499, 14023,
                 16099, 15865, 16139, 14242, 13239, 12048, 10453, 18943]

# ELSTAT Achaia (level 4, 24237) from age_gender_achaia_total.csv:
elstat_achaia = [12766, 14058, 16210, 19049, 20824, 15864, 15960, 19220,
                 22123, 22145, 22725, 20526, 19771, 17985, 15672, 31090]

# Synthetic Patras — from verify_population.py output (age_counts from E section)
# These are from the Counter over all members; we use ELSTAT as proxy since
# IPF calibrates to these marginals. Computing directly from JSON:
with open(os.path.join(ROOT, 'data', 'synthpop', 'patras_households.json')) as f:
    hh = json.load(f)

synth_bands = [0] * 16
for h in hh:
    for m in h['members']:
        synth_bands[m['age_group']] += 1

BAND_AGES = ['0-4','5-9','10-14','15-19','20-24','25-29','30-34','35-39',
             '40-44','45-49','50-54','55-59','60-64','65-69','70-74','75+']

# Five-group collapse
GROUPS = {
    '0-14':  [0, 1, 2],
    '15-29': [3, 4, 5],
    '30-44': [6, 7, 8],
    '45-64': [9, 10, 11, 12],
    '65+':   [13, 14, 15],
}

def five_group(bands):
    return {g: sum(bands[i] for i in idx) for g, idx in GROUPS.items()}

def median_age(bands):
    total = sum(bands)
    mid = total / 2
    cum = 0
    for b, n in enumerate(bands):
        if n == 0:
            continue
        if cum + n >= mid:
            frac = (mid - cum) / n
            lo = int(BAND_AGES[b].split('-')[0]) if '-' in BAND_AGES[b] else 75
            width = 5
            return lo + frac * width
        cum += n
    return None

sp = five_group(synth_bands)
ep = five_group(elstat_patras)
ea = five_group(elstat_achaia)
ts = sum(synth_bands)
tp = sum(elstat_patras)
ta = sum(elstat_achaia)

print('=== Age structure: Synthetic Patras vs ELSTAT Patras (primary validation) ===')
print(f'  {"Group":>6}  {"Synth n":>8}  {"Synth %":>8}  {"ELSTAT n":>9}  {"ELSTAT %":>9}  {"delta pp":>9}')
for g in GROUPS:
    sn, en = sp[g], ep[g]
    print(f'  {g:>6}  {sn:>8,}  {sn/ts:>8.2%}  {en:>9,}  {en/tp:>9.2%}  {sn/ts - en/tp:>+9.2%}')
print(f'  {"Median":>6}  {median_age(synth_bands):>8.1f}  {"":>8}  {median_age(elstat_patras):>9.1f}')

print()
print('=== Age structure: Synthetic Patras vs ELSTAT Achaia (regional reference) ===')
print(f'  {"Group":>6}  {"Synth %":>8}  {"ELSTAT %":>9}  {"delta pp":>9}')
for g in GROUPS:
    sn, en = sp[g], ea[g]
    print(f'  {g:>6}  {sn/ts:>8.2%}  {en/ta:>9.2%}  {sn/ts - en/ta:>+9.2%}')
print(f'  {"Median":>6}  {median_age(synth_bands):>8.1f}  {median_age(elstat_achaia):>9.1f}  {median_age(synth_bands)-median_age(elstat_achaia):>+9.1f}')
print()
print('Note: Patras is an urban center; lower 65+ share and younger median')
print('than the broader Achaia region (which includes rural/aging periphery)')
print(f'are demographic features of the target, not synthesis errors.')
