from flask import Flask, render_template, jsonify
import json
import os

app = Flask(__name__)

# Load the dummy geojson file at startup
data_path = os.path.join(app.root_path, "data", "europe_regions.geojson")
with open(data_path, "r", encoding="utf-8") as f:
    europe_geojson = json.load(f)


@app.route("/")
def index():
    # Renders the map page
    return render_template("index.html")


@app.route("/api/data")
def get_data():
    # Returns the dummy geojson data as JSON
    return jsonify(europe_geojson)


if __name__ == "__main__":
    # Run in debug mode for development
    app.run(debug=True)
