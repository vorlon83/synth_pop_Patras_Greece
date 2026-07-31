"""
Regenerate a current, canonical-data-consistent building-level geojson for
figures/visualize_gis.py, WITHOUT touching the existing data/initial_state.geojson
or data/gis_district_statistics.csv on disk (both left untouched/reversible).

Why this is needed
-------------------
data/initial_state.geojson on disk predates data/gis_district_statistics.csv
and data/synthpop/patras_households.json (see file mtimes) and was generated
by an older/different assignment run: it assigns only ~64.7k people (vs the
canonical 182,179) and its building properties carry only the raw shapefile
'GEIT_ID' attribute as a "district id". GEIT_ID is NOT unique across the 55
Patras districts (util.py: "GEIT_ID isn't unique so can't be used to identify
each district") -- 4 districts collapse onto GEIT_ID=9 and 2 onto GEIT_ID=49 --
which is why figures grouped by GEIT_ID (fig2/fig5 in the old committed PNGs)
showed a conflated "district 9" as the top entry instead of the true largest
district, DISTRICT_ID 54 (Zarouchleika).

This script re-runs the same building-assignment method as gis/assignment.py
(same OSM buildings/landuse inputs, same residential filtering, same building
capacity heuristic, same two-pass fill strategy, same household source
data/synthpop/patras_households.json) but additionally attaches the unique,
sequential DISTRICT_ID (0-54, from gis/util.load_districts()) used everywhere
else in the manuscript (districts.csv / districts_table.tex / gis_district_
statistics.csv), and writes the resulting building-level GeoDataFrame (with
each building's assigned households) to a NEW file,
figures/initial_state_regenerated.geojson, for figures/visualize_gis.py to
consume -- deliberately not overwriting the existing data/initial_state.geojson,
so this regeneration is reversible / auditable and gis/assignment.py (which
owns data/gis_district_statistics.csv) is left untouched.

This script reads PIPELINE_SEED the same way gis/assignment.py does (env var,
default 42), so the two scripts draw an identical seeded household shuffle and
the raw (undeduplicated) building x district assignment produced here is now
bit-identical to gis/assignment.py's own eligible_buildings assignment. The
totals printed by this script's "Placed .../... households" / "Assigned
.../... people" lines match gis/assignment.py's canonical run exactly.

Any residual gap between the manuscript figures and gis_district_statistics.csv
is NOT introduced here -- it previously came entirely from a deduplication step
in figures/visualize_gis.py (collapsing each building that straddles more than
one district polygon down to a single row for map rendering, which also
silently dropped that row's households from the numeric aggregates). That
script has been fixed to use the full undeduplicated rows for every numeric
aggregate and the deduplicated view only for the two spatial scatter maps.

Run from the repository root:
    python figures/generate_initial_state_geojson.py
"""
import json
import math
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "gis"))
import util  # noqa: E402

OSM_FOLDER = os.path.join(ROOT, "data", "greece-260611-free.shp")
BUILDINGS_F = os.path.join(OSM_FOLDER, "gis_osm_buildings_a_free_1.shp")
LANDUSE_F = os.path.join(OSM_FOLDER, "gis_osm_landuse_a_free_1.shp")
HOUSEHOLDS_F = os.path.join(ROOT, "data", "synthpop", "patras_households.json")
# NOTE: deliberately NOT overwriting the pre-existing data/initial_state.geojson
# in place -- that file, and data/gis_district_statistics.csv (owned by
# gis/assignment.py), are left untouched so this regeneration is reversible /
# auditable. The new, current-data-consistent geojson is written alongside it
# under figures/, and figures/visualize_gis.py is pointed at this new path.
OUT_GEOJSON = os.path.join(ROOT, "figures", "initial_state_regenerated.geojson")

print("Loading districts ...")
districts = util.load_districts()
print(f"  {len(districts)} districts loaded.")

minx, miny, maxx, maxy = districts.total_bounds
bbox = box(minx, miny, maxx, maxy)

print("Loading OSM landuse ...")
landuse = util.gpd_load_wrapper(LANDUSE_F, bbox=bbox)
landuse = landuse.cx[minx:maxx, miny:maxy]

print("Loading OSM buildings ...")
buildings = util.gpd_load_wrapper(BUILDINGS_F, bbox=bbox)
buildings = buildings.drop(columns=["name", "code"])
buildings = buildings.cx[minx:maxx, miny:maxy]

print("Filtering residential buildings ...")
residential_landuse = landuse[landuse["fclass"].isin(["residential", "retail"])]
residential_landuse = residential_landuse.drop(columns=["name"])

residential_buildings = gpd.sjoin(
    buildings, residential_landuse[["geometry"]], predicate="within", how="inner"
)
residential_buildings = residential_buildings.drop(columns=["index_right"])

