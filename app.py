import os

import geopandas as gpd
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Construct the absolute path to the GeoJSON file
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "europe_regions.geojson")
DATA_AUSTRIA_PATH = os.path.join(BASE_DIR, "data", "austria.geojson")

# Load your multi-year GeoJSON data once at startup
gdf = gpd.read_file(DATA_PATH)
gdf_austria = gpd.read_file(DATA_AUSTRIA_PATH)
dict_gdf = {
    "Europe": gdf,
    "Austria": gdf_austria,
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
    metric = request.args.get("metric", "mortality")

    property_name = f"{metric}_{year}"

    # Check if the requested region is valid
    if region not in dict_gdf:
        return jsonify({"error": "Invalid region specified"}), 400

    # Create a copy so we don't modify the original
    gdf_year = dict_gdf[region].copy()

    # Check if the requested year is valid
    if property_name not in gdf_year.columns:
        return jsonify({"error": f"No data available for year {year}"}), 400

    # Assign the column value for the selected year to a common property.
    gdf_year[metric] = gdf_year[property_name]
    print(gdf_year[metric].min(), gdf_year[metric].max())

    # Return the processed GeoJSON.
    return gdf_year.to_json()


if __name__ == "__main__":
    app.run(debug=True)
