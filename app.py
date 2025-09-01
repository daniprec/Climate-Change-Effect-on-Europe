import os

import geopandas as gpd
import pandas as pd
from flask import Flask, Response, jsonify, render_template, request

from ccee.rr_curve import fit_dlnm_weekly, generate_rr_curve

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
    sex = request.args.get("sex", "T")
    age = request.args.get("age", "T")

    # Check if the requested map_id is valid
    if map_id not in CSV_MAP:
        return jsonify({"error": "Invalid map_id specified"}), 400

    # Define the column name we are calling
    if (sex == "T") and (age == "T"):
        metric_full = metric
    else:
        metric_full = f"{metric}_{sex}_{age}"

    print(metric_full)

    # Check if the metric exists in the CSV
    df_check = pd.read_csv(CSV_MAP[map_id], nrows=0)
    if metric_full not in df_check.columns:
        metric_full = metric
    elif metric not in df_check.columns:
        return jsonify({"error": f"Metric '{metric}' not found in data"}), 400

    # Extract the DataFrame for the specified region, week and year
    df = pd.read_csv(CSV_MAP[map_id]).round(1)
    df = df[(df["year"] == int(year)) & (df["week"] == int(week))]

    # Check if the requested information exists in the DataFrame
    if df.empty:
        return jsonify({"error": f"No data available for {year}-W{week}"}), 400

    # If the metric_full is not the same as metric, rename the column
    # We do this because the map takes the column name from the "metric" parameter
    if metric != metric_full:
        df[metric] = df[metric_full]
        df = df.drop(columns=[metric_full])
    # TODO: Do the same for all other metrics in the future

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
    metric2 = request.args.get("metric2", None)
    # "null" means no second metric
    metric2 = metric2 if metric2 != "null" else None
    nuts_id = request.args.get("nuts_id", "AT")
    sex = request.args.get("sex", "T")
    age = request.args.get("age", "T")

    # Check if the requested map_id is valid
    if map_id not in CSV_MAP:
        return jsonify({"error": "Invalid map_id specified"}), 400

    # Define the column name we are calling
    if (sex == "T") and (age == "T"):
        metric_full = metric
        metric2_full = metric2
    else:
        metric_full = f"{metric}_{sex}_{age}"
        metric2_full = f"{metric2}_{sex}_{age}" if metric2 else None

    # Check if the metric exists in the CSV
    df_check = pd.read_csv(CSV_MAP[map_id], nrows=0)
    if metric_full not in df_check.columns:
        metric_full = metric
    elif metric not in df_check.columns:
        return jsonify({"error": f"Metric '{metric}' not found in data"}), 400
    if metric2_full and (metric2_full not in df_check.columns):
        metric2_full = metric2
    elif metric2 and (metric2 not in df_check.columns):
        return jsonify({"error": f"Metric '{metric2}' not found in data"}), 400

    # Load the DataFrame for the specified region
    usecols = ["NUTS_ID", "year", "week", metric_full]
    if metric2_full:
        usecols.append(metric2_full)
    df = pd.read_csv(CSV_MAP[map_id], usecols=usecols).round(1)

    # Filter by NUTS_ID
    df = df[df["NUTS_ID"] == nuts_id]

    columns = ["year", "week", metric_full]
    rename = {metric_full: "value"}
    if metric2:
        columns.append(metric2_full)
        rename[metric2_full] = "value2"

    # Prepare structured JSON
    time_series_data = (
        df[columns]
        .sort_values(["year", "week"])
        .rename(columns=rename)
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
    sex = request.args.get("sex", "T")
    age = request.args.get("age", "T")

    # Load the DataFrame for the specified map_id
    if map_id not in CSV_MAP:
        return jsonify({"error": "Invalid map_id specified"}), 400

    # Define the column name we are calling
    if (sex == "T") and (age == "T"):
        metric1_full = metric1
        metric2_full = metric2
    else:
        metric1_full = f"{metric1}_{sex}_{age}"
        metric2_full = f"{metric2}_{sex}_{age}" if metric2 else None

    # Check if the metric exists in the CSV
    df_check = pd.read_csv(CSV_MAP[map_id], nrows=0)
    if metric1_full not in df_check.columns:
        metric1_full = metric1
    elif metric1 not in df_check.columns:
        return jsonify({"error": f"Metric '{metric1}' not found in data"}), 400
    if metric2_full and (metric2_full not in df_check.columns):
        metric2_full = metric2
    elif metric2 and (metric2 not in df_check.columns):
        return jsonify({"error": f"Metric '{metric2}' not found in data"}), 400

    usecols = ["NUTS_ID", "year", "week", metric1_full]
    if metric2:
        usecols.append(metric2)
    df = pd.read_csv(CSV_MAP[map_id], usecols=usecols).round(1)

    # Validate metrics
    metrics = [metric1_full, metric2_full] if metric2_full else [metric1_full]

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


@app.route("/api/data/rr_curve")
def rr_curve():
    """
    Generate a JSON response for the relative risk curve.
    This is a placeholder function that returns static data.
    """
    map_id = request.args.get("map_id", "EU").upper()
    nuts_id = request.args.get("nuts_id", None).upper()
    metric1 = request.args.get("metric", "mortality_rate")
    metric2 = request.args.get("metric2", None)
    sex = request.args.get("sex", "T")
    age = request.args.get("age", "T")

    # Load the DataFrame for the specified map_id
    if map_id not in CSV_MAP:
        return jsonify({"error": "Invalid map_id specified"}), 400

    # Define the column name we are calling
    if (sex == "T") and (age == "T"):
        metric1_full = metric1
        metric2_full = metric2
    else:
        metric1_full = f"{metric1}_{sex}_{age}"
        metric2_full = f"{metric2}_{sex}_{age}" if metric2 else None

    # Check if the metric exists in the CSV
    df_check = pd.read_csv(CSV_MAP[map_id], nrows=0)
    if metric1_full not in df_check.columns:
        metric1_full = metric1
    elif metric1 not in df_check.columns:
        return jsonify({"error": f"Metric '{metric1}' not found in data"}), 400
    if metric2_full and (metric2_full not in df_check.columns):
        metric2_full = metric2
    elif metric2 and (metric2 not in df_check.columns):
        return jsonify({"error": f"Metric '{metric2}' not found in data"}), 400

    usecols = ["NUTS_ID", "year", "week", metric1_full]
    if metric2_full:
        usecols.append(metric2_full)
    df = pd.read_csv(CSV_MAP[map_id], usecols=usecols).round(1)

    # Choose a code
    df = df[df["NUTS_ID"] == nuts_id]

    # Drop rows with NaNs in x or y columns
    df.dropna(subset=[metric2_full, metric1_full], inplace=True)

    # Create column "date" from "year" and "week"
    df["date"] = pd.to_datetime(
        df["year"].astype(str) + df["week"].astype(str) + "0", format="%Y%W%w"
    )

    # Set date as index
    df.set_index("date", inplace=True)

    # Fit the DLNM model
    model, spline_df, spline_spec = fit_dlnm_weekly(df, metric2_full, metric1_full)

    # Plot the relative risk curve
    dict_curve = generate_rr_curve(model, spline_spec, max_lag=5)

    # Return the relative risk curve as JSON
    return jsonify(
        {
            "nuts_id": nuts_id,
            "metric1": metric1_full,
            "metric2": metric2_full,
            **dict_curve,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
