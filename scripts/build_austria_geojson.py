import os
import sys
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import Polygon

sys.path.append(".")
from utils.eurostat import download_eurostat_data


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
    # Download NUTS Boundaries Shapefile
    # ------------------------------------------------------
    # Source: https://github.com/roboes/at-shapefile

    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    shapefile_dir = os.path.join(data_dir, "shapefiles")

    # Download Shapefile
    bytesfile = BytesIO(
        initial_bytes=requests.get(
            url="https://data.statistik.gv.at/data/OGDEXT_NUTS_1_STATISTIK_AUSTRIA_NUTS3_20250101.zip",
            headers=None,
            timeout=5,
            verify=True,
        ).content,
    )
    with ZipFile(file=bytesfile, mode="r", compression=ZIP_DEFLATED) as zip_file:
        zip_file.extractall(path=shapefile_dir)

    # Import
    filename = os.path.join(shapefile_dir, "STATISTIK_AUSTRIA_NUTS3_20250101.shp")
    gdf_at = (
        gpd.read_file(
            filename=filename,
            layer="STATISTIK_AUSTRIA_NUTS3_20250101",
            columns=["g_id", "g_name", "geometry"],
            driver=None,
            encoding="utf-8",
        )
        # Rename columns
        .rename(columns={"g_id": "NUTS_ID", "g_name": "name"})
        # Change dtypes
        .astype(dtype={"NUTS_ID": "str"})
    )

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

    # Choose the columns for the output; keep "name", "geometry", and all mortality columns.
    mortality_columns = [col for col in gdf_at.columns if col.startswith("mortality_")]
    columns_to_keep = ["name", "geometry"] + mortality_columns

    # ------------------------------------------------------
    # Merge with Population Density Data
    # ------------------------------------------------------

    # Download population density data
    df_popdensity = download_eurostat_data(dataset="demo_r_d3dens", fmt="SDMX-CSV")
    # Rename columns
    df_popdensity = df_popdensity.rename(
        columns={
            "TIME_PERIOD": "year",
            "OBS_VALUE": "popdensity",
            "geo": "NUTS_ID",
        }
    )
    # Convert year to int
    df_popdensity["year"] = df_popdensity["year"].astype(int)
    # Choose only rows for Austria (NUTS_ID starts with "AT")
    df_popdensity = df_popdensity[df_popdensity["NUTS_ID"].str.startswith("AT")]

    for year in range(2012, 2024):
        # Filter for the current year
        df_year = df_popdensity[df_popdensity["year"] == year]
        # Rename the column to "popdensity_YYYY"
        col = f"popdensity_{year}"
        df_year = df_year.rename(columns={"popdensity": col})
        # Merge with the merged_gdf DataFrame on NUTS_ID
        gdf_at = gdf_at.merge(df_year[["NUTS_ID", col]], how="left", on="NUTS_ID")
        columns_to_keep.append(col)

    # ------------------------------------------------------
    # Export Final GeoJSON
    # ------------------------------------------------------
    merged_gdf = gdf_at[columns_to_keep]
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
