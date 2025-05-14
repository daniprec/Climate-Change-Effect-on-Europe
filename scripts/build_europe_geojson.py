import os
import sys
import zipfile

import geopandas as gpd
import pandas as pd
import requests

sys.path.append(".")
from utils.eurostat import download_eurostat_data

ISO_A2_COUNTRY_CODES = {
    "France": "FR",
    "Germany": "DE",
    "United Kingdom": "GB",
    "Norway": "NO",
    "Kosovo": "XK",
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


def build_europe_geojson():
    """
    Downloads Natural Earth data for Admin 0 countries,
    downloads Eurostat mortality data,
    filters to European countries, merges with mortality data,
    and saves as a final GeoJSON file.
    """

    # ------------------------------------------------------
    # 1. Download Natural Earth Admin 0 Shapefile (1:50m)
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

    # ------------------------------------------------------
    # 2. Download Eurostat data
    # ------------------------------------------------------
    print("[INFO] Reading Eurostat data into Pandas...")
    df = download_eurostat_data(dataset="tps00029")

    # DEATH_NR = Deaths - number
    # GDEATHRT_THSP = Crude death rate - per thousand persons
    # Choose "GDEATHRT_THSP" as the indicator
    df = df[df["indic_de"] == "GDEATHRT_THSP"].copy()
    # We can drop the "indic_de" and "freq" columns now
    df.drop(columns=["indic_de", "freq"], inplace=True)
    print(df["geo"])

    # Next columns typically contain data for various years, e.g. "2020 ", "2021 "
    # 3.2 Identify those year columns
    year_cols = [col for col in df.columns if col.strip().isdigit()]
    if not year_cols:
        raise ValueError(
            "No year columns found in the downloaded TSV. The structure may have changed."
        )

    # Rename the year columns to "mortality_YYYY"
    for col_old in year_cols:
        year = col_old.strip()
        col = f"mortality_{year}"
        df.rename(columns={col_old: col}, inplace=True)
        # Convert the column to numeric (ignore the letters if any)
        df[col] = pd.to_numeric(df[col], errors="coerce")
        # Replace NaNs with -1
        df[col].fillna(-1, inplace=True)

    print("[INFO] Final parsed DataFrame sample:")
    print(df.head(10))

    # ------------------------------------------------------
    # 3. Match Eurostat "geo" codes to Natural Earth country names
    # ------------------------------------------------------
    # We will do a left join on ISO_A2 = geo
    gdf_europe["ISO_A2"] = gdf_europe["ISO_A2"].str.strip()
    # Some countries are missing ISO_A2 codes, e.g. "FR" for France
    # We will use their "NAME_EN" to match them, using the ISO_A2_COUNTRY_CODES dict
    # to fill in the missing codes
    for country, iso_code in ISO_A2_COUNTRY_CODES.items():
        gdf_europe.loc[gdf_europe["NAME_EN"] == country, "ISO_A2"] = iso_code
    print(gdf_europe[["NAME_EN", "ISO_A2"]])

    merged_gdf = gdf_europe.merge(df, left_on="ISO_A2", right_on="geo", how="left")

    # Create the "name" column for GeoJSON
    merged_gdf["name"] = merged_gdf["NAME_EN"].str.strip()

    # Choose the columns we want to keep in the final GeoJSON
    columns_to_keep = [
        "name",
        "geometry",
    ] + [col for col in merged_gdf.columns if col.startswith("mortality_")]
    merged_gdf = merged_gdf[columns_to_keep]

    # ------------------------------------------------------
    # 4. Export final GeoJSON
    # ------------------------------------------------------
    output_geojson = os.path.join(data_dir, "europe_regions.geojson")
    merged_gdf.to_file(output_geojson, driver="GeoJSON")
    print(
        f"[INFO] Successfully wrote {len(merged_gdf)} European features to {output_geojson}!"
    )

    # -------------------------------------------------------
    # 5. Cleanup (optional)
    # -------------------------------------------------------
    os.remove(zip_path)
    for f in os.listdir(shapefile_dir):
        os.remove(os.path.join(shapefile_dir, f))
    os.rmdir(shapefile_dir)
    print(f"[INFO] Cleaned up temporary files in {data_dir}.")


def main():
    build_europe_geojson()


if __name__ == "__main__":
    main()
