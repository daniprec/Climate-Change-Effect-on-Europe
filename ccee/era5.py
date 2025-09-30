import datetime as dt
import os

import cdsapi
import geopandas as gpd
import pandas as pd
import requests
import xarray as xr

from ccee._io_utils import write_dataset_json, write_partitioned_parquet

DICT_FILE_TERMINATION = {
    "grib": ".grib",
    "netcdf": ".nc",
}


def download_era5_file(
    year: int = 1981,
    month: int = 1,
    data_format: str = "grib",
    folder: str = "./data/era5-land",
) -> str:
    """
    Download ERA5-Land reanalysis data for a specified period and region.
    A single year and month has to be downloaded at a time, as the CDS API does not support downloading multiple months or years in a single request.
    Source: https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land?tab=form
    Reference: Loïc Duffar, https://github.com/loicduffar/ERA5-tools

    Parameters
    ----------
    year : int
        Year for the data download (default is 1981).
    month : int
        Month for the data download (default is 1).
    data_format : str
        Format of the downloaded data, either 'grib' or 'netcdf'. Default is the
        format recommended by the Copernicus Climate Data Store (CDS), which is 'grib'.
    folder : str
        Folder where the downloaded file will be saved (default is './data').

    Returns
    -------
    str
        Path to the downloaded file.
    """

    # Name of the downloaded file
    fout = f"ERA5-Land-{year:04d}-{month:02d}{DICT_FILE_TERMINATION[data_format]}"
    fout = os.path.join(folder, fout)

    if not os.path.exists(folder):
        os.makedirs(folder)
    elif os.path.exists(fout):
        # If the file already exists, return its path and skip the download
        return fout

    # AREA to extract
    lon_min, lat_min, lon_max, lat_max = [-9.66, 35.37, 49.5, 71.55]  # EUROPA

    # Download
    start_day = 1
    end_day = 31
    days = [str(start_day + i).zfill(2) for i in range(end_day - start_day + 1)]

    c = cdsapi.Client()

    c.retrieve(
        "reanalysis-era5-land",
        # See the CDS API documentation for more options.
        {
            "product_type": "reanalysis",
            "variable": [
                "2m_temperature",
                "specific_humidity",
            ],  # Variables to download.
            "year": f"{year:04d}",  # Year in YYYY format
            "month": f"{month:02d}",  # Month in MM format
            "day": days,  # All days of the month
            "time": [f"{h:02d}:00" for h in range(24)],  # All hours
            "area": [lat_min, lon_min, lat_max, lon_max],
            # "grid": [0.25, 0.25],  # 0.25° grid resolution
            "data_format": data_format,
            "download_format": "unarchived",
            "nocache": "123",  # to avoid caching the file
        },
        fout,
    )

    return fout


