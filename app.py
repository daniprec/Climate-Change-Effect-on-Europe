import os

import geopandas as gpd
import pandas as pd
from flask import Flask, jsonify, render_template, request

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


@app.route("/")
def index():
    # Render the base HTML page; the page can load data via AJAX.
    return render_template(
        "index.html",
        min_year=2012,
        max_year=2023,
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
        min_year=2012,
        max_year=2023,
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
    metric = request.args.get("metric", "mortality")

    # Check if the requested region is valid
    if region not in dict_df:
        return jsonify({"error": "Invalid region specified"}), 400

    # Extract the DataFrame for the specified region, week and year
    df = pd.read_csv(dict_df[region])
    df = df[(df["year"] == int(year)) & (df["week"] == int(week))]

    # Check if the requested information exists in the DataFrame
    if (metric not in df.columns) or (df.empty):
        return jsonify({"error": f"No data available for {year:04d}-W{week:02d}"}), 400

    # Match the NUTS_ID with the GeoDataFrame
    gdf_region = gdf[gdf["NUTS_ID"].isin(df["NUTS_ID"])].copy()
    # Merge the DataFrame with the GeoDataFrame
    gdf_region = gdf_region.merge(df, on="NUTS_ID", how="left")

    # Print the difference between gdf and df NUTS_IDs for debugging
    # NUTS_IDS in gdf that are not in df
    missing_nuts_ids = sorted(set(gdf["NUTS_ID"]) - set(df["NUTS_ID"]))
    # NUTS_IDS in df that are not in gdf
    missing_nuts_ids_df = sorted(set(df["NUTS_ID"]) - set(gdf["NUTS_ID"]))
    print(f"Missing NUTS_IDs in DataFrame for {region}: {missing_nuts_ids_df}")
    print(f"Missing NUTS_IDs in GeoDataFrame for {region}: {missing_nuts_ids}")

    # Return the processed GeoJSON.
    return gdf_region.to_json()


if __name__ == "__main__":
    app.run(debug=True)