eligible_buildings = gpd.sjoin(
    residential_buildings,
    districts[["DISTRICT_ID", "GEIT_ID", "geometry", "pop2021"]],
    predicate="intersects",
    how="left",
)
eligible_buildings = eligible_buildings.drop(columns=["index_right"])
print(f"  {len(eligible_buildings):,} residential buildings eligible for assignment.")

print(f"Loading households from {HOUSEHOLDS_F} ...")
with open(HOUSEHOLDS_F, "r") as f:
    households = json.load(f)
# Seed the household-order shuffle the same way as gis/assignment.py so this
# export is drawn from the identical seeded shuffle that produces
# data/gis_district_statistics.csv (PIPELINE_SEED, default 42).
_SEED = int(os.environ.get("PIPELINE_SEED", "42"))
np.random.seed(_SEED)
np.random.shuffle(households)

total_households = len(households)
total_people = sum(len(hh["members"]) for hh in households)
avg_hh_size = total_people / total_households
print(f"  {total_households:,} households, {total_people:,} people, mean size {avg_hh_size:.2f}")

SINGLE_FAMILY = {"house", "detached", "terrace", "bungalow", "semidetached_house"}
MULTI_FAMILY = {"apartments", "residential", "flat", "dormitory"}


def building_cap(btype):
    if pd.isna(btype) or str(btype).lower() in ("yes", ""):
        return 3
    t = str(btype).lower()
    if t in SINGLE_FAMILY:
        return 1
    if t in MULTI_FAMILY:
        return 5
    return 2


min_hh = 1
max_hh = 5

eligible_buildings = eligible_buildings.reset_index(drop=True)
eligible_buildings["households"] = pd.Series(
    [[] for _ in range(len(eligible_buildings))], dtype=object
)
col_pos = eligible_buildings.columns.get_loc("households")

hh_index = 0
assigned_people = 0

print("Assigning households to buildings by district ...")
for district_id, district_buildings in eligible_buildings.groupby("DISTRICT_ID"):
    if pd.isna(district_id):
        continue
    district_target_pop = districts.loc[
        districts["DISTRICT_ID"] == district_id, "pop2021"
    ].iloc[0]
    district_people = 0
    building_indices = list(district_buildings.index)
    n_buildings = len(building_indices)

    est_hh_needed = math.ceil(district_target_pop / avg_hh_size)
    base_per_building = max(min_hh, est_hh_needed // n_buildings)
    extra_count = est_hh_needed % n_buildings

    for i, pos in enumerate(building_indices):
        if hh_index >= total_households:
            break
        btype = eligible_buildings.at[pos, "type"] if "type" in eligible_buildings.columns else None
        cap = min(building_cap(btype), max_hh)
        n = min(base_per_building + (1 if i < extra_count else 0), cap)
        selected = []
        for _ in range(n):
            if hh_index >= total_households:
                break
            hh = households[hh_index]
            selected.append(hh)
            district_people += len(hh["members"])
            assigned_people += len(hh["members"])
            hh_index += 1
        eligible_buildings.iat[pos, col_pos] = selected

    if district_people < district_target_pop:
        for pos in building_indices:
            if hh_index >= total_households or district_people >= district_target_pop:
                break
            btype = eligible_buildings.at[pos, "type"] if "type" in eligible_buildings.columns else None
            cap = min(building_cap(btype), max_hh)
            current = eligible_buildings.iat[pos, col_pos]
            if len(current) < cap:
                hh = households[hh_index]
                current.append(hh)
                eligible_buildings.iat[pos, col_pos] = current
                district_people += len(hh["members"])
                assigned_people += len(hh["members"])
                hh_index += 1

print(f"  Placed {hh_index:,}/{total_households:,} households "
      f"({100 * hh_index / total_households:.1f}%).")
print(f"  Assigned {assigned_people:,}/{total_people:,} people "
      f"({100 * assigned_people / total_people:.1f}%).")

# ── Write geojson (osm_id, GEIT_ID, DISTRICT_ID, households, geometry) ─────
out = eligible_buildings[["osm_id", "GEIT_ID", "DISTRICT_ID", "geometry", "households"]].copy()
out["households"] = out["households"].apply(json.dumps)
out = gpd.GeoDataFrame(out, geometry="geometry", crs=eligible_buildings.crs)
out.to_file(OUT_GEOJSON, driver="GeoJSON")
print(f"Saved {OUT_GEOJSON}  ({len(out):,} building features)")

n_hh_check = sum(len(json.loads(h)) for h in out["households"])
n_people_check = sum(
    len(hh.get("members", [])) for h in out["households"] for hh in json.loads(h)
)
print(f"Sanity check: {n_hh_check:,} households / {n_people_check:,} people in output geojson.")
