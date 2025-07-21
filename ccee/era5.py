import os

import cdsapi
import geopandas as gpd
import xarray as xr

DICT_FILE_TERMINATION = {
    "grib": ".grib",
    "netcdf": ".nc",
}


def download_era5_file(
    year: int = 1981,
    month: int = 1,
    data_format: str = "grid",
    folder: str = "./data",
    variable: str = "2m_temperature",
) -> str:
    """
    Download ERA5-Land reanalysis data for a specified period and region.
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
    variable : str
        Variable to download, default is '2m_temperature'. Other options include
        'total_precipitation', 'surface_pressure', etc. Check the CDS documentation
        for available variables.

    Returns
    -------
    str
        Path to the downloaded file.
    """

    # https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land?tab=form

    # Name of the downloaded file
    downloaded_file = f"ERA5-Land-hourly{DICT_FILE_TERMINATION[data_format]}"

    # AREA to extract
    lon_min, lat_min, lon_max, lat_max = [-9.66, 35.37, 49.5, 71.55]  # EUROPA

    # Download
    downloaded_file = os.path.join(folder, downloaded_file)
    start_day = 1
    end_day = 31
    days = [str(start_day + i).zfill(2) for i in range(end_day - start_day + 1)]

    c = cdsapi.Client()

    c.retrieve(
        "reanalysis-era5-land",
        {
            "product_type": "reanalysis",
            "variable": variable,
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
        downloaded_file,
    )

    return downloaded_file


def era5_reanalysis_to_dataframe_per_region(
    path_geojson: str = "./data/regions.geojson",
    fin: str = "./data",
    year: int = 2025,
    week_label: str = "W-SUN",  # choose "W-MON", "W-SUN"…
):
    """
    Return a DataFrame with weekly mean 2m temperature for each region in the
    provided GeoJSON file, sampled from ERA5-Land reanalysis data.

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
    """
    # ------------------------------------------------------------------ #
    # 1.  Region centroids
    # ------------------------------------------------------------------ #
    gdf = gpd.read_file(path_geojson).set_crs(4326)

    # metric CRS for a trustworthy centroid
    centroids = gdf.to_crs(3035).geometry.centroid.to_crs(4326)
    gdf["lon"] = centroids.x
    gdf["lat"] = centroids.y

    # ------------------------------------------------------------------ #
    # 2.  Load ERA5 2m-temp  (daily)  -> °C
    # ------------------------------------------------------------------ #
    era5_file = download_era5_file(year=year, folder=fin, data_format="grib")
    era5 = xr.open_dataset(era5_file, engine="cfgrib")
    temp = era5["t2m"]

    # ------------------------------------------------------------------ #
    # 3.  Sample tas at each centroid  (dims: point × time)
    # ------------------------------------------------------------------ #
    samp = temp.interp(
        rlon=xr.DataArray(gdf["lon"], dims="point"),
        rlat=xr.DataArray(gdf["lat"], dims="point"),
        method="nearest",
    ).transpose("point", "time")

    # ------------------------------------------------------------------ #
    # 4.  DAILY -> WEEKLY (mean)
    # ------------------------------------------------------------------ #
    # Resample to weekly means, using the specified week label
    samp_week = samp.resample(time=week_label).mean()

    # ------------------------------------------------------------------ #
    # 6.  Long-format DataFrame
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

    return df_long[["NUTS_ID", "year", "week", "temperature"]]


def main(year: int = 2025):
    """
    Main function to execute the ERA5 reanalysis to DataFrame conversion.
    """
    df = era5_reanalysis_to_dataframe_per_region(year=year)
    print(df.head())


if __name__ == "__main__":
    main()
