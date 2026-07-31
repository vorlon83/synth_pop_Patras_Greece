# === FIGURE GENERATOR ===
# Generates (manuscript figures): img/fig_coresidence_structure.png
# Run from repo root: python figures/generate_coresidence_figure.py
# ============================================================
"""
Generate Figure: Age-based co-residence structure of the synthetic population.
Shows singleton rates by age band (zero child singletons by construction).
"""
import json
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import defaultdict

AGE_GROUP_LUT = {
    0:'0-4', 1:'5-9', 2:'10-14', 3:'15-19', 4:'20-24', 5:'25-29',
    6:'30-34', 7:'35-39', 8:'40-44', 9:'45-49', 10:'50-54',
    11:'55-59', 12:'60-64', 13:'65-69', 14:'70-74', 15:'75+'
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, 'data', 'synthpop', 'patras_households.json')

with open(JSON_PATH) as f:
    data = json.load(f)

# Singleton rate within each age band
band_total  = defaultdict(int)
band_single = defaultdict(int)
for hh in data:
    is_single = len(hh['members']) == 1
    for m in hh['members']:
        ag = m['age_group']
        band_total[ag] += 1
        if is_single:
            band_single[ag] += 1

bands  = list(range(16))
labels = [AGE_GROUP_LUT[i] for i in bands]
rates  = [100 * band_single[i] / band_total[i] if band_total[i] else 0 for i in bands]

sing_age  = [band_single[i] for i in bands]
total_sing = sum(sing_age)
sing_pct   = [100 * s / total_sing for s in sing_age]

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

# ----- Left panel: singleton rate by 5-year age band -----
ax = axes[0]
ax.bar(labels, rates, color='#1f77b4', edgecolor='white', linewidth=0.5)
ax.set_xlabel('Age band', fontsize=11)
ax.set_ylabel('Singleton rate (%)', fontsize=11)
ax.set_title('Singleton rate by age band\n(canonical population, seed 42)', fontsize=11)
ax.tick_params(axis='x', rotation=45)
ax.set_ylim(0, 35)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# Annotate peak bars
ax.text(4, rates[4] + 0.5, f'{rates[4]:.1f}%', ha='center', va='bottom',
        fontsize=8, color='#1f77b4', fontweight='bold')   # 20-24
ax.text(15, rates[15] + 0.5, f'{rates[15]:.1f}%', ha='center', va='bottom',
        fontsize=8, color='#1f77b4', fontweight='bold')   # 75+

# ----- Right panel: age distribution of singletons -----
ax2 = axes[1]
ax2.bar(labels, sing_pct, color='#1f77b4', edgecolor='white', linewidth=0.5)
ax2.set_xlabel('Age band', fontsize=11)
ax2.set_ylabel('Share of all singletons (%)', fontsize=11)
ax2.set_title(f'Age distribution of singleton households\n(N = {total_sing:,})', fontsize=11)
ax2.tick_params(axis='x', rotation=45)
ax2.grid(axis='y', alpha=0.3, linestyle='--')

ax2.text(15, sing_pct[15] + 0.3, f'{sing_pct[15]:.1f}%', ha='center', va='bottom',
         fontsize=9, fontweight='bold', color='#1f77b4')

plt.tight_layout()
out = os.path.join(ROOT, 'Synthetic_Population_manuscript', 'img', 'fig_coresidence_structure.png')
plt.savefig(out, dpi=200, bbox_inches='tight')
print(f"Saved: {out}")
print(f"Total singletons: {total_sing}")
for i in bands:
    if sing_pct[i] > 0.5:
        print(f"  band {i} ({AGE_GROUP_LUT[i]}): rate={rates[i]:.1f}%  share={sing_pct[i]:.1f}%")
plt.close()
