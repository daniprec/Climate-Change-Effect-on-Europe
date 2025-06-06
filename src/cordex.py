from datetime import datetime
from pathlib import Path

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
