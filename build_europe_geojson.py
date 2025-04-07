import gzip
import os
import shutil
import zipfile

import geopandas as gpd
import pandas as pd
import requests


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
    # 2. Download Eurostat mortality data
    # ------------------------------------------------------
    # Eurostat mortality data
    eurostat_url = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tps00029?format=TSV&compressed=true"
    eurostat_tsv_gz = os.path.join(data_dir, "mortality.tsv.gz")
    download_file(eurostat_url, eurostat_tsv_gz)

    # We need to decompress the GZ into a .tsv file
    eurostat_tsv = os.path.join(data_dir, "mortality.tsv")
    if not os.path.exists(eurostat_tsv):
        print(f"[INFO] Decompressing {eurostat_tsv_gz} to {eurostat_tsv} ...")
        with (
            gzip.open(eurostat_tsv_gz, "rb") as gz_in,
            open(eurostat_tsv, "wb") as tsv_out,
        ):
            shutil.copyfileobj(gz_in, tsv_out)
        print("[INFO] Decompression complete.")

    # ------------------------------------------------------
    # 3. Parse the Eurostat TSV (COMPLETED STEP)
    # ------------------------------------------------------
    print("[INFO] Reading Eurostat data into Pandas...")
    df = pd.read_csv(eurostat_tsv, sep="\t", na_values=":", dtype=str)

    # The first column is something like "freq,indic_de,geo\TIME_PERIOD"
    # 3.1 Split that into separate columns
    df[["freq", "indic_de", "geo"]] = df.iloc[:, 0].str.split(",", expand=True)

    # Drop the now-redundant combined column
    df = df.iloc[:, 1:]

    # Choose "DEATH_NR" as the indicator
    df = df[df["indic_de"] == "DEATH_NR"].copy()

    # Next columns typically contain data for various years, e.g. "2020 ", "2021 "
    # 3.2 Identify those year columns
    year_cols = [col for col in df.columns if col.strip().isdigit()]
    if not year_cols:
        raise ValueError(
            "No year columns found in the downloaded TSV. The structure may have changed."
        )

    # Pick the most recent year column
    latest_year = sorted(year_cols, key=lambda x: x.strip())[-1]
    print(f"[INFO] Found year columns {year_cols}. Using {latest_year} for data.")

    # 3.3 Convert that latest year's data into a numeric column
    df["mortality_raw"] = df[latest_year].str.strip().replace(":", "-1")
    df["mortality"] = (
        pd.to_numeric(df["mortality_raw"], errors="coerce").fillna(0).astype(int)
    )

    # Keep only the geo code + the mortality
    df = df[["geo", "mortality"]]

    print("[INFO] Final parsed DataFrame sample:")
    print(df.head(10))

    # ------------------------------------------------------
    # 4. Match Eurostat "geo" codes to Natural Earth country names
    # ------------------------------------------------------
    # We will do a left join on ISO_A2 = geo
    gdf_europe["ISO_A2"] = gdf_europe["ISO_A2"].str.strip()

    merged_gdf = gdf_europe.merge(df, left_on="ISO_A2", right_on="geo", how="left")

    # If a country doesn't match, we get NaN in "mortality"
    # We will fill them with 0 for demonstration
    merged_gdf["mortality"] = merged_gdf["mortality"].fillna(0).astype(int)

    # Create the "name" column for GeoJSON
    merged_gdf["name"] = merged_gdf["NAME_EN"].str.strip()

    # ------------------------------------------------------
    # 5. Export final GeoJSON
    # ------------------------------------------------------
    output_geojson = os.path.join(data_dir, "europe_regions.geojson")
    merged_gdf.to_file(output_geojson, driver="GeoJSON")
    print(
        f"[INFO] Successfully wrote {len(merged_gdf)} European features to {output_geojson}!"
    )

    # -------------------------------------------------------
    # 6. Cleanup (optional)
    # -------------------------------------------------------
    os.remove(zip_path)
    for f in os.listdir(shapefile_dir):
        os.remove(os.path.join(shapefile_dir, f))
    os.rmdir(shapefile_dir)
    os.remove(eurostat_tsv_gz)
    os.remove(eurostat_tsv)
    print(f"[INFO] Cleaned up temporary files in {data_dir}.")


def main():
    build_europe_geojson()


if __name__ == "__main__":
    main()
