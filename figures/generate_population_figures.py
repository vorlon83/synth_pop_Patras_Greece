"""
Generate synthetic-population composition figures for the manuscript.

Outputs (saved to Synthetic_Population_manuscript/img/):
  fig_age_pyramid_full.png    -- full 215,927-person age-sex pyramid vs ELSTAT Patras
  fig_employment_stacked.png  -- employment-status composition by 5-year age band
"""
import json
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, 'data', 'synthpop', 'patras_households.json')
OUT_DIR  = os.path.join(ROOT, 'Synthetic_Population_manuscript', 'img')

BAND_LABELS = [
    '0–4','5–9','10–14','15–19','20–24','25–29',
    '30–34','35–39','40–44','45–49','50–54','55–59',
    '60–64','65–69','70–74','75+',
]
N_BANDS = 16

# ELSTAT 2021 Patras municipality (code 2423701) by age band and sex
# Source: age_gender_achaia_compatible.csv, level 5 row
ELSTAT_M = [4669,5089,6046,7323,8545,5890,5649,6798,7866,7704,7652,6577,6222,5592,4921,7991]
ELSTAT_F = [4409,4853,5519,7143,8147,5741,5847,7222,8230,8163,8489,7663,7018,6454,5533,10951]

# Employment category labels and display colours
EMP_LABELS = ['Employed','Unemployed','Student','Pensioner','Income recip.','Homemaker','Other inact.']
EMP_COLORS = ['#2171b5','#cb181d','#41ab5d','#9e9ac8','#fe9929','#fb6a4a','#bdbdbd']

# ── Load population ────────────────────────────────────────────────────────────
print('Loading population ...')
with open(JSON_PATH) as f:
    households = json.load(f)

synth_m   = np.zeros(N_BANDS, dtype=int)
synth_f   = np.zeros(N_BANDS, dtype=int)
emp_by_age = np.zeros((N_BANDS, 7), dtype=int)   # [age_band, employment_code]

for hh in households:
    for m in hh['members']:
        age  = m['age_group']
        emp  = m['employment']
        gend = m['gender']  # 0=male, 1=female
        if gend == 0:
            synth_m[age] += 1
        else:
            synth_f[age] += 1
        if 0 <= emp <= 6:
            emp_by_age[age, emp] += 1

total = int(synth_m.sum() + synth_f.sum())
print(f'  {total:,} individuals loaded')

# ── Figure 1: Full age-sex pyramid vs ELSTAT Patras ───────────────────────────
elstat_m = np.array(ELSTAT_M, dtype=float)
elstat_f = np.array(ELSTAT_F, dtype=float)

# Normalise each to 1,000 per 1,000 people for direct comparison
N_synth = total
N_elstat = elstat_m.sum() + elstat_f.sum()
scale = 1000.0

sm_rate = synth_m / N_synth * scale
sf_rate = synth_f / N_synth * scale
em_rate = elstat_m / N_elstat * scale
ef_rate = elstat_f / N_elstat * scale

y = np.arange(N_BANDS)
fig, ax = plt.subplots(figsize=(9, 7))

bar_h = 0.38
# Synthetic: solid bars
ax.barh(y + bar_h/2, -sm_rate, height=bar_h, color='#2171b5', label='Synthetic males')
ax.barh(y + bar_h/2,  sf_rate, height=bar_h, color='#cb181d', label='Synthetic females')
# ELSTAT: step outlines
ax.barh(y - bar_h/2, -em_rate, height=bar_h,
        color='none', edgecolor='#2171b5', linewidth=1.4,
        linestyle='--', label='ELSTAT males')
ax.barh(y - bar_h/2,  ef_rate, height=bar_h,
        color='none', edgecolor='#cb181d', linewidth=1.4,
        linestyle='--', label='ELSTAT females')

ax.set_yticks(y)
ax.set_yticklabels(BAND_LABELS, fontsize=10)
ax.set_xlabel('Individuals per 1,000 population', fontsize=11)
ax.set_title('Age–sex pyramid: synthetic Patras vs ELSTAT 2021\n'
             f'(synthetic $n={total:,}$; ELSTAT $n={int(N_elstat):,}$)', fontsize=11)

# Symmetric x-axis with labels as absolute values
xmax = max(sm_rate.max(), sf_rate.max(), em_rate.max(), ef_rate.max()) * 1.15
ax.set_xlim(-xmax, xmax)
xticks = np.arange(0, xmax, 5)
ax.set_xticks(np.concatenate([-xticks[::-1][:-1], xticks]))
ax.set_xticklabels([f'{abs(x):.0f}' for x in ax.get_xticks()], fontsize=9)

ax.axvline(0, color='gray', linewidth=0.8)
ax.text(-xmax*0.5, N_BANDS - 0.5, 'Male', ha='center', fontsize=11, color='#2171b5')
ax.text( xmax*0.5, N_BANDS - 0.5, 'Female', ha='center', fontsize=11, color='#cb181d')
ax.legend(loc='lower right', fontsize=9, ncol=2)
ax.grid(axis='x', alpha=0.3, linestyle='--')
plt.tight_layout()

out1 = os.path.join(OUT_DIR, 'fig_age_pyramid_full.png')
plt.savefig(out1, dpi=200, bbox_inches='tight')
print(f'Saved: {out1}')
plt.close()

# ── Figure 2: Employment composition by age band (stacked bars) ───────────────
# Normalise each row (age band) to 100%
emp_pct = np.zeros_like(emp_by_age, dtype=float)
row_totals = emp_by_age.sum(axis=1)
for i in range(N_BANDS):
    if row_totals[i] > 0:
        emp_pct[i] = emp_by_age[i] / row_totals[i] * 100

fig, ax = plt.subplots(figsize=(12, 5))
bottoms = np.zeros(N_BANDS)
x = np.arange(N_BANDS)
for j, (label, color) in enumerate(zip(EMP_LABELS, EMP_COLORS)):
    vals = emp_pct[:, j]
    ax.bar(x, vals, bottom=bottoms, color=color, label=label, width=0.75)
    bottoms += vals

ax.set_xticks(x)
ax.set_xticklabels(BAND_LABELS, rotation=45, ha='right', fontsize=9)
ax.set_ylabel('Share of age band (%)', fontsize=11)
ax.set_xlabel('5-year age band', fontsize=11)
ax.set_title('Employment-status composition by age band\n'
             'Synthetic Patras population ($n=215,927$)', fontsize=11)
ax.set_ylim(0, 100)
ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9, borderaxespad=0)
ax.grid(axis='y', alpha=0.3, linestyle='--')
plt.tight_layout()

out2 = os.path.join(OUT_DIR, 'fig_employment_stacked.png')
plt.savefig(out2, dpi=200, bbox_inches='tight')
print(f'Saved: {out2}')
plt.close()

print('Done.')
