import os
import zipfile

import cdsapi
import matplotlib.pyplot as plt
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


def main():
    file_nc = "./data/tas_EUR-11_MPI-M-MPI-ESM-LR_rcp45_r1i1p1_CLMcom-CCLM4-8-17_v1_day_20460101-20501231.nc"

    # Ensure file exists before opening
    if not os.path.exists(file_nc):
        print(f"The file {file_nc} does not exist.")
        # Run the download function
        download_cordex_data()

    # Open the nc file in the extracted folder
    ds = xr.open_dataset(file_nc)

    # Location of Vienna
    vienna_lat = 48.2082
    vienna_lon = 16.3738

    # Transform lon/lat -> rotated-pole grid coords
    tfm = Transformer.from_crs(
        CRS.from_epsg(4326),
        CRS.from_cf(ds.rotated_latitude_longitude.attrs),
        always_xy=True,
    )
    rlon, rlat = tfm.transform(vienna_lon, vienna_lat)

    # Get nearest grid point +/- size of Vienna
    size = 0.2
    ds_vienna = ds.sel(
        rlon=slice(rlon - size, rlon + size), rlat=slice(rlat - size, rlat + size)
    )
    # Compute mean over the area
    ds_vienna_mean = ds_vienna.mean(dim=["rlon", "rlat"])

    # Select year 2050
    ds_vienna_mean = ds_vienna_mean.sel(time=slice("2050-01-01", "2050-12-31"))

    # Plot histogram of daily temperatures
    # Use bins of 1ºC from -10ºC to 40ºC
    plt.figure(figsize=(10, 6))
    tas = ds_vienna_mean.tas - 273.15  # Convert from K to °C
    plt.hist(tas.values.flatten(), bins=range(-10, 41), edgecolor="black")
    plt.title("Histogram of Daily Temperatures in Vienna (2050)")
    plt.xlabel("Temperature (°C)")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig("output/vienna_temperature_histogram.png")
    plt.close()


if __name__ == "__main__":
    main()
