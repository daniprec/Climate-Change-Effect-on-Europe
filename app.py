import os

import geopandas as gpd
import pandas as pd
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Construct the absolute path to the GeoJSON file
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
REGIONS_PATH = os.path.join(BASE_DIR, "data", "regions.geojson")

# Load multi-year GeoJSON data once at startup
gdf = gpd.read_file(REGIONS_PATH)
CSV_MAP = {
    "EU": os.path.join(BASE_DIR, "data", "europe.csv"),
    "AT": os.path.join(BASE_DIR, "data", "austria.csv"),
}

REGION_META = {
    "EU": {  # Europe layer
        "bbox": [[34, -25], [71, 45]],
        "center": [50, 20],
        "zoom": 4,
    },
    "AT": {  # Austria
        "bbox": [[46.358, 9.372], [49.038, 17.508]],
        "center": [47.5, 13],
        "zoom": 7,
    },
}


# Get minimum and maximum year
df = pd.read_csv(CSV_MAP["EU"])
min_year = df["year"].min()
max_year = df["year"].max()


@app.route("/")
def index():
    # Render the base HTML page; the page can load data via AJAX.
    meta = REGION_META["EU"]
    return render_template(
        "index.html",
        min_year=int(min_year),
        max_year=int(max_year),
        center_lat=meta["center"][0],
        center_lon=meta["center"][1],
        zoom=meta["zoom"],
        nuts_id="EU",
        ls_ids=list(CSV_MAP.keys()),
    )


@app.get("/api/data")
def api_data():
    region = request.args.get("region", "EU").upper()
    year = request.args.get("year", "2023")
    week = request.args.get("week", "1")
    metric = request.args.get("metric", "mortality_rate")

    # Check if the requested region is valid
    if region not in CSV_MAP:
        return jsonify({"error": "Invalid region specified"}), 400

    # Extract the DataFrame for the specified region, week and year
    df = pd.read_csv(CSV_MAP[region])
    df = df[(df["year"] == int(year)) & (df["week"] == int(week))]

    # Check if the requested information exists in the DataFrame
    if (metric not in df.columns) or (df.empty):
        return jsonify({"error": f"No data available for {year}-W{week}"}), 400

    # Match the NUTS_ID with the GeoDataFrame
    gdf_region = gdf[gdf["NUTS_ID"].isin(df["NUTS_ID"])].copy()
    # Merge the DataFrame with the GeoDataFrame
    gdf_region = gdf_region.merge(df, on="NUTS_ID", how="left")

    # Return the processed GeoJSON.
    return gdf_region.to_json()


@app.get("/api/bbox")
def api_bbox():
    iso = request.args.get("nuts_id", "EU").upper()
    meta = REGION_META.get(iso)
    return (
        jsonify(bbox=meta["bbox"], center=meta["center"], zoom=meta["zoom"])
        if meta
        else (jsonify(error="No bbox"), 404)
    )


@app.route("/api/data/ts")
def app_data_time_series():
    region = request.args.get("region", "EU").upper()
    metric = request.args.get("metric", "mortality_rate")
    nuts_id = request.args.get("nuts_id", "AT")

    # Check if the requested region is valid
    if region not in CSV_MAP:
        return jsonify({"error": "Invalid region specified"}), 400

    # Load the DataFrame for the specified region
    df = pd.read_csv(CSV_MAP[region])

    # Filter by NUTS_ID
    df = df[df["NUTS_ID"] == nuts_id]

    # Validate metric
    if metric not in df.columns:
        return jsonify({"error": f"No data available for metric '{metric}'"}), 400

    # Prepare structured JSON
    time_series_data = (
        df[["year", "week", metric]]
        .sort_values(["year", "week"])
        .rename(columns={metric: "value"})
        .dropna()
        .to_dict(orient="records")
    )

    return jsonify(
        {
            "data": time_series_data,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
