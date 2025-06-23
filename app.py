import os

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

# Construct the absolute path to the GeoJSON file
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
REGIONS_PATH = os.path.join(BASE_DIR, "data", "regions.geojson")

# Load your multi-year GeoJSON data once at startup
gdf = gpd.read_file(REGIONS_PATH)
dict_df = {
    "Europe": os.path.join(BASE_DIR, "data", "europe.csv"),
    "Austria": os.path.join(BASE_DIR, "data", "austria.csv"),
}

# Get minimum and maximum year
df = pd.read_csv(dict_df["Europe"])
min_year = df["year"].min()
max_year = df["year"].max()


@app.route("/")
def index():
    # Render the base HTML page; the page can load data via AJAX.
    return render_template(
        "index.html",
        min_year=min_year,
        max_year=max_year,
        center_lat=50,
        center_lon=5,
        zoom=4,
        region="Europe",
    )


@app.route("/austria")
def index_austria():
    # Render the country-specific HTML page; the page can load data via AJAX.
    return render_template(
        "index.html",
        min_year=min_year,
        max_year=max_year,
        center_lat=47.5,
        center_lon=13,
        zoom=7,
        region="Austria",
    )


@app.get("/api/data")
def api_data():
    region = request.args.get("region", "europe")
    year = request.args.get("year", "2023")
    week = request.args.get("week", "1")
    metric = request.args.get("metric", "mortality_rate")

    # Check if the requested region is valid
    if region not in dict_df:
        return jsonify({"error": "Invalid region specified"}), 400

    # Extract the DataFrame for the specified region, week and year
    df = pd.read_csv(dict_df[region])
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


@app.route("/api/data/ts")
def app_data_time_series():
    region = request.args.get("region", "europe")
    metric = request.args.get("metric", "mortality_rate")
    nuts_id = request.args.get("nuts_id", "AT")

    # Check if the requested region is valid
    if region not in dict_df:
        return jsonify({"error": "Invalid region specified"}), 400

    # Load the DataFrame for the specified region
    df = pd.read_csv(dict_df[region])

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
