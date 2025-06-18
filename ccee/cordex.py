import datetime as dt
from datetime import datetime
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import xarray as xr


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
