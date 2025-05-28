import os
import sys
import zipfile

import geopandas as gpd
import pandas as pd
import requests

sys.path.append(".")
from utils.eurostat import download_eurostat_data


def download_file(url: str, local_path: str) -> None:
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


def extract_zip(zip_path: str, extract_to: str) -> None:
    """
    Extracts all contents of a zip file to the specified directory.
    """
    print(f"[INFO] Extracting {zip_path} into {extract_to} ...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)
    print("[INFO] Extraction complete.")


def build_europe_geojson(spatial_geojson: str = "./data/regions.geojson"):
    """
    Downloads Natural Earth data for Admin 0 countries,
    downloads Eurostat mortality data,
    filters to European countries, merges with mortality data,
    and saves as a final GeoJSON file.
    """

    # ------------------------------------------------------
    # Download Natural Earth Admin 0 Shapefile (1:50m)
    # ------------------------------------------------------
    # Reliable NACIS CDN link for 1:50m Admin 0 Countries
    ne_url = (
        "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
    )

    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)

    zip_path = os.path.join(data_dir, "ne_50m_admin_0_countries.zip")
    shapefile_dir = os.path.join(data_dir, "ne_50m_admin_0_countries")

    download_file(ne_url, zip_path)

    if not os.path.exists(shapefile_dir):
        os.makedirs(shapefile_dir, exist_ok=True)
        extract_zip(zip_path, shapefile_dir)

    # Read the shapefile with GeoPandas
    shp_files = [f for f in os.listdir(shapefile_dir) if f.endswith(".shp")]
    if not shp_files:
        raise FileNotFoundError(
            "No .shp file found in the extracted Natural Earth folder."
        )
    shp_path = os.path.join(shapefile_dir, shp_files[0])

    print(f"[INFO] Reading shapefile: {shp_path}")
    gdf = gpd.read_file(shp_path)
    print(f"[INFO] Loaded {len(gdf)} country polygons from Natural Earth.")

    # Filter to countries in Europe
    gdf_europe = gdf[gdf["CONTINENT"] == "Europe"].copy()
    print(f"[INFO] Filtered to {len(gdf_europe)} countries in Europe (by CONTINENT).")

    # If any value in "ISO_A2" is empty, fill it with "ISO_A2_EH" (European Union)
    gdf_europe["ISO_A2"] = gdf_europe["ISO_A2"].fillna(gdf_europe["ISO_A2_EH"])

    # Filter columns and rename
    gdf_europe = gdf_europe.rename(columns={"ISO_A2": "NUTS_ID", "NAME_SORT": "name"})[
        ["NUTS_ID", "name", "geometry"]
    ]

    # Check if the spatial data is available
    if os.path.exists(spatial_geojson):
        gdf_spatial = gpd.read_file(spatial_geojson)
        # Stack both datasets, and in case of duplicated NUTS_ID, keep ours
        gdf_spatial = pd.concat([gdf_europe, gdf_spatial], ignore_index=True)
        gdf_spatial = gdf_spatial.drop_duplicates(subset=["NUTS_ID"])
    else:
        gdf_spatial = gdf_europe

    # Store the spatial data
    gdf_spatial.sort_values(by="NUTS_ID", inplace=True)
    gdf_spatial.to_file(spatial_geojson, driver="GeoJSON")

    # Clean up temporary files
    os.remove(zip_path)
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
    df_demomwk = df_demomwk[df_demomwk["NUTS_ID"].isin(gdf_europe["NUTS_ID"])].copy()

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
    # Store the dataframe
    # ------------------------------------------------------

    df = df_demomwk
    df.sort_values(by=["NUTS_ID", "year", "week"], inplace=True)
    output_csv = os.path.join(data_dir, "europe.csv")
    df.to_csv(output_csv, index=False)
    print(f"[INFO] Successfully wrote {len(df)} records to {output_csv}!")


if __name__ == "__main__":
    build_europe_geojson()
