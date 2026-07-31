# === FIGURE GENERATOR ===
# Generates (manuscript figures): img/fig_multilayer_network.png
# Run from repo root: python figures/generate_multilayer_network.py
# ============================================================
#!/usr/bin/env python3
"""
Five-layer contact network figure for the ABM.
Produces a 3D stacked-layer ("layer-cake") diagram showing 18 synthetic agents
across the five contact layers used in the epidemic simulation.

Output: Synthetic_Population_manuscript/img/fig_multilayer_network.png
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

rng = np.random.default_rng(42)

# ── 18 synthetic agents ───────────────────────────────────────────────────────
# age: 0=child(0-14)  1=adult(25-45)  2=adult(46-64)  3=elderly(65+)
# wp/sc = -1 → not a member of that institution
AGENTS = [
    {'id':  0, 'hh': 0, 'wp': 0, 'sc': -1, 'age': 1},   # HH0 – parent
    {'id':  1, 'hh': 0, 'wp': 1, 'sc': -1, 'age': 2},   # HH0 – parent
    {'id':  2, 'hh': 0, 'wp': -1,'sc': 0,  'age': 0},   # HH0 – child
    {'id':  3, 'hh': 0, 'wp': -1,'sc': 0,  'age': 0},   # HH0 – child
    {'id':  4, 'hh': 1, 'wp': 0, 'sc': -1, 'age': 1},   # HH1 – parent
    {'id':  5, 'hh': 1, 'wp': 1, 'sc': -1, 'age': 1},   # HH1 – parent
    {'id':  6, 'hh': 1, 'wp': -1,'sc': 0,  'age': 0},   # HH1 – child
    {'id':  7, 'hh': 2, 'wp': 0, 'sc': -1, 'age': 2},   # HH2 – adult
    {'id':  8, 'hh': 2, 'wp': -1,'sc': -1, 'age': 3},   # HH2 – elderly
    {'id':  9, 'hh': 2, 'wp': -1,'sc': -1, 'age': 3},   # HH2 – elderly
    {'id': 10, 'hh': 3, 'wp': 1, 'sc': -1, 'age': 1},   # HH3 – adult
    {'id': 11, 'hh': 3, 'wp': 0, 'sc': -1, 'age': 2},   # HH3 – adult
    {'id': 12, 'hh': 3, 'wp': -1,'sc': 0,  'age': 0},   # HH3 – child
    {'id': 13, 'hh': 4, 'wp': -1,'sc': -1, 'age': 3},   # HH4 – singleton elderly
    {'id': 14, 'hh': 5, 'wp': 1, 'sc': -1, 'age': 1},   # HH5 – adult
    {'id': 15, 'hh': 5, 'wp': 0, 'sc': -1, 'age': 2},   # HH5 – adult
    {'id': 16, 'hh': 5, 'wp': -1,'sc': 0,  'age': 0},   # HH5 – child
    {'id': 17, 'hh': 5, 'wp': -1,'sc': -1, 'age': 3},   # HH5 – elderly grandparent
]
N = len(AGENTS)

# ── Build membership groups ───────────────────────────────────────────────────
def group_by(key, skip=-1):
    g = {}
    for ag in AGENTS:
        v = ag[key]
        if v != skip:
            g.setdefault(v, []).append(ag['id'])
    return g

HH_MEMBERS  = group_by('hh')
WP_MEMBERS  = group_by('wp')
SC_MEMBERS  = group_by('sc')
AGE_MEMBERS = group_by('age', skip=None)   # age always set

# ── Node layout: clustered by household ──────────────────────────────────────
HH_CENTERS = {0: (0.18, 0.76), 1: (0.18, 0.30),
               2: (0.50, 0.78), 3: (0.50, 0.28),
               4: (0.82, 0.54), 5: (0.82, 0.20)}

xy = np.zeros((N, 2))
for hh_id, members in HH_MEMBERS.items():
    cx, cy = HH_CENTERS[hh_id]
    n = len(members)
    if n == 1:
        xy[members[0]] = [cx, cy]
    else:
        r = 0.055 + 0.008 * n
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False) + (np.pi / n)
        for k, ag_id in enumerate(members):
            xy[ag_id] = [cx + r * np.cos(angles[k]), cy + r * np.sin(angles[k])]

# ── Edge sets per layer ───────────────────────────────────────────────────────
def clique(members):
    return [(members[i], members[j])
            for i in range(len(members)) for j in range(i + 1, len(members))]

family_edges   = sum([clique(m) for m in HH_MEMBERS.values()], [])
work_edges     = sum([clique(m) for m in WP_MEMBERS.values()], [])
school_edges   = sum([clique(m) for m in SC_MEMBERS.values()], [])

# Random community: cross-household only, 10 edges
cross = [(i, j) for i in range(N) for j in range(i + 1, N)
         if AGENTS[i]['hh'] != AGENTS[j]['hh']]
rng.shuffle(cross)
rand_edges = cross[:10]

# Same-age / POLYMOD: within age cohort, capped per cohort for legibility
same_age_edges = []
for age, members in AGE_MEMBERS.items():
    edges = clique(members)
    if len(edges) > 5:
        idxs = rng.choice(len(edges), 5, replace=False)
        edges = [edges[i] for i in sorted(idxs)]
    same_age_edges.extend(edges)

LAYER_EDGES = [family_edges, work_edges, school_edges, rand_edges, same_age_edges]

# ── Layer styling ─────────────────────────────────────────────────────────────
LAYERS = [
    {'name': 'Family',              'color': '#4FC3F7',
     'beta': r'$\beta_\mathrm{fam}=0.0221$',    'z': 0},
    {'name': 'Workplace',           'color': '#FFB74D',
     'beta': r'$\beta_\mathrm{work}=0.10$',      'z': 1},
    {'name': 'School',              'color': '#81C784',
     'beta': r'$\beta_\mathrm{sch}=0.04$',       'z': 2},
    {'name': 'Community',           'color': '#CE93D8',
     'beta': r'$\beta_\mathrm{rand}=0.01$',      'z': 3},
    {'name': 'Same-age (POLYMOD)',  'color': '#EF9A9A',
     'beta': r'$\beta_\mathrm{age}=0.0005$',     'z': 4},
]

AGE_COLORS = {0: '#E65100', 1: '#1565C0', 2: '#2E7D32', 3: '#6A1B9A'}
AGE_LABELS = {0: 'Child 0–14', 1: 'Adult 25–45', 2: 'Adult 46–64', 3: 'Elderly 65+'}
AGE_MARKERS= {0: 's', 1: 'o', 2: 'o', 3: '^'}   # shape also encodes role

BG   = 'white'
ZSPC = 1.4        # z-spacing between layers

# ── Figure setup ──────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(14, 9), facecolor=BG)
ax  = fig.add_subplot(111, projection='3d')
ax.set_facecolor(BG)
ax.patch.set_facecolor(BG)

# ── Layer background planes ───────────────────────────────────────────────────
for layer in LAYERS:
    z   = layer['z'] * ZSPC
    col = layer['color']
    verts = [[(0.04, 0.04, z), (0.96, 0.04, z), (0.96, 0.96, z), (0.04, 0.96, z)]]
    poly  = Poly3DCollection(verts, alpha=0.12,
                             facecolor=col, edgecolor=col, linewidth=0.8)
    ax.add_collection3d(poly)

# ── Vertical identity spines (same agent across layers) ───────────────────────
for i in range(N):
    x, y = xy[i]
    ax.plot([x, x], [y, y], [0, (len(LAYERS) - 1) * ZSPC],
            color='#AAAAAA', linewidth=0.6, linestyle=':', alpha=0.9)

# ── Household boundary rings (family layer only) ──────────────────────────────
for hh_id, members in HH_MEMBERS.items():
    if len(members) < 2:
        continue
    pts = xy[members]
    cx, cy = pts.mean(axis=0)
    r = np.max(np.linalg.norm(pts - [cx, cy], axis=1)) + 0.06
    theta = np.linspace(0, 2 * np.pi, 80)
    ax.plot(cx + r * np.cos(theta), cy + r * np.sin(theta), np.zeros(80),
            color='#4FC3F7', alpha=0.25, linewidth=0.9, linestyle='--')

# household label (e.g. "HH 0") in family layer
for hh_id, members in HH_MEMBERS.items():
    pts = xy[members]
    cx, cy = pts.mean(axis=0)
    ax.text(cx, cy - 0.11, -0.05,
            f'HH {hh_id}', color='#4FC3F7', fontsize=6.5, alpha=0.5,
            ha='center', va='top')

# ── Edges: glow (thick translucent) + crisp (thin bright) ─────────────────────
for li, layer in enumerate(LAYERS):
    z   = li * ZSPC
    col = layer['color']
    for (i, j) in LAYER_EDGES[li]:
        xi, yi = xy[i];  xj, yj = xy[j]
        ax.plot([xi, xj], [yi, yj], [z, z], color=col, alpha=0.18, linewidth=5)
        ax.plot([xi, xj], [yi, yj], [z, z], color=col, alpha=0.80, linewidth=1.3)

# ── Nodes ──────────────────────────────────────────────────────────────────────
for li in range(len(LAYERS)):
    z = li * ZSPC
    for ag in AGENTS:
        i = ag['id'];  x, y = xy[i]
        col = AGE_COLORS[ag['age']]
        mkr = AGE_MARKERS[ag['age']]
        # halo
        ax.scatter(x, y, z, color=col, s=160, marker=mkr,
                   edgecolors='none', alpha=0.30, depthshade=False)
        # crisp node
        ax.scatter(x, y, z, color=col, s=60, marker=mkr,
                   edgecolors='#333333', linewidths=0.5, depthshade=False, zorder=10)

# ── Layer name + β text on each plane ─────────────────────────────────────────
for li, layer in enumerate(LAYERS):
    z   = li * ZSPC
    col = layer['color']
    # name in top-left of plane
    ax.text(0.06, 0.94, z + 0.04,
            layer['name'], color=col,
            fontsize=9.5, fontweight='bold', va='bottom', ha='left')
    # β value in top-right
    ax.text(0.94, 0.94, z + 0.04,
            layer['beta'], color=col,
            fontsize=8, va='bottom', ha='right', style='italic')

# ── Axes formatting ────────────────────────────────────────────────────────────
ax.view_init(elev=21, azim=-55)
ax.set_xlim(0.0, 1.0)
ax.set_ylim(0.0, 1.0)
ax.set_zlim(-0.05, (len(LAYERS) - 1) * ZSPC + 0.1)
ax.set_axis_off()

# ── Legend: node type ──────────────────────────────────────────────────────────
age_handles = [
    Line2D([0], [0], marker=AGE_MARKERS[k], linestyle='',
           markerfacecolor=AGE_COLORS[k], markeredgecolor='white',
           markersize=8, label=AGE_LABELS[k])
    for k in sorted(AGE_COLORS)
]
leg_age = fig.legend(handles=age_handles, loc='lower left',
                     bbox_to_anchor=(0.03, 0.03),
                     framealpha=0.85, labelcolor='black',
                     fontsize=9, title='Node role',
                     title_fontsize=9.5, facecolor='white', edgecolor='#AAAAAA')

# ── Legend: layer colours ──────────────────────────────────────────────────────
layer_handles = [
    Line2D([0], [0], color=lyr['color'], linewidth=2.5, label=lyr['name'])
    for lyr in LAYERS
]
leg_layer = fig.legend(handles=layer_handles, loc='lower right',
                       bbox_to_anchor=(0.97, 0.03),
                       framealpha=0.85, labelcolor='black',
                       fontsize=9, title='Contact layer',
                       title_fontsize=9.5, facecolor='white', edgecolor='#AAAAAA')

# ── Titles ─────────────────────────────────────────────────────────────────────
fig.text(0.46, 0.97,
         'Five-Layer Contact Network  ·  ABM',
         ha='center', va='top', fontsize=15, fontweight='bold', color='#111111')
fig.text(0.46, 0.935,
         '18-agent illustrative example  ·  Patras Synthetic Population  ·  SAR = 20 %',
         ha='center', va='top', fontsize=10, color='#555555')

# small note about β_fam derivation
fig.text(0.97, 0.97,
         r'$\beta_\mathrm{fam} = 1-(1-\mathrm{SAR})^{\gamma}$',
         ha='right', va='top', fontsize=9, color='#666666', style='italic')

# ── Save ───────────────────────────────────────────────────────────────────────
out = os.path.join(ROOT, 'Synthetic_Population_manuscript', 'img',
                   'fig_multilayer_network.png')
plt.savefig(out, dpi=180, bbox_inches='tight', facecolor=BG, edgecolor='none')
print(f"Saved → {out}")
plt.close()