def download_era5_target_year_target_month(
    path_geojson: str = "./data/regions.geojson",
    path_data_raw: str = "./data/era5-land",
    year: int = 2025,
    month: int = 1,
    week_label: str = "W-SUN",  # choose "W-MON", "W-SUN"…
) -> pd.DataFrame:
    """
    Return a DataFrame with weekly mean 2m temperature for each region in the
    provided GeoJSON file, sampled from ERA5-Land reanalysis data.
    A single year and month has to be downloaded at a time, as the CDS API does not support downloading multiple months or years in a single request.

    Parameters
    ----------
    path_geojson : str
        GeoJSON with polygons and a `NUTS_ID` column.
    path_data_raw : str
        Folder or file pattern understood by `download_era5_file`.
    year : int
        Year to open from the ERA5-Land reanalysis data (default 2025).
    week_label : str
        Pandas/xarray resample code (default 'W-SUN' = ISO weeks ending Sunday).

    Returns
    -------
    pd.DataFrame
        DataFrame containing weekly mean 2m temperature for each region in the
        provided GeoJSON file, sampled from ERA5-Land reanalysis data.
    """
    # ------------------------------------------------------------------ #
    # Region centroids
    # ------------------------------------------------------------------ #
    gdf = gpd.read_file(path_geojson).set_crs(4326)

    # metric CRS for a trustworthy centroid
    centroids = gdf.to_crs(3035).geometry.centroid.to_crs(4326)
    gdf["lon"] = centroids.x
    gdf["lat"] = centroids.y

    # ------------------------------------------------------------------ #
    # Load ERA5 2m-temp  (daily)  -> °C
    # ------------------------------------------------------------------ #
    era5_file = download_era5_file(
        year=year, month=month, folder=path_data_raw, data_format="grib"
    )
    era5 = xr.open_dataset(era5_file, engine="cfgrib", decode_timedelta=True)
    temp = era5["t2m"]

    # We can now close the xarray dataset to free resources
    era5.close()

    # Coordinates:
    # time: day
    # step: hour (0, 1, ..., 23)

    # Temperature is in Kelvin, convert to Celsius
    temp = temp - 273.15  # Convert from Kelvin to Celsius

    # ------------------------------------------------------------------ #
    # Sample tas at each centroid  (dims: point x time x step)
    # ------------------------------------------------------------------ #
    samp = temp.interp(
        longitude=xr.DataArray(gdf["lon"], dims="point"),
        latitude=xr.DataArray(gdf["lat"], dims="point"),
        method="nearest",
    ).transpose("point", "time", "step")

    # ------------------------------------------------------------------ #
    # HOURLY -> WEEKLY (percentiles 5, 50, 95)
    # ------------------------------------------------------------------ #
    # Stack "time" and "step" into a single datetime dimension
    samp_stacked = samp.stack(datetime=("time", "step"))

    # Convert the stacked index to actual datetimes
    new_datetime = pd.to_datetime(samp_stacked["time"].values) + pd.to_timedelta(
        samp_stacked["step"].values, unit="h"
    )
    samp_stacked = samp_stacked.drop_vars(["time", "step"]).assign_coords(
        datetime=new_datetime
    )

    # Now resample the "datetime" dimension to weekly and compute quantiles
    samp_week = samp_stacked.resample(datetime=week_label).quantile(
        q=[0.05, 0.5, 0.95], dim="datetime", skipna=True
    )

    # Transform to long format DataFrame
    df_long = (
        samp_week.to_dataframe(name="temperature")
        # point | datetime | quantile | temperature
        .reset_index()
        .merge(
            gdf[["NUTS_ID"]].reset_index().rename(columns={"index": "point"}),
            on="point",
            how="left",
        )
    )
    # Quantile as "qXX"
    df_long["stat"] = df_long["quantile"].apply(lambda x: f"q{x * 100:02.0f}")

    iso = df_long["datetime"].dt.isocalendar()  # ISO year/week/day
    df_long["year"] = iso.year
    df_long["week"] = iso.week

    # Turn datetime into date (week starting date)
    df_long["date"] = df_long["datetime"].dt.to_period(week_label).dt.start_time

    # Assign level: EU for NUTS-ID with 2 letters, else country code
    df_long["level"] = df_long["NUTS_ID"].apply(
        lambda x: "EU" if len(x) == 2 else x[:2]
    )

    # Rename columns
    df_long = df_long.rename(columns={"temperature": "value"})

    return df_long[
        [
            "NUTS_ID",
            "date",
            "year",
            "week",
            "stat",
            "level",
            "value",
        ]
    ].reset_index(drop=True)


def download_era5_target_year_all_months(
    path_geojson: str = "./data/regions.geojson",
    path_data_raw: str = "./data/era5-land",
    year: int = 2025,
    week_label: str = "W-SUN",
) -> pd.DataFrame:
    """Download ERA5-Land reanalysis data for a specific year and return a DataFrame.
    This function has to perform a for loop over each month,
    as the CDS API does not support downloading multiple months or years in a single request.

    Parameters
    ----------
    path_geojson : str
        GeoJSON with polygons and a `NUTS_ID` column.
    path_data_raw : str
        Folder or file pattern understood by `download_era5_file`.
    year : int
        Year to open from the ERA5-Land reanalysis data (default 2025).
    week_label : str
        Pandas/xarray resample code (default 'W-SUN' = ISO weeks ending Sunday).

    Returns
    -------
    pd.DataFrame
        DataFrame containing weekly mean 2m temperature for each region in the
        provided GeoJSON file, sampled from ERA5-Land reanalysis data.
    """
    # Initialize an empty list to store DataFrames for each month
    ls_df: list[pd.DataFrame] = []
    # Iterate over each month in the specified year
    for month in range(1, 13):
        # If this date is in the future, skip it
        if dt.datetime(year, month, 1) > dt.datetime.now():
            continue
        # Else, we download and process the data
        try:
            # Download and process each month
            df = download_era5_target_year_target_month(
                path_geojson=path_geojson,
                path_data_raw=path_data_raw,
                year=year,
                month=month,
                week_label=week_label,
            )
        except requests.exceptions.HTTPError as e:
            print(
                f"Error downloading data for {year}-{month:02d}: {e}. Skipping this month."
            )
            continue
        ls_df.append(df)
        print(f"[INFO] Downloaded and processed data for {year}-{month:02d}")
    df_all = pd.concat(ls_df, ignore_index=True)
    return df_all


