"""
GIS Assignment Visualizations
Generates 5 figures from initial_state.geojson and schools.geojson.

Input geojson: figures/initial_state_regenerated.geojson, produced by
figures/generate_initial_state_geojson.py from the current canonical
data/synthpop/patras_households.json (same assignment method as
gis/assignment.py, which produces data/gis_district_statistics.csv).
The older data/initial_state.geojson predates the canonical population/CSV
and is left untouched on disk but is no longer read here.

District identity uses DISTRICT_ID (unique, 0-54, matching districts.csv /
districts_table.tex / gis_district_statistics.csv), not the raw shapefile
GEIT_ID attribute -- GEIT_ID is NOT unique across the 55 Patras districts
(4 districts share GEIT_ID=9, 2 share GEIT_ID=49; see gis/util.py), which
previously caused fig2/fig5 to show a conflated "district 9" as the top
entry instead of the true largest district, DISTRICT_ID 54 (Zarouchleika).
"""

import json, ast, warnings, os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap, BoundaryNorm, Normalize
from matplotlib.cm import ScalarMappable
import matplotlib.gridspec as gridspec
from shapely.geometry import shape, Point

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "Synthetic_Population_manuscript", "img")
os.makedirs(IMG_DIR, exist_ok=True)

# ── cartographic helpers ─────────────────────────────────────────────────────────

def add_north_arrow(ax, x=0.955, y=0.965, size=0.045):
    """Draw a simple north arrow in axes-fraction coordinates."""
    ax.annotate(
        "N", xy=(x, y), xytext=(x, y - size),
        xycoords="axes fraction", textcoords="axes fraction",
        ha="center", va="center", fontsize=10, fontweight="bold", color="black",
        arrowprops=dict(arrowstyle="-|>", color="black", lw=1.6,
                         shrinkA=0, shrinkB=2),
        zorder=10,
    )

def add_scale_bar(ax, length_km=2, location=(0.05, 0.04), color="black"):
    """Draw a metric scale bar for a lon/lat (EPSG:4326) map, converting the
    requested ground length to degrees longitude at the map's mean latitude."""
    y0, y1 = ax.get_ylim()
    x0, x1 = ax.get_xlim()
    mean_lat = (y0 + y1) / 2.0
    km_per_deg_lon = 111.32 * np.cos(np.radians(mean_lat))
    bar_deg = length_km / km_per_deg_lon

    x_start = x0 + location[0] * (x1 - x0)
    y_bar = y0 + location[1] * (y1 - y0)
    x_end = x_start + bar_deg

    ax.plot([x_start, x_end], [y_bar, y_bar], color=color, lw=2.2,
            solid_capstyle="butt", zorder=10)
    tick_h = 0.006 * (y1 - y0)
    for xt in (x_start, x_end):
        ax.plot([xt, xt], [y_bar - tick_h, y_bar + tick_h], color=color, lw=1.4, zorder=10)
    ax.text((x_start + x_end) / 2, y_bar + 0.012 * (y1 - y0), f"{length_km} km",
            ha="center", va="bottom", fontsize=7.5, color=color, zorder=10)

# ── helpers ────────────────────────────────────────────────────────────────────

