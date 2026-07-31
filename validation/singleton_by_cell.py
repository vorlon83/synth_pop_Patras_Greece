"""Singleton rate by (age_group, gender) — contact-layer check."""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(ROOT, 'data', 'synthpop', 'patras_households.json')) as f:
    hh = json.load(f)

BAND_AGES = ['0-4','5-9','10-14','15-19','20-24','25-29','30-34','35-39',
             '40-44','45-49','50-54','55-59','60-64','65-69','70-74','75+']

solo_by_cell = Counter()
total_by_cell = Counter()

for h in hh:
    for m in h['members']:
        k = (m['age_group'], m['gender'])
        total_by_cell[k] += 1
        if len(h['members']) == 1:
            solo_by_cell[k] += 1

overall = sum(1 for h in hh if len(h['members']) == 1) / len(hh)
print(f'Overall household singleton rate: {overall:.3f}  ({overall:.1%})')
print()
header = ('  band    age      M_solo   M_total    M_rate      F_solo   F_total    F_rate      gap_pp')
print(header)
print('  ' + '-' * (len(header)-2))

max_excess_band = None
max_excess = 0.0
warn_bands = []

for b in range(16):
    sm = solo_by_cell[(b, 0)]; tm = total_by_cell[(b, 0)]
    sf = solo_by_cell[(b, 1)]; tf = total_by_cell[(b, 1)]
    rm = sm / tm if tm else 0
    rf = sf / tf if tf else 0
    excess_m = rm / overall if overall else 0
    excess_f = rf / overall if overall else 0
    flag = ''
    if excess_m > 2.5 or excess_f > 2.5:
        flag = '  ** ELEVATED >2.5x overall'
        warn_bands.append((b, rm, rf))
    print(f'  {b:>4}  {BAND_AGES[b]:>6}  {sm:>9,}  {tm:>9,}  {rm:>9.1%}  {sf:>9,}  {tf:>9,}  {rf:>9.1%}  {rm-rf:>+9.1%}{flag}')
    if max(rm, rf) > max_excess:
        max_excess = max(rm, rf)
        max_excess_band = b

print()
print(f'Overall rate: {overall:.1%}')
print(f'Max cell rate: {max_excess:.1%} (band {max_excess_band}, {BAND_AGES[max_excess_band]})')
print()

# Concentration check: do working-age bands (6-12, ages 30-64) show over-representation?
working_age_bands = range(6, 13)
total_working = sum(total_by_cell[(b,0)] + total_by_cell[(b,1)] for b in working_age_bands)
solo_working = sum(solo_by_cell[(b,0)] + solo_by_cell[(b,1)] for b in working_age_bands)
working_solo_rate = solo_working / total_working if total_working else 0
print(f'Working-age (30-64) singleton rate: {working_solo_rate:.1%} vs overall {overall:.1%}')
ratio = working_solo_rate / overall if overall else 0
print(f'  Ratio: {ratio:.2f}x overall  (>1 = over-represented)')
if ratio < 1.5:
    print('  [OK] Working-age singleton concentration within 1.5x — contact layer acceptable')
elif ratio < 2.0:
    print('  [WARN] Moderate working-age singleton concentration — document as caveat')
else:
    print('  [FLAG] Strong working-age singleton concentration — contact layer bias')
