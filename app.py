import geopandas as gpd
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Load your multi-year GeoJSON data once at startup
gdf = gpd.read_file("data/europe_regions.geojson")


@app.route("/")
def index():
    # Render the base HTML page; the page can load data via AJAX.
    return render_template("index.html")


@app.route("/api/mortality")
def get_mortality():
    # Get the requested year; default to 2023 if not provided
    year = request.args.get("year", "2023")
    property_name = f"mortality_{year}"

    if property_name not in gdf.columns:
        return jsonify({"error": f"No data available for year {year}"}), 400

    # Create a copy so we don't modify the original
    gdf_year = gdf.copy()

    # Assign the mortality value for the selected year to a common property.
    gdf_year["mortality"] = gdf_year[property_name]

    # Return the processed GeoJSON.
    return gdf_year.to_json()


if __name__ == "__main__":
    app.run(debug=True)