def parse_households(raw):
    """Return list of household dicts regardless of storage format."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            pass
        try:
            return ast.literal_eval(raw)
        except Exception:
            return []
    return []

AGE_LABELS = [
    "0–4","5–9","10–14","15–19","20–24","25–29",
    "30–34","35–39","40–44","45–49","50–54","55–59",
    "60–64","65–69","70–74","75+"
]
EMP_LABELS  = ["Employed","Unemployed","Student","Pensioner",
               "Income recip.","Homemaker","Other inactive"]
EDU_LABELS  = ["Doctoral","Master's","University","Higher Voc.",
               "Post-sec.","Lyceum","Voc. Lyceum","Voc. School",
               "Gymnasium","Primary","Incomplete primary",
               "Preschool only","Illiterate","Not classifiable"]

# ── load geojson ───────────────────────────────────────────────────────────────
print("Loading initial_state_regenerated.geojson …")
gdf = gpd.read_file(os.path.join(ROOT, "figures", "initial_state_regenerated.geojson"))
print(f"  {len(gdf)} raw features")

# ── parse + deduplicate ─────────────────────────────────────────────────────────
# Each building can appear multiple times; keep the row with the most households.
records = []
for _, row in gdf.iterrows():
    hhs = parse_households(row["households"])
    records.append({
        "osm_id":      row["osm_id"],
        "DISTRICT_ID": row["DISTRICT_ID"],
        "geometry":    row.geometry,
        "households":  hhs,
        "n_hh":        len(hhs),
        "n_people":    sum(len(h.get("members", [])) for h in hhs),
    })

df_raw = pd.DataFrame(records)
# keep max-household row per (osm_id, DISTRICT_ID)
idx = df_raw.groupby("osm_id")["n_hh"].idxmax()
df_bld = df_raw.loc[idx].copy().reset_index(drop=True)
bld = gpd.GeoDataFrame(df_bld, geometry="geometry", crs="EPSG:4326")
print(f"  {len(bld)} unique buildings")
print(f"  {bld['n_hh'].sum()} total household assignments")
print(f"  {bld['n_people'].sum()} total people assigned")

# ── person-level data ───────────────────────────────────────────────────────────
print("Extracting person records …")
people = []
for _, row in df_bld.iterrows():
    for hh in row["households"]:
        sz = len(hh.get("members", []))
        for m in hh.get("members", []):
            people.append({
                "gender":    m.get("gender"),
                "age_group": m.get("age_group"),
                "employment":m.get("employment"),
                "education": m.get("education"),
                "hh_size":   sz,
                "DISTRICT_ID": row["DISTRICT_ID"],
            })
people = pd.DataFrame(people)
print(f"  {len(people)} persons in assigned buildings")

# ── load schools ────────────────────────────────────────────────────────────────
print("Loading schools.geojson …")
sch_raw = gpd.read_file(os.path.join(ROOT, "data", "schools.geojson"))
sch = sch_raw.drop_duplicates(subset=["name","edu_level"]).copy()
sch["edu_level"] = sch["edu_level"].astype(str).str.strip()
print(f"  {len(sch)} unique schools")

# ── district summary ─────────────────────────────────────────────────────────────
# Grouped by DISTRICT_ID (unique, matches districts.csv / gis_district_statistics.csv),
# NOT the raw shapefile GEIT_ID attribute, which is not unique across districts.
dist = (bld[bld["DISTRICT_ID"].notna()]
        .groupby("DISTRICT_ID")
        .agg(n_buildings=("n_hh","count"),
             n_hh=("n_hh","sum"),
             n_people=("n_people","sum"))
        .reset_index()
        .sort_values("n_people", ascending=False))

# ══════════════════════════════════════════════════════════════════════════════
# FIG 1 – SPATIAL OVERVIEW: buildings coloured by district, schools overlaid
# ══════════════════════════════════════════════════════════════════════════════
print("\nFig 1: spatial overview …")
bld["centroid_x"] = bld.geometry.centroid.x
bld["centroid_y"] = bld.geometry.centroid.y

# only assigned buildings for colour plot
occ = bld[bld["n_hh"] > 0].copy()
unassigned = bld[(bld["n_hh"] == 0) & bld["DISTRICT_ID"].notna()].copy()

# colour by district (DISTRICT_ID, unique 0-54)
n_dist = 55
cmap55 = matplotlib.colormaps.get_cmap("tab20").resampled(20)

fig, ax = plt.subplots(figsize=(10, 13))
ax.set_facecolor("#f5f5f7")
fig.patch.set_facecolor("white")

# unassigned buildings – light grey
ax.scatter(unassigned["centroid_x"], unassigned["centroid_y"],
           s=0.4, color="#c0c0c8", alpha=0.5, linewidths=0, rasterized=True)

# assigned buildings – colour by district mod 20
district_ids = occ["DISTRICT_ID"].fillna(0).astype(int)
colors_bld = [cmap55(int(g) % 20) for g in district_ids]
ax.scatter(occ["centroid_x"], occ["centroid_y"],
           s=1.4, c=colors_bld, alpha=0.85, linewidths=0, rasterized=True)

# schools – distinct markers by level (darker colours for white background)
sch_styles = {
    "0": dict(marker="^", color="#cc8800", s=70, zorder=5, label="Preschool (νηπιαγωγείο)",
              edgecolors="white", linewidths=0.5),
    "1": dict(marker="s", color="#0077bb", s=70, zorder=5, label="Primary (δημοτικό)",
              edgecolors="white", linewidths=0.5),
    "2": dict(marker="D", color="#cc4400", s=70, zorder=5, label="Lower secondary (γυμνάσιο)",
              edgecolors="white", linewidths=0.5),
    "3": dict(marker="*", color="#aa0044", s=120, zorder=5, label="Upper secondary (λύκειο)",
              edgecolors="white", linewidths=0.5),
}
for lvl, sty in sch_styles.items():
    sub = sch[sch["edu_level"] == lvl]
    if len(sub):
        ax.scatter(sub.geometry.x, sub.geometry.y, **sty)

ax.set_xlabel("Longitude", fontsize=9)
ax.set_ylabel("Latitude",  fontsize=9)
ax.tick_params(labelsize=7)
for spine in ax.spines.values():
    spine.set_edgecolor("#bbbbbb")

legend_bld   = mpatches.Patch(color="#4488ff", label="Occupied buildings (colour = district)")
legend_empty = mpatches.Patch(color="#c0c0c8", label="Unoccupied buildings")
handles = [legend_bld, legend_empty] + [
    plt.scatter([], [], marker=sty["marker"], color=sty["color"], s=sty["s"])
    for sty in sch_styles.values()
]
labels  = [legend_bld.get_label(), legend_empty.get_label()] + [s["label"] for s in sch_styles.values()]
ax.legend(handles, labels, loc="upper left", fontsize=7.5,
          facecolor="white", edgecolor="#aaaaaa", framealpha=0.9)

ax.set_title("Patras GIS Assignment: Building footprints & school locations\n"
             f"({len(occ):,} occupied | {len(unassigned):,} unoccupied | {len(sch)} schools)",
             fontsize=11, pad=10)

add_scale_bar(ax, length_km=2, location=(0.05, 0.035))
add_north_arrow(ax, x=0.955, y=0.965, size=0.045)

plt.tight_layout()
plt.savefig(os.path.join(IMG_DIR, "fig1_spatial_overview.png"), dpi=200,
            facecolor="white", bbox_inches="tight")
plt.close()
print("  saved fig1_spatial_overview.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 2 – DISTRICT SUMMARY (households & people per district, top 30)
# ══════════════════════════════════════════════════════════════════════════════
print("Fig 2: district summary …")
top = dist.head(30).copy()
top["DISTRICT_ID"] = top["DISTRICT_ID"].astype(int).astype(str)
x = np.arange(len(top))

fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
fig.suptitle("District-level spatial assignment summary (top 30 districts by population)",
             fontsize=12, fontweight="bold")

bar_colors_hh = plt.cm.Blues(np.linspace(0.4, 0.9, len(top)))
bar_colors_pp = plt.cm.Oranges(np.linspace(0.4, 0.9, len(top)))

axes[0].bar(x, top["n_hh"], color=bar_colors_hh, edgecolor="white", linewidth=0.3)
axes[0].set_ylabel("Households assigned", fontsize=9)
axes[0].set_ylim(0, top["n_hh"].max() * 1.15)
for i, v in enumerate(top["n_hh"]):
    axes[0].text(i, v + 5, str(v), ha="center", va="bottom", fontsize=6, rotation=90)
axes[0].grid(axis="y", alpha=0.3, linestyle="--")
axes[0].spines[["top","right"]].set_visible(False)

axes[1].bar(x, top["n_people"], color=bar_colors_pp, edgecolor="white", linewidth=0.3)
axes[1].set_ylabel("People assigned", fontsize=9)
axes[1].set_ylim(0, top["n_people"].max() * 1.15)
for i, v in enumerate(top["n_people"]):
    axes[1].text(i, v + 20, str(v), ha="center", va="bottom", fontsize=6, rotation=90)
axes[1].grid(axis="y", alpha=0.3, linestyle="--")
axes[1].spines[["top","right"]].set_visible(False)
axes[1].set_xlabel("District ID", fontsize=9)

plt.xticks(x, top["DISTRICT_ID"], rotation=90, fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(IMG_DIR, "fig2_district_summary.png"), dpi=180, bbox_inches="tight")
plt.close()
print("  saved fig2_district_summary.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 3 – HOUSEHOLD SIZE DISTRIBUTION vs WG reference
# ══════════════════════════════════════════════════════════════════════════════
print("Fig 3: household size distribution …")
all_hh_sizes = []
for _, row in df_bld.iterrows():
    for hh in row["households"]:
        all_hh_sizes.append(len(hh.get("members", [])))

sz_series = pd.Series(all_hh_sizes)
cats = [1, 2, 3, 4, "5+"]
synth_counts = [
    (sz_series == 1).sum(),
    (sz_series == 2).sum(),
    (sz_series == 3).sum(),
    (sz_series == 4).sum(),
    (sz_series >= 5).sum(),
]
total_hh = len(sz_series)
synth_pct = [c / total_hh * 100 for c in synth_counts]

# ELSTAT 2021 Western Greece reference (5 size categories)
wg_pct = [32.2, 28.9, 17.4, 14.7, 6.8]  # from manuscript

x = np.arange(len(cats))
w = 0.35
fig, ax = plt.subplots(figsize=(8, 5))
b1 = ax.bar(x - w/2, synth_pct, w, label="Synthetic S1 (this study)", color="#2196F3", alpha=0.88)
b2 = ax.bar(x + w/2, wg_pct,    w, label="ELSTAT 2021 Western Greece (reference)", color="#FF7043", alpha=0.88)

for bar in b1:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
            f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8)
for bar in b2:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
            f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8)

ax.set_xticks(x)
ax.set_xticklabels([str(c) for c in cats], fontsize=10)
ax.set_xlabel("Household size (number of members)", fontsize=10)
ax.set_ylabel("Share of households (%)", fontsize=10)
ax.set_title(f"Household size distribution — Synthetic S1 vs ELSTAT Western Greece\n"
             f"N={total_hh:,} synthetic households  |  JSD = 0.009 bits  |  "
             f"Mean synthetic: {sz_series.mean():.2f}  |  WG mean ≈ 2.45",
             fontsize=9)
ax.legend(fontsize=9)
ax.grid(axis="y", alpha=0.3, linestyle="--")
ax.spines[["top","right"]].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(IMG_DIR, "fig3_hh_size_distribution.png"), dpi=180, bbox_inches="tight")
plt.close()
print("  saved fig3_hh_size_distribution.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 4 – AGE PYRAMID (16 bands × male/female)
# ══════════════════════════════════════════════════════════════════════════════
print("Fig 4: age pyramid …")
male_counts   = people[people["gender"] == 0]["age_group"].value_counts().reindex(range(16), fill_value=0)
female_counts = people[people["gender"] == 1]["age_group"].value_counts().reindex(range(16), fill_value=0)
total_people_fig = len(people)

fig, ax = plt.subplots(figsize=(9, 8))
y = np.arange(16)
bar_m = ax.barh(y, -male_counts.values,   color="#2196F3", alpha=0.85, label="Male",   height=0.7)
bar_f = ax.barh(y,  female_counts.values, color="#E91E63", alpha=0.85, label="Female", height=0.7)

max_val = max(male_counts.max(), female_counts.max())
ax.set_xlim(-max_val * 1.15, max_val * 1.15)
ax.set_yticks(y)
ax.set_yticklabels(AGE_LABELS, fontsize=9)
ax.axvline(0, color="black", linewidth=0.8)

xticks = ax.get_xticks()
ax.set_xticklabels([f"{abs(int(t)):,}" for t in xticks], fontsize=8)
ax.set_xlabel("Number of individuals", fontsize=10)
ax.set_title(f"Age–sex pyramid — spatially assigned population\n"
             f"N = {total_people_fig:,} persons  |  {len(bld[bld['n_hh']>0]):,} occupied buildings",
             fontsize=10)
ax.legend(fontsize=9, loc="lower right")
ax.grid(axis="x", alpha=0.3, linestyle="--")
ax.spines[["top","right"]].set_visible(False)

# annotate male / female sides
ax.text(-max_val * 0.5, 15.6, "← Male", fontsize=9, color="#2196F3", ha="center", fontweight="bold")
ax.text( max_val * 0.5, 15.6, "Female →", fontsize=9, color="#E91E63", ha="center", fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(IMG_DIR, "fig4_age_pyramid.png"), dpi=180, bbox_inches="tight")
plt.close()
print("  saved fig4_age_pyramid.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 5 – MULTI-PANEL: buildings-per-district heatmap + occupancy map + employment
# ══════════════════════════════════════════════════════════════════════════════
print("Fig 5: multi-panel summary …")

fig = plt.figure(figsize=(16, 7))
gs  = gridspec.GridSpec(1, 3, figure=fig, wspace=0.32)

# ── panel A: occupancy scatter (households per building, log colour) ──────────
ax_a = fig.add_subplot(gs[0])
ax_a.set_facecolor("#f0f0f5")

# show ALL buildings (centroid dots)
n_hh_plot = np.clip(bld["n_hh"].values, 0, 5)
cmap_occ  = plt.cm.YlOrRd
norm_occ  = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5, 5.5], cmap_occ.N)

sc = ax_a.scatter(bld["centroid_x"], bld["centroid_y"],
                  c=n_hh_plot, cmap=cmap_occ, norm=norm_occ,
                  s=0.5, alpha=0.6, linewidths=0, rasterized=True)
cb = fig.colorbar(ScalarMappable(norm=norm_occ, cmap=cmap_occ), ax=ax_a,
                  shrink=0.7, pad=0.02)
cb.set_ticks([0,1,2,3,4,5])
cb.set_ticklabels(["0","1","2","3","4","5+"], fontsize=7)
cb.set_label("Households assigned", fontsize=8)
ax_a.set_title("Building occupancy\n(households per footprint)", fontsize=9, fontweight="bold")
ax_a.set_xlabel("Longitude", fontsize=8); ax_a.set_ylabel("Latitude", fontsize=8)
ax_a.tick_params(labelsize=7)
ax_a.spines[["top","right"]].set_visible(False)
add_scale_bar(ax_a, length_km=2, location=(0.06, 0.03))
add_north_arrow(ax_a, x=0.92, y=0.955, size=0.06)

# ── panel B: employment breakdown ─────────────────────────────────────────────
ax_b = fig.add_subplot(gs[1])
emp_counts = people["employment"].value_counts().reindex(range(7), fill_value=0)
emp_pct    = emp_counts / emp_counts.sum() * 100

emp_colors = ["#4CAF50","#F44336","#2196F3","#9C27B0","#FF9800","#795548","#607D8B"]
bars = ax_b.barh(range(7), emp_pct.values[::-1],
                 color=emp_colors[::-1], alpha=0.88, height=0.65)
ax_b.set_yticks(range(7))
ax_b.set_yticklabels(EMP_LABELS[::-1], fontsize=8)
ax_b.set_xlabel("Share of assigned population (%)", fontsize=8)
ax_b.set_title("Employment status\nof assigned population", fontsize=9, fontweight="bold")
for bar, val in zip(bars, emp_pct.values[::-1]):
    ax_b.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
              f"{val:.1f}%", va="center", fontsize=7.5)
ax_b.grid(axis="x", alpha=0.3, linestyle="--")
ax_b.spines[["top","right"]].set_visible(False)
ax_b.set_xlim(0, emp_pct.max() * 1.3)

# ── panel C: school distribution by type ─────────────────────────────────────
ax_c = fig.add_subplot(gs[2])
ax_c.set_facecolor("#f0f0f5")

sch_colors = {"0":"#FFC107","1":"#03A9F4","2":"#FF5722","3":"#9C27B0"}
sch_markers= {"0":"^","1":"s","2":"D","3":"*"}
sch_names  = {"0":"Preschool (νηπιαγωγείο)",
              "1":"Primary (δημοτικό)",
              "2":"Lower secondary (γυμνάσιο)",
              "3":"Upper secondary (λύκειο)"}

# background: unoccupied buildings faint
ax_c.scatter(bld["centroid_x"], bld["centroid_y"],
             s=0.2, color="#ccccdd", alpha=0.3, linewidths=0, rasterized=True)

for lvl, color in sch_colors.items():
    sub = sch[sch["edu_level"] == lvl]
    if len(sub):
        ax_c.scatter(sub.geometry.x, sub.geometry.y,
                     color=color, marker=sch_markers[lvl],
                     s=55, zorder=5, edgecolors="white", linewidths=0.5,
                     label=f"{sch_names[lvl]} (n={len(sub)})")

ax_c.legend(fontsize=7, loc="upper left", framealpha=0.85)
ax_c.set_title("School locations by level\n(185 active schools)", fontsize=9, fontweight="bold")
ax_c.set_xlabel("Longitude", fontsize=8); ax_c.set_ylabel("Latitude", fontsize=8)
ax_c.tick_params(labelsize=7)
ax_c.spines[["top","right"]].set_visible(False)
add_scale_bar(ax_c, length_km=2, location=(0.06, 0.03))
add_north_arrow(ax_c, x=0.92, y=0.955, size=0.06)

fig.suptitle("GIS Spatial Assignment — Summary Panels", fontsize=13, fontweight="bold", y=1.01)
plt.savefig(os.path.join(IMG_DIR, "fig5_summary_panels.png"), dpi=180, bbox_inches="tight")
plt.close()
print("  saved fig5_summary_panels.png")

# ══════════════════════════════════════════════════════════════════════════════
# PRINT SUMMARY STATS
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Summary ──────────────────────────────────────────────")
print(f"Total buildings (unique):        {len(bld):,}")
print(f"Occupied buildings:              {(bld['n_hh']>0).sum():,}")
print(f"Unoccupied buildings:            {(bld['n_hh']==0).sum():,}")
print(f"Total households assigned:       {bld['n_hh'].sum():,}")
print(f"Total people assigned:           {bld['n_people'].sum():,}")
print(f"Mean HH/building (occupied):     {bld[bld['n_hh']>0]['n_hh'].mean():.2f}")
print(f"Max HH/building:                 {bld['n_hh'].max()}")
print(f"Districts covered (DISTRICT_ID): {bld['DISTRICT_ID'].nunique()}")
print(f"Unique schools:                  {len(sch)}")
print(f"Mean household size (assigned):  {sz_series.mean():.3f}")
print(f"\nAll figures saved to {IMG_DIR}")
