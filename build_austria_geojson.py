import os
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import Polygon


def download_file(url, local_path):
    """
    Downloads a file from `url` to `local_path`.
    If it already exists, we skip re-downloading.
    """
    if os.path.exists(local_path):
        print(f"[INFO] {local_path} already exists, skipping download.")
        return
    print(f"[INFO] Downloading {url} ...")
    r = requests.get(url)
    r.raise_for_status()
    with open(local_path, "wb") as f:
        f.write(r.content)
    print(f"[INFO] Saved to {local_path}")


def extract_zip(zip_path, extract_to):
    """
    Extracts all contents of a zip file to the specified directory.
    """
    print(f"[INFO] Extracting {zip_path} into {extract_to} ...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)
    print("[INFO] Extraction complete.")


def line_to_polygon(geom: gpd.GeoSeries) -> gpd.GeoSeries:
    """
    Given a Shapely geometry, convert a LineString or MultiLineString
    to a Polygon by ensuring the coordinate sequence is closed.

    If the geometry is already a Polygon, it's returned unchanged.
    """
    if geom.geom_type == "Polygon":
        # Already a polygon; nothing to do.
        return geom
    elif geom.geom_type == "LineString":
        coords = list(geom.coords)
        # Ensure the ring is closed.
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        return Polygon(coords)
    elif geom.geom_type == "MultiLineString":
        # For a MultiLineString, one common approach is to merge all parts into a single set of coordinates.
        # This assumes all parts belong to one boundary.
        merged_coords = []
        for line in geom.geoms:
            merged_coords.extend(list(line.coords))
        # Sometimes the parts might not be ordered correctly. One may need to sort or reassemble the ring.
        # Here we use the simplest approach: assume the parts come in order.
        if merged_coords[0] != merged_coords[-1]:
            merged_coords.append(merged_coords[0])
        return Polygon(merged_coords)
    else:
        # For any other geometry type, return it unchanged.
        return geom


def build_austria_geojson():
    """
    Downloads the Eurostat NUTS boundaries shapefile,
    filters to Austria's NUTS-3 regions (district level),
    downloads Eurostat mortality data,
    processes and renames year columns,
    merges the mortality data to the boundaries via NUTS_ID,
    and writes a final GeoJSON.
    """

    # ------------------------------------------------------
    # Download Eurostat NUTS Boundaries Shapefile
    # ------------------------------------------------------
    # The following URL points to the 2024 reference dataset.
    # Download a low resolution (options are 1:1, 1:3, 1:10, 1:20, 1:60)
    nuts_url = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/download/ref-nuts-2024-01m.shp.zip"
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)

    zip_path = os.path.join(data_dir, "ref-nuts.shp.zip")
    shapefile_dir = os.path.join(data_dir, "ref-nuts")
    download_file(nuts_url, zip_path)
    if not os.path.exists(shapefile_dir):
        os.makedirs(shapefile_dir, exist_ok=True)
        extract_zip(zip_path, shapefile_dir)

    # Some shp files are still zipped as zip files, so we need to check for that.
    # If the zip file is not extracted, we need to extract it.
    for f in os.listdir(shapefile_dir):
        if f.endswith(".zip"):
            zip_file_path = os.path.join(shapefile_dir, f)
            extract_zip(zip_file_path, shapefile_dir)
            os.remove(zip_file_path)
            print(f"[INFO] Removed zip file: {zip_file_path}")

    # Identify the .shp file in the extracted folder
    shp_files = [f for f in os.listdir(shapefile_dir) if f.endswith(".shp")]
    if not shp_files:
        raise FileNotFoundError("No .shp file found in the extracted NUTS folder.")
    shp_path = os.path.join(shapefile_dir, shp_files[0])
    print(f"[INFO] Reading NUTS shapefile: {shp_path}")
    gdf_nuts = gpd.read_file(shp_path)
    print(f"[INFO] Loaded {len(gdf_nuts)} NUTS features.")

    # The codes are contained in the csv columns "NUTS_ID" and "NUTS_NAME"
    # We will use the column "LEFT_NUTS3" from the gdf_nuts dataframe
    # to filter the NUTS-3 regions in Austria.
    df_codes = pd.read_csv(
        os.path.join(shapefile_dir, "NUTS_AT_2024.csv"),
        sep=",",
        encoding="utf-8",
    )
    # Rename the column
    gdf_nuts = gdf_nuts.rename({"LEFT_NUTS3": "NUTS_ID"}, axis=1)
    print(f"[INFO] Loaded {len(df_codes)} NUTS codes.")
    gdf_nuts = gdf_nuts.merge(df_codes, on="NUTS_ID")
    print("[INFO] Merged NUTS codes into GeoDataFrame.")
    # Create the "CNTR_CODE" column for filtering
    gdf_nuts["CNTR_CODE"] = gdf_nuts["NUTS_ID"].str[:2]

    # Filter to Austria only (CNTR_CODE == "AT") and level 3 regions:
    gdf_at = gdf_nuts[
        (gdf_nuts["CNTR_CODE"] == "AT") & (gdf_nuts["LEVL_CODE"] == 3)
    ].copy()
    print(f"[INFO] Filtered to {len(gdf_at)} NUTS-3 regions in Austria.")

    # Next, to convert from LineString to Polygon, we need to close the polygons
    # by adding the first point to the end of the list of points.
    # This is done automatically by GeoPandas when converting to Polygon.
    # However, we need to ensure that the geometry is of type Polygon.
    gdf_at["geometry"] = gdf_at["geometry"].apply(line_to_polygon)
    # The coordinates are in EPSG:3035 (ETRS89 / LAEA Europe)
    # We need to convert them to EPSG:4326 (WGS 84) for GeoJSON
    gdf_at = gdf_at.to_crs(epsg=4326)
    print("[INFO] Converted coordinates to EPSG:4326 (WGS 84).")

    # ------------------------------------------------------
    # Merge Mortality Data with Austrian Municipalities
    # ------------------------------------------------------

    # Create new columns named "mortality_YYYY" for each year in the mortality data
    # and fill them with random values for demonstration purposes.
    for year in range(2012, 2024):
        gdf_at[f"mortality_{year}"] = np.random.randint(0, 15, size=len(gdf_at))

    # Create the "name" field for the GeoJSON from a suitable column, e.g., "NUTS_NAME"
    # (The actual column name may vary; check the shapefile attributes.)
    if "NUTS_NAME" in gdf_at.columns:
        gdf_at["name"] = gdf_at["NUTS_NAME"].str.strip()
    else:
        gdf_at["name"] = gdf_at["NUTS_ID"].str.strip()

    # Choose the columns for the output; keep "name", "geometry", and all mortality columns.
    mortality_columns = [col for col in gdf_at.columns if col.startswith("mortality_")]
    columns_to_keep = ["name", "geometry"] + mortality_columns
    merged_gdf = gdf_at[columns_to_keep]

    # ------------------------------------------------------
    # Export Final GeoJSON
    # ------------------------------------------------------
    output_geojson = os.path.join(data_dir, "austria.geojson")
    merged_gdf.to_file(output_geojson, driver="GeoJSON")
    print(f"[INFO] Successfully wrote {len(merged_gdf)} features to {output_geojson}!")

    # -------------------------------------------------------
    # Cleanup (optional)
    # -------------------------------------------------------
    # os.remove(zip_path)
    for f in os.listdir(shapefile_dir):
        os.remove(os.path.join(shapefile_dir, f))
    os.rmdir(shapefile_dir)
    print(f"[INFO] Cleaned up temporary files in {data_dir}.")


def main():
    build_austria_geojson()


if __name__ == "__main__":
    main()
