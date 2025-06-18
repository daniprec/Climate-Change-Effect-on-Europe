import datetime as dt
from pathlib import Path

import cartopy.crs as ccrs
import imageio
import matplotlib.pyplot as plt
import xarray as xr

from ccee.cordex import load_eurocordex_data


def plot_eurocordex_data(
    ds: xr.Dataset,
    date: str = "2028-01-01",
    fout: str = "output",
) -> Path:
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
    ax = plt.axes(projection=rp)
    ax.coastlines("50m", linewidth=0.8)

    # Plot the temperature with lower and upper bounds (in Kelvin)
    tas_at_t0.plot(ax=ax, transform=rp, cmap="coolwarm", vmin=235, vmax=320)

    # Add title
    ax.set_title(f"Surface Air Temperature ({ts.astype('datetime64[M]').astype(str)})")

    # Make sure the output directory exists
    folder = Path(fout)
    folder.mkdir(parents=True, exist_ok=True)

    plt.tight_layout()
    file = folder / f"tas_{ts.astype('datetime64[M]').astype(str)}.png"
    plt.savefig(file, dpi=300)

    plt.close()
    return file


def main():
    # Load the Euro-CORDEX data
    ds = load_eurocordex_data()

    ls_files = []

    # Plot the Euro-CORDEX data
    for year in range(2021, 2031):
        for month in range(1, 13):
            # Create a date string for the tenth day of the month
            # (easier to break ties when the reference is the middle of the month)
            date = f"{year}-{month:02d}-10"
            file = plot_eurocordex_data(ds, date=date)
            ls_files.append(file)

    # Sort the files by date
    ls_files = sorted(list(set(ls_files)))

    # Create a gif from the png files
    with imageio.get_writer("output/tas.gif", mode="I", loop=0) as writer:
        for filename in ls_files:
            image = imageio.imread(filename)
            writer.append_data(image)
    # Remove the png files
    for filename in ls_files:
        filename.unlink()


if __name__ == "__main__":
    main()
