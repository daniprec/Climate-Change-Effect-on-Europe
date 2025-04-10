import os
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

NUTS3 = {
    "AT111": "Mittelburgenland",
    "AT112": "Nordburgenland",
    "AT113": "Südburgenland",
    "AT121": "Mostviertel-Eisenwurzen",
    "AT122": "Niederösterreich-Süd",
    "AT123": "Sankt Pölten",
    "AT124": "Waldviertel",
    "AT125": "Weinviertel",
    "AT126": "Wiener Umland/Nordteil",
    "AT127": "Wiener Umland/Südteil",
}


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
    # The following URL points to the 2021 reference dataset at 1:1M scale.
    nuts_url = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/download/ref-nuts-2021-01m.shp.zip"
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)

    zip_path = os.path.join(data_dir, "ref-nuts-2021-01m.shp.zip")
    shapefile_dir = os.path.join(data_dir, "ref-nuts-2021-01m")
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

    # The codes are contained in the csv "NUTS_RG_BN_01M_2021.csv"
    # columns "NUTS_CODE" and "NUTS_BN_ID"
    # We will use the column "NUTS_BN_ID" from the gdf_nuts dataframe
    # to filter the NUTS-3 regions in Austria.
    df_codes = pd.read_csv(
        os.path.join(shapefile_dir, "NUTS_RG_BN_01M_2021.csv"),
        sep=",",
        encoding="utf-8",
    )
    print(f"[INFO] Loaded {len(df_codes)} NUTS codes.")
    gdf_nuts = gdf_nuts.merge(
        df_codes, right_on="NUTS_BN_CODE", left_on="NUTS_BN_ID", how="left"
    )
    print("[INFO] Merged NUTS codes into GeoDataFrame.")
    # Create the "CNTR_CODE" column for filtering
    gdf_nuts["CNTR_CODE"] = gdf_nuts["NUTS_CODE"].str[:2]

    # Filter to Austria only (CNTR_CODE == "AT") and level 3 regions:
    gdf_at = gdf_nuts[
        (gdf_nuts["CNTR_CODE"] == "AT") & (gdf_nuts["LEVL_CODE"] == 3)
    ].copy()
    print(f"[INFO] Filtered to {len(gdf_at)} NUTS-3 regions in Austria.")

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
        # Fallback: use the NUTS_ID as name if NUTS_NAME is unavailable.
        gdf_at["name"] = gdf_at["NUTS_CODE"].apply(
            lambda code: NUTS3.get(code, code)  # Use NUTS3 mapping if available
        )
    # Choose the columns for the output; keep "name", "geometry", and all mortality columns.
    mortality_columns = [col for col in gdf_at.columns if col.startswith("mortality_")]
    columns_to_keep = ["name", "geometry"] + mortality_columns
    merged_gdf = gdf_at[columns_to_keep]

    # ------------------------------------------------------
    # Export Final GeoJSON
    # ------------------------------------------------------
    output_geojson = os.path.join(data_dir, "austria_municipalities.geojson")
    merged_gdf.to_file(output_geojson, driver="GeoJSON")
    print(f"[INFO] Successfully wrote {len(merged_gdf)} features to {output_geojson}!")

    # -------------------------------------------------------
    # Cleanup (optional)
    # -------------------------------------------------------
    os.remove(zip_path)
    for f in os.listdir(shapefile_dir):
        os.remove(os.path.join(shapefile_dir, f))
    os.rmdir(shapefile_dir)
    print(f"[INFO] Cleaned up temporary files in {data_dir}.")


def main():
    build_austria_geojson()


if __name__ == "__main__":
    main()
