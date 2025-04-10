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
    "europe": gdf,
    "austria": gdf_austria,
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
        region="europe",
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
        region="austria",
    )


@app.route("/api/mortality")
def get_mortality():
    # Get the requested year; default to 2023 if not provided
    year = request.args.get("year", "2023")
    property_name = f"mortality_{year}"
    # Check if the requested year is valid
    if property_name not in gdf.columns:
        return jsonify({"error": f"No data available for year {year}"}), 400

    region = request.args.get("region", "europe").lower()
    # Check if the requested region is valid
    if region not in dict_gdf:
        return jsonify({"error": "Invalid region specified"}), 400

    # Create a copy so we don't modify the original
    gdf_year = dict_gdf[region].copy()

    # Assign the mortality value for the selected year to a common property.
    gdf_year["mortality"] = gdf_year[property_name]

    # Return the processed GeoJSON.
    return gdf_year.to_json()


if __name__ == "__main__":
    app.run(debug=True)
