import datetime as dt
from datetime import datetime
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
import xarray as xr
from pyproj import CRS, Transformer


def load_eurocordex_data(fin: str = "./data", year: int = 2025) -> xr.Dataset:
    """
    Load the Euro-CORDEX data from the specified folder.
    The data is expected to be in NetCDF format.

    Parameters
    ----------
    fin : str
        Path to the folder containing the NetCDF files
    year : int
        Target year to find the closest matching file

    Returns
    -------
    xr.Dataset
        The loaded dataset from the closest matching file
    """
    # Define the folder containing the data
    folder = Path(fin)

    # The file names end with "YYYYMM-YYYYMM.nc" where YYYY is the year
    # and MM is the month. The first element is the start date and the second
    # element is the end date.
    # We want to select the file with the year closest to the specified year.
    # Get the list of files in the folder
    files = list(folder.glob("*.nc"))

    if not files:
        raise FileNotFoundError(f"No NetCDF files found in {folder}")

    # Extract the start and end dates from the file names
    file_dates = []
    for file in files:
        # Extract the date part from the filename (remove .nc extension)
        date_str = file.stem.split("_")[-1]
        try:
            # Split into start and end dates
            start_date, end_date = date_str.split("-")
            # Convert to datetime objects
            start_dt = datetime.strptime(start_date, "%Y%m")
            end_dt = datetime.strptime(end_date, "%Y%m")
            # Calculate the middle year of the date range
            mid_year = (start_dt.year + end_dt.year) / 2
            file_dates.append((file, mid_year))
        except ValueError:
            print(f"Warning: Skipping file {file} due to invalid date format")
            continue

    if not file_dates:
        raise ValueError("No valid date formats found in filenames")

    # Find the file with the closest year to the target
    closest_file = min(file_dates, key=lambda x: abs(x[1] - year))[0]

    # Open the file with xarray
    ds = xr.open_dataset(closest_file)

    return ds


def plot_eurocordex_data(
    ds: xr.Dataset, date: str = "2028-01-01"
) -> tuple[plt.Figure, plt.Axes]:
    """
    Plot the Euro-CORDEX data.
    The data is expected to be in a rotated pole projection.
    """
    # Select the surface air temperature variable
    tas = ds["tas"]

    # Pick the date closest to the specified date
    # Convert the date to a datetime object
    ts_target = dt.datetime.strptime(date, "%Y-%m-%d")
    # Find the closest time index to the target date
    ts = tas.sel(time=ts_target, method="nearest").time.values
    tas_at_t0 = tas.sel(time=ts)

    # The dataset is in a rotated pole projection
    # Get the rotated pole attributes
    dict_rotated_pole = ds.rotated_pole.attrs
    lat = dict_rotated_pole["grid_north_pole_latitude"]
    lon = dict_rotated_pole["grid_north_pole_longitude"]

    # Create a rotated pole projection
    # The pole latitude and longitude are in degrees
    rp = ccrs.RotatedPole(
        pole_longitude=lon,
        pole_latitude=lat,
        globe=ccrs.Globe(semimajor_axis=6370000, semiminor_axis=6370000),
    )

    # Create a figure with a rotated pole projection
    fig = plt.figure(figsize=(10, 6), dpi=300)
    ax = fig.add_subplot(1, 1, 1, projection=rp)
    ax.coastlines("50m", linewidth=0.8)

    # Plot the temperature with lower and upper bounds (in Kelvin)
    tas_at_t0.plot(ax=ax, transform=rp, cmap="coolwarm", vmin=235, vmax=320)

    # Add title
    ax.set_title(f"Surface Air Temperature ({ts.astype('datetime64[M]').astype(str)})")

    # Tight layout to avoid overlapping labels
    plt.tight_layout()

    return fig, ax


import pandas as pd
import xarray as xr


def cordex_tas_to_dataframe_per_region(
    path_geojson: str = "./data/regions.geojson",
    fin: str = "../data",
    year: int = 2025,
    week_label: str = "W-MON",  # choose "W-MON", "W-SUN"…
):
    """
    Return a DataFrame with columns NUTS_ID, year, week, temperature (°C)
    where temperature is the ISO-week mean of CORDEX tas sampled at each
    region's centroid.

    Parameters
    ----------
    path_geojson : str
        GeoJSON with polygons and a `NUTS_ID` column.
    fin : str
        Folder or file pattern understood by `load_eurocordex_data`.
    year : int
        Year to open from the CORDEX archive.
    week_label : str
        Pandas/xarray resample code (default 'W-MON' = ISO weeks ending Monday).
    """
    # ------------------------------------------------------------------ #
    # 1.  Region centroids
    # ------------------------------------------------------------------ #
    gdf = gpd.read_file(path_geojson).set_crs(4326)

    centroids = gdf.to_crs(3035).geometry.centroid.to_crs(
        4326
    )  # metric CRS for a trustworthy centroid
    gdf["lon"] = centroids.x
    gdf["lat"] = centroids.y

    # ------------------------------------------------------------------ #
    # 2.  Load CORDEX tas  (monthly)  → °C
    # ------------------------------------------------------------------ #
    cor = load_eurocordex_data(fin=fin, year=year)  # user-supplied loader
    tas = cor["tas"] - 273.15  # Kelvin → Celsius

    # ------------------------------------------------------------------ #
    # 3.  Transform lon/lat → rotated-pole grid coords
    # ------------------------------------------------------------------ #
    tfm = Transformer.from_crs(
        CRS.from_epsg(4326),
        CRS.from_cf(cor.rotated_pole.attrs),
        always_xy=True,
    )
    rlon, rlat = tfm.transform(gdf["lon"].values, gdf["lat"].values)

    # ------------------------------------------------------------------ #
    # 4.  Sample tas at each centroid  (dims: point × time)
    # ------------------------------------------------------------------ #
    samp = tas.interp(
        rlon=xr.DataArray(rlon, dims="point"),
        rlat=xr.DataArray(rlat, dims="point"),
        method="nearest",
    ).transpose("point", "time")

    # ------------------------------------------------------------------ #
    # 5.  MONTHLY -> DAILY (linear) -> WEEKLY (mean)
    # ------------------------------------------------------------------ #
    # build a full daily index spanning the monthly series
    # We grab the first day of the first year and the last day of the last year
    # to ensure we cover the entire range of the time series.
    start_year = pd.to_datetime(tas.time.values[0]).replace(day=1, month=1, hour=0)
    end_year = pd.to_datetime(tas.time.values[-1]).replace(day=31, month=12, hour=23)
    daily_index = pd.date_range(
        start=start_year,
        end=end_year,
        freq="1D",
    )

    samp_daily = samp.interp(time=daily_index)  # linear time interp
    samp_week = samp_daily.resample(time=week_label).mean()  # weekly mean

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
