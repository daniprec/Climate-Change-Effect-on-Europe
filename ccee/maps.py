import os
import zipfile

import geopandas as gpd
import requests
from shapely.geometry import Polygon

DICT_NUTS = {"GB": "UK"}


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
