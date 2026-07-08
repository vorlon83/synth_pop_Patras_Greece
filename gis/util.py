import geopandas as gpd
import pandas as pd
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# WGS84 (lat/lon): 4326
# Greek: 2100
EPSG = 4326

'''
Mapping used for education levels of schools when processing school GIS
'''
education_level_map = {
    "νηπιαγωγειο": 0,
    "δημοτικο": 1,
    "γυμνασιο": 2,
    "λυκειο": 3,
}

# TODO: check if bbox is ok
def gpd_load_wrapper(SRC, bbox=None):
    '''
    Loads gdf with an optional bbox parameter.

    Sets all gdf to project desired CRS
    '''
    gdf = gpd.read_file(SRC, bbox=bbox)
    gdf = gdf.to_crs(EPSG)
    return gdf


def explore_gdf(gdf, output_file=False):
    '''
    Prints basic information about the gpd df.

    Optionally saves gpd df to file (without geometry to avoid non-human readable text)
    '''
    print(gdf.columns)
    
    print(gdf.crs)

    head_10 = gdf.head(10).drop(columns=['geometry'])
    print(head_10)

    if output_file:
        gdf_without_geometry = gdf.drop(columns=['geometry'])
        with open('output.txt', 'w', encoding='utf-8', errors='replace') as f:
            f.write(gdf_without_geometry.to_string(index=False))

def load_districts():
    '''
    Loads all Patras districts. 
    
    Aligns CRS and then joins the gpd dataframes into one.
    '''
    folder = os.path.join(ROOT, 'data', 'PATRAS_GIS_DATA', 'GEITONIES_PATRAS')
    
    # Find all .shp files
    shp_files = [f for f in os.listdir(folder) 
             if f.endswith('.shp') and f != 'geitonies_08.shp'] # geitonies will cause duplicate entries
    gdfs = []
    
    for shp in shp_files:
        path = os.path.join(folder, shp)
        try:
            temporary_gdf = gpd.read_file(path, encoding='cp1253')
            gdfs.append(temporary_gdf)
            
        except Exception as e:
            print(f"Failed to load district {shp}: {e}")
    
    # Combine
    combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
    combined_gdf = combined_gdf.to_crs(EPSG)

    # Add unique DISTRICT_ID
    # !!!: GEIT_ID isn't unique so can't be used to identify each district
    combined_gdf["DISTRICT_ID"] = range(0, len(combined_gdf))
    
    return combined_gdf