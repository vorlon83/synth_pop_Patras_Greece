"""
GIS household assignment for Section 6.3 statistics.

Runs the spatial assignment on the accepted population
(data/synthpop/patras_households.json) and reports:
  - Total individuals assigned to actual residential building polygons
  - Individuals unplaced (no centroid fallback; peripheral areas)
  - District-level fill rate: min, median, max across 55 districts
  - Building occupancy: mean, median, max households per occupied building

Writes:
  gis_assignment_results.txt   -- console-formatted stats summary
  district_statistics.csv      -- per-district statistics
"""
import math, os, sys, json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, Point

# ── Project root ──────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gis'))
import util

print("Working directory:", os.getcwd())

# ── File paths ────────────────────────────────────────────────────────────────
OSM_FOLDER   = os.path.join(ROOT, 'data', 'greece-260611-free.shp')
BUILDINGS_F  = os.path.join(OSM_FOLDER, 'gis_osm_buildings_a_free_1.shp')
LANDUSE_F    = os.path.join(OSM_FOLDER, 'gis_osm_landuse_a_free_1.shp')
SCHOOLS_F    = os.path.join(ROOT, 'data', 'SCHOOLS', 'patras_schools_shifted.shp')
HOUSEHOLDS_F = os.path.join(ROOT, 'data', 'synthpop', 'patras_households.json')

# ── Load districts ────────────────────────────────────────────────────────────
print("\nLoading districts ...")
districts = util.load_districts()
print(f"  {len(districts)} districts loaded.")

minx, miny, maxx, maxy = districts.total_bounds
bbox = box(minx, miny, maxx, maxy)

target_pop_sum = int(districts['pop2021'].sum())
print(f"  Total target population (districts): {target_pop_sum:,}")

# ── Load GIS layers ───────────────────────────────────────────────────────────
print("\nLoading OSM landuse ...")
landuse = util.gpd_load_wrapper(LANDUSE_F, bbox=bbox)
landuse = landuse.cx[minx:maxx, miny:maxy]

print("Loading OSM buildings ...")
buildings = util.gpd_load_wrapper(BUILDINGS_F, bbox=bbox)
buildings = buildings.drop("name", axis=1)
buildings = buildings.drop("code", axis=1)
buildings = buildings.cx[minx:maxx, miny:maxy]

print("Loading schools ...")
schools = util.gpd_load_wrapper(SCHOOLS_F, bbox=bbox)
print(f"  {len(schools)} school features loaded.")

# ── Residential filtering ─────────────────────────────────────────────────────
print("\nFiltering residential buildings ...")
residential_landuse = landuse[landuse['fclass'].isin(['residential', 'retail'])]
residential_landuse = residential_landuse.drop('name', axis=1)

residential_buildings = gpd.sjoin(
    buildings,
    residential_landuse[['geometry']],
    predicate='within',
    how='inner'
)
residential_buildings = residential_buildings.drop('index_right', axis=1)

schools_with_districts = gpd.sjoin(
    schools,
    districts[['DISTRICT_ID', 'geometry']],
    how='left',
    predicate='intersects'
)
schools_with_districts = schools_with_districts.drop('index_right', axis=1)

eligible_buildings = gpd.sjoin(
    residential_buildings,
    districts[['DISTRICT_ID', 'geometry', 'pop2021']],
    predicate='intersects',
    how='left'
)
print(f"  {len(eligible_buildings):,} residential buildings eligible for assignment.")

# ── Load households ───────────────────────────────────────────────────────────
print(f"\nLoading households from {HOUSEHOLDS_F} ...")
with open(HOUSEHOLDS_F, 'r') as f:
    households = json.load(f)
# Seed the household-order shuffle so the spatial assignment is reproducible.
# PIPELINE_SEED (default 42) matches the seed convention used elsewhere in the pipeline.
_SEED = int(os.environ.get('PIPELINE_SEED', '42'))
np.random.seed(_SEED)
np.random.shuffle(households)

total_households = len(households)
total_people = sum(len(hh['members']) for hh in households)
avg_hh_size = total_people / total_households
print(f"  {total_households:,} households, {total_people:,} people, "
      f"mean size {avg_hh_size:.2f}")

