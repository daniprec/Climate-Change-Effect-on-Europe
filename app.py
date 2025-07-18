import os

import geopandas as gpd
import pandas as pd
from flask import Flask, Response, jsonify, render_template, request

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

META_MAP = {
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
df = pd.read_csv(CSV_MAP["EU"]).round(1)
min_year = df["year"].min()
max_year = df["year"].max()


@app.route("/")
def map():
    # Render the base HTML page; the page can load data via AJAX.
    meta = META_MAP["EU"]
    return render_template(
        "map.html",
        min_year=int(min_year),
        max_year=int(max_year),
        center_lat=meta["center"][0],
        center_lon=meta["center"][1],
        zoom=meta["zoom"],
        map_id="EU",
        ls_map_ids=list(CSV_MAP.keys()),
    )


@app.route("/questions")
def questions():
    return render_template("questions.html")


@app.get("/api/data")
def api_data():
    map_id = request.args.get("map_id", "EU").upper()
    year = request.args.get("year", "2023")
    week = request.args.get("week", "1")
    metric = request.args.get("metric", "mortality_rate")

    # Check if the requested map_id is valid
    if map_id not in CSV_MAP:
        return jsonify({"error": "Invalid map_id specified"}), 400

    # Extract the DataFrame for the specified region, week and year
    df = pd.read_csv(CSV_MAP[map_id]).round(1)
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
    meta = META_MAP.get(iso)
    return (
        jsonify(bbox=meta["bbox"], center=meta["center"], zoom=meta["zoom"])
        if meta
        else (jsonify(error="No bbox"), 404)
    )


@app.route("/api/data/ts")
def app_data_time_series():
    map_id = request.args.get("map_id", "EU").upper()
    metric = request.args.get("metric", "mortality_rate")
    nuts_id = request.args.get("nuts_id", "AT")

    # Check if the requested map_id is valid
    if map_id not in CSV_MAP:
        return jsonify({"error": "Invalid map_id specified"}), 400

    # Load the DataFrame for the specified region
    df = pd.read_csv(CSV_MAP[map_id]).round(1)

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


@app.route("/api/data/download")
def download_data():
    map_id = request.args.get("map_id", "EU").upper()
    nuts_id = request.args.get("nuts_id", None).upper()
    metric1 = request.args.get("metric", "mortality_rate")
    metric2 = request.args.get("metric2", None)

    # Load the DataFrame for the specified map_id
    if map_id not in CSV_MAP:
        return jsonify({"error": "Invalid map_id specified"}), 400
    df = pd.read_csv(CSV_MAP[map_id])

    # Validate metrics
    if metric1 not in df.columns:
        return jsonify({"error": f"No data available for metric '{metric1}'"}), 400
    else:
        metrics = [metric1]
    if metric2 not in df.columns:
        metric2 = None
    else:
        metrics.append(metric2)

    # Prepare the DataFrame for download
    df = df[["NUTS_ID", "year", "week"] + metrics]
    # Mask NUTS_ID if specified
    if nuts_id != "EU":
        df = df[df["NUTS_ID"] == nuts_id]
    # Drop rows that have NaN values in both metrics
    df = df.dropna(subset=metrics, how="all")
    # If the DataFrame is empty, return an error
    if df.empty:
        return jsonify({"error": "No data available for the specified criteria"}), 400
    # Convert DataFrame to CSV
    csv_data = df.to_csv(index=False)
    # Return the CSV data as a response
    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{nuts_id}_data.csv"'
    )
    return response


if __name__ == "__main__":
    app.run(debug=True)