def download_era5_land_reanalysis(
    path_geojson: str = "./data/regions.geojson",
    path_data_raw: str = "./data/era5-land",
    year_min: int = 2000,
    year_max: int | None = None,
    week_label: str = "W-SUN",  # choose "W-MON", "W-SUN"…
) -> pd.DataFrame:
    """Download ERA5-Land reanalysis data for multiple years and return a DataFrame.
    This function has to perform a for loop over each year and month,
    as the CDS API does not support downloading multiple months or years in a single request.

    Parameters
    ----------
    path_geojson : str
        GeoJSON with polygons and a `NUTS_ID` column.
    path_data_raw : str
        Folder or file pattern understood by `download_era5_file`.
    year_min : int
        Minimum year to open from the ERA5-Land reanalysis data (default 1980).
    year_max : int
        Maximum year to open from the ERA5-Land reanalysis data (default current year).
    week_label : str
        Pandas/xarray resample code (default 'W-SUN' = ISO weeks ending Sunday).

    Returns
    -------
    pd.DataFrame
        DataFrame containing weekly mean 2m temperature for each region in the
        provided GeoJSON file, sampled from ERA5-Land reanalysis data.
    """
    # Use current year if not specified
    year_max = year_max or dt.datetime.now().year
    # Initialize an empty list to store DataFrames for each month
    ls_df: list[pd.DataFrame] = []
    # Iterate over each year and month in the specified range
    for year in range(year_min, year_max + 1):
        try:
            # Download and process each month
            df = download_era5_target_year_all_months(
                path_geojson=path_geojson,
                path_data_raw=path_data_raw,
                year=year,
                week_label=week_label,
            )
        except requests.exceptions.HTTPError as e:
            print(f"Error downloading data for {year}: {e}. Skipping this year.")
            continue
        ls_df.append(df)
        print(f"[INFO] Downloaded and processed data for {year}")
    df_all = pd.concat(ls_df, ignore_index=True)
    return df_all


def era5_land_reanalysis_to_parquet(
    path_geojson: str = "data/regions.geojson",
    path_data_raw: str = "data/era5-land",
    path_processed: str = "data/processed/era5/temp/parquet",
    path_json: str = "data/processed/era5/temp/dataset.json",
):
    """
    Main function to execute the ERA5 reanalysis to DataFrame conversion.
    """
    year_min = 1980
    year_max = dt.datetime.now().year

    # Initialize variables to avoid unbound errors
    stats = []
    levels = []
    date_min = ""
    date_max = ""

    # Iterate over each year and month in the specified range
    for year in range(year_min, year_max + 1):
        # Download and process each month
        df_long = download_era5_target_year_all_months(
            path_geojson=path_geojson,
            path_data_raw=path_data_raw,
            year=year,
        )

        write_partitioned_parquet(
            df_long.sort_values(["NUTS_ID", "date"]),
            base_dir=path_processed,
            partition_cols=["stat", "level", "year"],
        )
        print(f"[INFO] Downloaded and processed data for {year}")

        if year == year_min:
            # Keep the metadata from the first year only
            date_min: str = df_long["date"].min().date().isoformat()
            stats: list[str] = sorted(df_long["stat"].unique().tolist())
            levels: list[str] = sorted(df_long["level"].unique().tolist())

        # Update date_max each year
        date_max: str = df_long["date"].max().date().isoformat()

    meta = {
        "dataset_id": "era5-temp-weekly",
        "source": "ERA5-Land",
        "producer_script": "scripts/era5.py",
        "variable": "temp",
        "stats": stats,
        "levels": levels,
        "frequency": "weekly",
        "units": "degC",
        "time_coverage": {
            "start": date_min,
            "end": date_max,
        },
        "partitions": ["stat", "level", "year"],
        "path_glob": "data/processed/era5/temp/parquet/**.parquet",
        "schema": {
            "fields": [
                "NUTS_ID",
                "date",
                "year",
                "week",
                "stat",
                "level",
                "value",
            ],
            "types": [
                "string",
                "date",
                "int16",
                "int8",
                "string",
                "string",
                "float32",
            ],
        },
        "display": {"label": "Temperature", "unit_symbol": "°C"},
        "created_at": dt.datetime.today().isoformat(timespec="seconds") + "Z",
        "version": "1.0.0",
    }

    write_dataset_json(meta, path_json)


if __name__ == "__main__":
    era5_land_reanalysis_to_parquet()
