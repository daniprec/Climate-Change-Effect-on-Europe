import os
import zipfile
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Polygon


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


def build_europe_map(
    path_data: str = "data", path_geojson: str = "./data/regions.geojson"
):
    """
    Downloads Natural Earth data for Admin 0 countries.
    """

    # ------------------------------------------------------
    # Download Natural Earth Admin 0 Shapefile (1:50m)
    # ------------------------------------------------------

    # Reliable NACIS CDN link for 1:50m Admin 0 Countries
    ne_url = (
        "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
    )

    zip_path = os.path.join(path_data, "ne_50m_admin_0_countries.zip")
    shapefile_dir = os.path.join(path_data, "ne_50m_admin_0_countries")

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
    if os.path.exists(path_geojson):
        gdf_spatial = gpd.read_file(path_geojson)
        # Stack both datasets, and in case of duplicated NUTS_ID, keep ours
        gdf_spatial = pd.concat([gdf_europe, gdf_spatial], ignore_index=True)
        gdf_spatial = gdf_spatial.drop_duplicates(subset=["NUTS_ID"])
    else:
        gdf_spatial = gdf_europe

    # Store the spatial data
    gdf_spatial.sort_values(by="NUTS_ID", inplace=True)
    gdf_spatial.to_file(path_geojson, driver="GeoJSON")

    # Clean up temporary files
    os.remove(zip_path)
    for f in os.listdir(shapefile_dir):
        os.remove(os.path.join(shapefile_dir, f))
    os.rmdir(shapefile_dir)
    print(f"[INFO] Cleaned up temporary files in {path_data}.")


def build_austria_map(
    path_data: str = "data", path_geojson: str = "./data/regions.geojson"
):
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

    shapefile_dir = os.path.join(path_data, "shapefiles")

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
    if os.path.exists(path_geojson):
        gdf_spatial = gpd.read_file(path_geojson)
        # Stack both datasets, and in case of duplicated NUTS_ID, keep ours
        gdf_spatial = pd.concat([gdf_at, gdf_spatial], ignore_index=True)
        gdf_spatial = gdf_spatial.drop_duplicates(subset=["NUTS_ID"])
    else:
        gdf_spatial = gdf_at

    # Store the NUTS-3 data in the spatial data
    gdf_spatial.sort_values(by="NUTS_ID", inplace=True)
    gdf_spatial.to_file(path_geojson, driver="GeoJSON")

    # Clean up temporary files
    for f in os.listdir(shapefile_dir):
        os.remove(os.path.join(shapefile_dir, f))
    os.rmdir(shapefile_dir)
    print(f"[INFO] Cleaned up temporary files in {path_data}.")


def main(path_data: str = "data", path_geojson: str = "./data/regions.geojson"):
    os.makedirs(path_data, exist_ok=True)
    build_europe_map(path_data, path_geojson)
    build_austria_map(path_data, path_geojson)


if __name__ == "__main__":
    main()
