import os
import sys
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import pandas as pd
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


def build_austria_geojson(spatial_geojson: str = "./data/regions.geojson") -> None:
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

    # Load the shapefile
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
    gdf_at = gdf_at[["NUTS_ID", "name", "geometry"]]
    print("[INFO] Converted coordinates to EPSG:4326 (WGS 84).")

    # Check if the spatial data is available
    if os.path.exists(spatial_geojson):
        gdf_spatial = gpd.read_file(spatial_geojson)
        # Stack both datasets, and in case of duplicated NUTS_ID, keep ours
        gdf_spatial = pd.concat([gdf_at, gdf_spatial], ignore_index=True)
        gdf_spatial = gdf_spatial.drop_duplicates(subset=["NUTS_ID"])
    else:
        gdf_spatial = gdf_at

    # Store the NUTS-3 data in the spatial data
    gdf_spatial.sort_values(by="NUTS_ID", inplace=True)
    gdf_spatial.to_file(spatial_geojson, driver="GeoJSON")

    # Clean up temporary files
    for f in os.listdir(shapefile_dir):
        os.remove(os.path.join(shapefile_dir, f))
    os.rmdir(shapefile_dir)
    print(f"[INFO] Cleaned up temporary files in {data_dir}.")

    # ------------------------------------------------------
    # Mortality - Download Eurostat data
    # ------------------------------------------------------
    print("[INFO] Reading Eurostat data into Pandas...")

    # Mortality data
    df_demomwk = download_eurostat_data(dataset="demo_r_mwk3_t")
    df_demomwk.rename(columns={"geo": "NUTS_ID"}, inplace=True)

    # Match the NUTS_ID with the GeoDataFrame
    df_demomwk = df_demomwk[df_demomwk["NUTS_ID"].isin(gdf_at["NUTS_ID"])].copy()

    # The column names are like "2015-W01"
    # We will turn the dataframe into a long format:
    # Columns will be "NUTS_ID", "year", "week", "mortality"
    # Drop columns "freq" and "unit" first
    df_demomwk.drop(columns=["freq", "unit"], inplace=True)
    df_demomwk = df_demomwk.melt(
        id_vars=["NUTS_ID"],
        var_name="year_week",
        value_name="mortality",
    )
    # Extract year and week from "year_week"
    df_demomwk["year"] = df_demomwk["year_week"].str[:4].astype(int)
    df_demomwk["week"] = df_demomwk["year_week"].str[6:].astype(int)
    # Drop the "year_week" column
    df_demomwk.drop(columns=["year_week"], inplace=True)
    # Drop NaNs in "mortality"
    df_demomwk.dropna(subset=["mortality"], inplace=True)
    # Sort column order: NUTS_ID, year, week, mortality
    df_demomwk = df_demomwk[["NUTS_ID", "year", "week", "mortality"]]

    # ------------------------------------------------------
    # Merge with Population Density Data
    # ------------------------------------------------------

    # Download population density data
    df_popdensity = download_eurostat_data(dataset="demo_r_d3dens")
    df_popdensity.rename(columns={"geo": "NUTS_ID"}, inplace=True)
    df_popdensity.drop(columns=["freq", "unit"], inplace=True)
    # Filter for Austria's NUTS-3 regions
    df_popdensity = df_popdensity[
        df_popdensity["NUTS_ID"].isin(gdf_at["NUTS_ID"])
    ].copy()
    # Melt the DataFrame to long format
    df_popdensity = df_popdensity.melt(
        id_vars=["NUTS_ID"],
        var_name="year",
        value_name="population_density",
    )
    # Drop NaNs in "population_density"
    df_popdensity.dropna(subset=["population_density"], inplace=True)
    # Convert year to integer
    df_popdensity["year"] = df_popdensity["year"].astype(int)
    # Sort column order: NUTS_ID, year, population_density
    df_popdensity = df_popdensity[["NUTS_ID", "year", "population_density"]]

    # Add the population density to the mortality data, for each week present in the mortality data
    df = df_demomwk.merge(
        df_popdensity,
        on=["NUTS_ID", "year"],
        how="left",
    )

    # ----------------------------------------
    # Population - Download Eurostat data
    # ----------------------------------------
    print("[INFO] Reading Eurostat population data into Pandas...")
    # Population data
    df_pop = download_eurostat_data(dataset="demo_r_pjanaggr3")
    # Filter for total sex and age class
    mask_sex = df_pop["sex"] == "Total"
    mask_age = df_pop["age"] == "Total"
    df_pop = df_pop[mask_sex & mask_age].copy()
    df_pop.rename(columns={"geo": "NUTS_ID"}, inplace=True)
    df_pop.drop(columns=["freq", "unit", "sex", "age"], inplace=True)

    # The column names are like "2020"
    # We will turn the dataframe into a long format:
    # Columns will be "name", "year", "population"
    df_pop = df_pop.melt(
        id_vars=["NUTS_ID"],
        var_name="year",
        value_name="population",
    )

    # Convert "year" to integer
    df_pop["year"] = df_pop["year"].astype(int)

    # Merge population data with all prior data
    df = df.merge(df_pop, on=["NUTS_ID", "year"], how="left")

    # Use the mortality and population to calculate the mortality rate
    df["mortality_rate"] = 100000 * df["mortality"] / df["population"]

    # ------------------------------------------------------
    # Store the dataframe
    # ------------------------------------------------------

    df.sort_values(by=["NUTS_ID", "year", "week"], inplace=True)
    output_csv = os.path.join(data_dir, "austria.csv")
    df.to_csv(output_csv, index=False)
    print(f"[INFO] Successfully wrote {len(df)} records to {output_csv}!")


if __name__ == "__main__":
    build_austria_geojson()