# ── Building capacity ─────────────────────────────────────────────────────────
# OSM building tags are sparse: ~60% have no 'type' or 'yes'.  Capacities are
# conservative lower bounds to avoid placing 20 households in a detached house.
SINGLE_FAMILY = {'house', 'detached', 'terrace', 'bungalow', 'semidetached_house'}
MULTI_FAMILY  = {'apartments', 'residential', 'flat', 'dormitory'}

def building_cap(btype):
    if pd.isna(btype) or str(btype).lower() in ('yes', ''):
        return 3  # unknown tag: assume small apartment block
    t = str(btype).lower()
    if t in SINGLE_FAMILY: return 1
    if t in MULTI_FAMILY:  return 5
    return 2

min_hh = 1
max_hh = 5  # hard cap: prevents extreme over-occupancy of large footprints

# ── Assignment ────────────────────────────────────────────────────────────────
eligible_buildings = eligible_buildings.reset_index(drop=True)
eligible_buildings['households'] = pd.Series(
    [[] for _ in range(len(eligible_buildings))], dtype=object
)
col_pos = eligible_buildings.columns.get_loc('households')

hh_index     = 0
assigned_people = 0

print("\nAssigning households to buildings by district ...")
for district_id, district_buildings in eligible_buildings.groupby('DISTRICT_ID'):
    if pd.isna(district_id):
        continue
    district_target_pop = districts.loc[
        districts['DISTRICT_ID'] == district_id, 'pop2021'
    ].iloc[0]
    district_people = 0
    building_indices = list(district_buildings.index)
    n_buildings = len(building_indices)

    # Two-pass strategy: first distribute a base allocation evenly, then top-up
    # buildings with spare capacity until the district population target is met.
    # This avoids under-filling all buildings while also avoids single buildings
    # receiving an outsized share.
    est_hh_needed     = math.ceil(district_target_pop / avg_hh_size)
    base_per_building = max(min_hh, est_hh_needed // n_buildings)
    extra_count       = est_hh_needed % n_buildings

    # First pass: assign base + 1 to the first extra_count buildings
    for i, pos in enumerate(building_indices):
        if hh_index >= total_households:
            break
        btype = eligible_buildings.at[pos, 'type'] if 'type' in eligible_buildings.columns else None
        cap = min(building_cap(btype), max_hh)
        n = min(base_per_building + (1 if i < extra_count else 0), cap)
        selected = []
        for _ in range(n):
            if hh_index >= total_households:
                break
            hh = households[hh_index]
            selected.append(hh)
            district_people += len(hh['members'])
            assigned_people += len(hh['members'])
            hh_index += 1
        eligible_buildings.iat[pos, col_pos] = selected

    # Second pass: top-up if target not met
    if district_people < district_target_pop:
        for pos in building_indices:
            if hh_index >= total_households or district_people >= district_target_pop:
                break
            btype = eligible_buildings.at[pos, 'type'] if 'type' in eligible_buildings.columns else None
            cap = min(building_cap(btype), max_hh)
            current = eligible_buildings.iat[pos, col_pos]
            if len(current) < cap:
                hh = households[hh_index]
                current.append(hh)
                eligible_buildings.iat[pos, col_pos] = current
                district_people += len(hh['members'])
                assigned_people += len(hh['members'])
                hh_index += 1

print(f"  Placed {hh_index:,}/{total_households:,} households "
      f"({100*hh_index/total_households:.1f}%).")
print(f"  Assigned {assigned_people:,}/{total_people:,} people "
      f"({100*assigned_people/total_people:.1f}%); "
      f"unplaced {total_people - assigned_people:,} "
      f"({100*(total_people - assigned_people)/total_people:.1f}%).")

# ── Per-district statistics ───────────────────────────────────────────────────
print("\nComputing per-district statistics ...")
district_rows = []
for district_id, db in eligible_buildings.groupby('DISTRICT_ID'):
    if pd.isna(district_id):
        continue
    target_pop = int(districts.loc[districts['DISTRICT_ID'] == district_id, 'pop2021'].iloc[0])
    district_name = districts.loc[districts['DISTRICT_ID'] == district_id, 'NAME'].values[0]

    total_bldg  = len(db)
    filled_mask = db['households'].apply(lambda x: isinstance(x, list) and len(x) > 0)
    filled_bldg = int(filled_mask.sum())
    fill_rate   = 100.0 * filled_bldg / total_bldg if total_bldg > 0 else 0.0

    assigned_pop = int(db['households'].apply(
        lambda hhs: sum(len(hh['members']) for hh in hhs) if isinstance(hhs, list) else 0
    ).sum())

    total_hh_placed = int(db['households'].apply(
        lambda hhs: len(hhs) if isinstance(hhs, list) else 0
    ).sum())

    district_rows.append({
        'DISTRICT_ID':        int(district_id),
        'NAME':               district_name,
        'pop2021':            target_pop,
        'total_people':       assigned_pop,
        'pop_accuracy':       round(100*(1 - abs(assigned_pop - target_pop)/target_pop), 2),
        'total_households':   total_hh_placed,
        'num_buildings':      total_bldg,
        'buil_with_households': filled_bldg,
        'fill_rate':          round(fill_rate, 2),
    })

dist_df = pd.DataFrame(district_rows).sort_values('DISTRICT_ID')

# ── Fill rate statistics ──────────────────────────────────────────────────────
fill_rates = dist_df['fill_rate'].values
fr_min, fr_med, fr_max = float(np.min(fill_rates)), float(np.median(fill_rates)), float(np.max(fill_rates))
print(f"\n  District fill rate (n={len(dist_df)} districts):")
print(f"    Min:    {fr_min:.1f}%")
print(f"    Median: {fr_med:.1f}%")
print(f"    Max:    {fr_max:.1f}%")

# ── Building occupancy statistics ─────────────────────────────────────────────
occupied_mask = eligible_buildings['households'].apply(
    lambda x: isinstance(x, list) and len(x) > 0
)
occupied = eligible_buildings[occupied_mask]
hh_counts = occupied['households'].apply(len)
occ_mean   = float(hh_counts.mean())
occ_median = float(hh_counts.median())
occ_max    = int(hh_counts.max())
print(f"\n  Households per occupied building (n={len(occupied):,} buildings):")
print(f"    Mean:   {occ_mean:.2f}")
print(f"    Median: {occ_median:.1f}")
print(f"    Max:    {occ_max}")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("SECTION 6.3 NUMBERS")
print("="*65)
print(f"Total synthetic individuals (households JSON): {total_people:,}")
print(f"District target population (55 districts):     {target_pop_sum:,}")
print(f"Individuals assigned to building polygons:     {assigned_people:,} "
      f"({100*assigned_people/total_people:.1f}%)")
print(f"Individuals unplaced (no centroid fallback):   {total_people - assigned_people:,} "
      f"({100*(total_people - assigned_people)/total_people:.1f}%)")
print()
print(f"District-level fill rate (n=55 districts):")
print(f"  Min:    {fr_min:.1f}%")
print(f"  Median: {fr_med:.1f}%")
print(f"  Max:    {fr_max:.1f}%")
print()
print(f"Households per occupied building:")
print(f"  Mean:   {occ_mean:.2f}")
print(f"  Median: {occ_median:.1f}")
print(f"  Max:    {occ_max}")
print("="*65)

# ── Save outputs ──────────────────────────────────────────────────────────────
csv_path = os.path.join(ROOT, 'data', 'gis_district_statistics.csv')
dist_df.to_csv(csv_path, index=False)
print(f"\nSaved: {csv_path}")

results_txt = (
    f"GIS assignment results (patras_households.json)\n"
    f"{'='*65}\n"
    f"Total synthetic individuals: {total_people:,}\n"
    f"District target population:  {target_pop_sum:,}\n"
    f"Assigned to building polygons: {assigned_people:,} ({100*assigned_people/total_people:.1f}%)\n"
    f"Unplaced (peripheral/rural):   {total_people - assigned_people:,} ({100*(total_people - assigned_people)/total_people:.1f}%)\n"
    f"\nDistrict fill rate (n=55 districts):\n"
    f"  Min:    {fr_min:.1f}%\n"
    f"  Median: {fr_med:.1f}%\n"
    f"  Max:    {fr_max:.1f}%\n"
    f"\nHouseholds per occupied building:\n"
    f"  Mean:   {occ_mean:.2f}\n"
    f"  Median: {occ_median:.1f}\n"
    f"  Max:    {occ_max}\n"
)
results_path = os.path.join(ROOT, 'gis_assignment_results.txt')
with open(results_path, 'w') as f:
    f.write(results_txt)
print(f"Saved: {results_path}")
print("\nDONE.")
