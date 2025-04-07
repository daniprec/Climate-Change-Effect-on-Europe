import os
import requests
import zipfile
import pandas as pd
import geopandas as gpd


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
    filters to European countries, merges with dummy population/deaths data,
    and saves as a final GeoJSON file.
    """

    # ------------------------------------------------------
    # 1. Download Natural Earth Admin 0 Shapefile (1:50m)
    # ------------------------------------------------------
    # Official download link for 1:50m Admin 0 Countries
    # (Double-check version if it changes over time)
    ne_url = (
        "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
    )

    # We will store it locally
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)

    zip_path = os.path.join(data_dir, "ne_50m_admin_0_countries.zip")
    shapefile_dir = os.path.join(data_dir, "ne_50m_admin_0_countries")

    download_file(ne_url, zip_path)

    if not os.path.exists(shapefile_dir):
        os.makedirs(shapefile_dir, exist_ok=True)
        extract_zip(zip_path, shapefile_dir)

    # ------------------------------------------------------
    # 2. Read the shapefile using GeoPandas
    # ------------------------------------------------------
    # The shapefile name typically ends with .shp, e.g.:
    # "ne_50m_admin_0_countries.shp"
    shp_files = [f for f in os.listdir(shapefile_dir) if f.endswith(".shp")]
    if not shp_files:
        raise FileNotFoundError(
            "No .shp file found in the extracted Natural Earth folder."
        )
    shp_path = os.path.join(shapefile_dir, shp_files[0])

    print(f"[INFO] Reading shapefile: {shp_path}")
    gdf = gpd.read_file(shp_path)
    print(f"[INFO] Loaded {len(gdf)} country polygons from Natural Earth.")

    # ------------------------------------------------------
    # 3. Filter to countries in Europe
    # ------------------------------------------------------
    # Natural Earth has a field "CONTINENT", or "SUBREGION"
    # We'll keep only "Europe" or special cases. You can refine as needed.
    gdf_europe = gdf[gdf["CONTINENT"] == "Europe"].copy()
    print(f"[INFO] Filtered to {len(gdf_europe)} countries in Europe (by CONTINENT).")

    # Potentially, you can also manually add countries that are
    # transcontinental (e.g., Turkey, Russia) if you want them included.
    # For example:
    #   gdf_europe = gdf_europe.append(gdf[gdf["ADMIN"] == "Turkey"])

    # ------------------------------------------------------
    # 4. Prepare or fetch population/deaths data
    # ------------------------------------------------------
    # For demonstration, let's create a small dummy CSV of population & deaths
    # keyed by the ISO_A3 code. In practice, you'd fetch real data from
    # a reliable source (WHO, WB, etc.).
    csv_population = os.path.join(data_dir, "europe_population_deaths.csv")
    if not os.path.exists(csv_population):
        print("[INFO] Creating dummy population/deaths CSV.")
        dummy_data = {
            "NAME_EN": [
                "France",
                "Germany",
                "Spain",
                "Italy",
                "Poland",
                "Sweden",
                "Greece",
                "United Kingdom",
            ],
            "population": [
                65000000,
                83000000,
                47000000,
                60000000,
                38000000,
                10300000,
                10700000,
                67000000,
            ],
            "deaths": [1500, 2000, 1200, 1800, 1100, 900, 700, 1600],
        }
        df_dummy = pd.DataFrame(dummy_data)
        df_dummy.to_csv(csv_population, index=False)
    else:
        print("[INFO] Using existing CSV for population/deaths.")

    df_pop = pd.read_csv(csv_population)
    print("[INFO] Loaded population/deaths data:")
    print(df_pop.head())

    # ------------------------------------------------------
    # 5. Merge the population/deaths info into our GeoDataFrame
    # ------------------------------------------------------
    # Natural Earth uses "ISO_A3" for 3-letter country code
    # We will do a left join to keep all Europe's polygons
    gdf_europe_merged = gdf_europe.merge(df_pop, on="NAME_EN", how="left")
    # Rename columns for clarity
    gdf_europe_merged.rename(columns={"NAME_EN": "name"}, inplace=True)

    # Some countries won't match if not in the dummy CSV. They get NaN.
    # You can handle that if needed:
    gdf_europe_merged["population"] = gdf_europe_merged["population"].fillna(0)
    gdf_europe_merged["deaths"] = gdf_europe_merged["deaths"].fillna(0)

    # ------------------------------------------------------
    # 6. Export to GeoJSON
    # ------------------------------------------------------
    output_geojson = os.path.join(data_dir, "europe_regions.geojson")
    gdf_europe_merged.to_file(output_geojson, driver="GeoJSON")
    print(
        f"[INFO] Successfully wrote {len(gdf_europe_merged)} features to {output_geojson}!"
    )

    # -------------------------------------------------------
    # 7. Cleanup
    # -------------------------------------------------------
    # Remove the downloaded zip and extracted files
    os.remove(zip_path)
    for f in os.listdir(shapefile_dir):
        os.remove(os.path.join(shapefile_dir, f))
    os.rmdir(shapefile_dir)
    os.remove(csv_population)
    print(f"[INFO] Cleaned up temporary files in {data_dir}.")


def main():
    build_europe_geojson()


if __name__ == "__main__":
    main()
