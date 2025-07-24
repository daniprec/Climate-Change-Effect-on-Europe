import datetime as dt
import os

import cdsapi
import geopandas as gpd
import pandas as pd
import xarray as xr

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
            # "grid": [0.1, 0.1],  # 0.1° grid resolution
            "data_format": data_format,
            "download_format": "unarchived",
            "nocache": "123",  # to avoid caching the file
        },
        fout,
    )

    return fout


def download_era5_single_year_month(
    path_geojson: str = "./data/regions.geojson",
    fin: str = "./data/era5-land",
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
    fin : str
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
        year=year, month=month, folder=fin, data_format="grib"
    )
    era5 = xr.open_dataset(era5_file, engine="cfgrib")
    temp = era5["t2m"]

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
    # HOURLY -> DAILY -> WEEKLY (mean)
    # ------------------------------------------------------------------ #
    # Average through the day (average all "step")
    samp_day = samp.mean(dim="step", skipna=True)
    # Resample to weekly means, using the specified week label
    samp_week = samp_day.resample(time=week_label).mean(skipna=True)

    # ------------------------------------------------------------------ #
    # Long-format DataFrame
    # ------------------------------------------------------------------ #
    df_long = (
        samp_week.to_dataframe(name="temperature")  # point | time | temperature
        .reset_index()
        .merge(
            gdf[["NUTS_ID"]].reset_index().rename(columns={"index": "point"}),
            on="point",
            how="left",
        )
    )

    iso = df_long["time"].dt.isocalendar()  # ISO year/week/day
    df_long["year"] = iso.year
    df_long["week"] = iso.week

    # We can now close the xarray dataset to free resources
    era5.close()

    return df_long[["NUTS_ID", "year", "week", "temperature"]]


def download_era5_land_reanalysis(
    path_geojson: str = "./data/regions.geojson",
    fin: str = "./data/era5-land",
    year_min: int = 2000,
    year_max: int | None = None,
    week_label: str = "W-SUN",  # choose "W-MON", "W-SUN"…
) -> pd.DataFrame:
    """Download ERA5-Land reanalysis data for multiple years and return a DataFrame. This function has to perform a for loop over each year and month,
    as the CDS API does not support downloading multiple months or years in a single request.

    Parameters
    ----------
    path_geojson : str
        GeoJSON with polygons and a `NUTS_ID` column.
    fin : str
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
        for month in range(1, 13):
            # Download and process each month
            df = download_era5_single_year_month(
                path_geojson=path_geojson,
                fin=fin,
                year=year,
                month=month,
                week_label=week_label,
            )
            ls_df.append(df)
    df_all = pd.concat(ls_df, ignore_index=True)
    return df_all


def main(start: int = 2000):
    """
    Main function to execute the ERA5 reanalysis to DataFrame conversion.
    """
    # End year is current year (use date)
    current_year = dt.datetime.now().year
    # Download all files first
    for year in range(start, current_year + 1):
        for month in range(1, 13):
            download_era5_file(year=year, month=month)


if __name__ == "__main__":
    main()
