import sys
import os
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from shapely.geometry import Point

_GIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_GIS_DIR)
sys.path.insert(0, _GIS_DIR)
import util

# Load city boundaries from shapefile
city_gdf = gpd.read_file(os.path.join(ROOT, 'data', 'SCHOOLS', 'gr003l_Patrai.shp'))

# Load schools from CSV
schools_df = pd.read_csv(os.path.join(ROOT, 'data', 'SCHOOLS', 'sxoleia.csv'))

print("City boundaries shapefile info:")
print(f"Number of city polygons: {len(city_gdf)}")
print(f"Columns: {city_gdf.columns.tolist()}")
print(f"CRS: {city_gdf.crs}")
print("\n" + "="*50 + "\n")

print("Schools CSV info:")
print(f"Number of schools: {len(schools_df)}")
print(f"Columns: {schools_df.columns.tolist()}")
print("\nFirst 10 schools:")
print(schools_df.head(10))
print("\n" + "="*50 + "\n")

# Filter schools that have valid coordinates
schools_with_coords = schools_df.dropna(subset=['lat', 'long'])
# Additional filtering for valid coordinate ranges
schools_with_coords = schools_with_coords[
    (schools_with_coords['lat'] >= -90) & (schools_with_coords['lat'] <= 90) &
    (schools_with_coords['long'] >= -180) & (schools_with_coords['long'] <= 180) &
    (schools_with_coords['lat'] != 0) & (schools_with_coords['long'] != 0)  # Remove 0,0 coordinates
]

print(f"Schools with valid coordinates: {len(schools_with_coords)}")

# Create GeoDataFrame for schools
schools_geometry = [Point(xy) for xy in zip(schools_with_coords['long'], schools_with_coords['lat'])]
schools_gdf = gpd.GeoDataFrame(schools_with_coords, geometry=schools_geometry, crs="EPSG:4326")

# Handle CRS conversion for city boundaries
if city_gdf.crs is None:
    print("City boundaries have no CRS defined. Assuming it's in a local coordinate system.")
    city_gdf.set_crs("EPSG:2100", inplace=True)

# Convert city boundaries to WGS84 for consistency with schools
try:
    city_gdf = city_gdf.to_crs("EPSG:4326")
    print("Successfully converted city boundaries to WGS84")
except Exception as e:
    print(f"Error converting CRS: {e}")

# TODO: more professional bbox
# Filter schools to only those within the Patras area (approximate bounds)
patras_bounds = schools_gdf[
    (schools_gdf['long'] >= 21.69) & (schools_gdf['long'] <= 21.77) &
    (schools_gdf['lat'] >= 38.2) & (schools_gdf['lat'] <= 38.29)
]

print(f"Schools in Patras area: {len(patras_bounds)}")

# Export Patras schools as a shapefile (name, lat, long)
if len(patras_bounds) > 0:
    export_gdf = patras_bounds.copy()

    # 'onoma' to 'name' column
    if 'name' not in export_gdf.columns:
        if 'onoma' in export_gdf.columns:
            export_gdf = export_gdf.rename(columns={'onoma': 'name'})
        else:
            # Fallback: create a simple name from index
            export_gdf['name'] = export_gdf.index.astype(str)

    export_gdf['edu_level'] = None

    # Education level based on keyword match
    for keyword, level in util.education_level_map.items():
        mask = export_gdf['name'].str.contains(keyword, case=False, na=False)
        export_gdf.loc[mask, 'edu_level'] = level

    # TODO: if no keyword, don't add building since it's not school

    # Keep only requested fields plus geometry
    keep_columns = [col for col in ['name', 'lat', 'long', 'edu_level', 'geometry'] if col in export_gdf.columns]
    export_gdf = export_gdf[keep_columns]

    output_path = os.path.join(ROOT, 'data', 'SCHOOLS', 'patras_schools.shp')
    export_gdf.to_file(output_path, driver='ESRI Shapefile', encoding='utf-8')
    print(f"Saved Patras schools shapefile to {output_path} with {len(export_gdf)} features")
else:
    print("No Patras schools found; skipping shapefile export.")