import os
import zipfile

import cdsapi
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from pyproj import CRS, Transformer


def download_cordex_data():
    dataset = "projections-cordex-domains-single-levels"
    request = {
        "domain": "europe",
        "experiment": "rcp_4_5",
        "horizontal_resolution": "0_11_degree_x_0_11_degree",
        "temporal_resolution": "daily_mean",
        "variable": ["2m_air_temperature"],
        "gcm_model": "mpi_m_mpi_esm_lr",
        "rcm_model": "clmcom_clm_cclm4_8_17",
        "ensemble_member": "r1i1p1",
        "start_year": ["2046"],
        "end_year": ["2050"],
    }

    client = cdsapi.Client()
    client.retrieve(dataset, request).download()

    # Unzip the downloaded file
    file_zip = "b723a83d8bb5dc479b58a3a337cba40a.zip"

    with zipfile.ZipFile(file_zip, "r") as zip_ref:
        zip_ref.extractall("./data")


def load_projected_temperature_data(
    lat: float = 48.2085, lon: float = 16.3721, year: int = 2050
) -> np.ndarray:
    """
    Load daily temperature data for Vienna in 2050 from CORDEX dataset.
    Parameters
    ----------
    lat : float
        Latitude of Vienna in degrees.
    lon : float
        Longitude of Vienna in degrees.
    year : int
        Year for which to load the data (default is 2050).

    Returns
    -------
    np.ndarray
        Daily temperature values (in °C).
    """
    file_nc = "./data/tas_EUR-11_MPI-M-MPI-ESM-LR_rcp45_r1i1p1_CLMcom-CCLM4-8-17_v1_day_20460101-20501231.nc"

    # Ensure file exists before opening
    if not os.path.exists(file_nc):
        print(f"The file {file_nc} does not exist.")
        # Run the download function
        download_cordex_data()

    # Open the nc file in the extracted folder
    ds = xr.open_dataset(file_nc)

    # Transform lon/lat -> rotated-pole grid coords
    tfm = Transformer.from_crs(
        CRS.from_epsg(4326),
        CRS.from_cf(ds.rotated_latitude_longitude.attrs),
        always_xy=True,
    )
    rlon, rlat = tfm.transform(lon, lat)

    # Get nearest grid point +/- size
    size = 0.2
    ds_vienna = ds.sel(
        rlon=slice(rlon - size, rlon + size), rlat=slice(rlat - size, rlat + size)
    )
    # Compute mean over the area
    ds_vienna_mean = ds_vienna.mean(dim=["rlon", "rlat"])

    # Select year 2050
    ds_vienna_mean = ds_vienna_mean.sel(time=slice(f"{year}-01-01", f"{year}-12-31"))

    tas = ds_vienna_mean.tas - 273.15  # Convert from K to °C

    return tas.values.flatten()


def main():
    t50 = load_projected_temperature_data()

    # Plot histogram of daily temperatures
    # Use bins of 1ºC from -10ºC to 36ºC
    plt.figure(figsize=(10, 6))

    plt.hist(t50, bins=range(-10, 36, 2), edgecolor="black")
    plt.title("Histogram of Daily Temperatures in Vienna (2050)")
    plt.xlabel("Temperature (°C)")
    plt.ylabel("Frequency")

    # Mark the mean temperature as a red vertical line
    mean_temp = t50.mean()
    plt.axvline(mean_temp, color="red", linestyle="dashed", linewidth=1)
    plt.text(
        mean_temp + 0.5, plt.ylim()[1] * 0.9, f"Mean: {mean_temp:.2f} °C", color="red"
    )

    plt.tight_layout()
    plt.savefig("output/vienna_temperature_histogram.png")
    plt.close()


if __name__ == "__main__":
    main()
