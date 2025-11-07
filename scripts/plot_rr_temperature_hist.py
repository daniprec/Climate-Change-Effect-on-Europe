import os
import zipfile

import cdsapi
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from patsy import bs  # b-spline basis
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

    # Sample at nearest grid point
    ds_slice = ds.sel(
        rlon=rlon,
        rlat=rlat,
        method="nearest",
    )

    # Select year 2050
    ds_slice_mean = ds_slice.sel(time=slice(f"{year}-01-01", f"{year}-12-31"))

    tas = ds_slice_mean.tas - 273.15  # Convert from K to °C

    return tas.values.flatten()


def load_reanalysis_temperature_data(
    lat: float = 48.2085, lon: float = 16.3721, year: int = 2024
) -> np.ndarray:
    ls_temps = []
    for month in range(1, 13):
        era5_file = f"./data/era5-land/ERA5-Land-{year}-{month:02d}.grib"
        era5 = xr.open_dataset(era5_file, engine="cfgrib", decode_timedelta=True)
        temp = era5["t2m"]
        # Coordinates:
        # time: day
        # step: hour (0, 1, ..., 23)

        # Temperature is in Kelvin, convert to Celsius
        temp = temp - 273.15  # Convert from Kelvin to Celsius

        # Sample nearest grid point to Vienna
        temp_slice = temp.sel(latitude=lat, longitude=lon, method="nearest")

        # Average over hours to get daily mean
        temp_slice = temp_slice.mean(dim="step")

        ls_temps.append(temp_slice)

    # Return a single numpy array with all daily temperatures
    return np.concatenate([t.values.flatten() for t in ls_temps])


def plot_rr_curve(urau_code: str = "AT001C"):
    coefs_df = pd.read_csv("../EUcityProj/data/coefs.csv")
    # 5 age groups x 5 coefficients
    coefs = coefs_df[coefs_df["URAU_CODE"] == urau_code].iloc[:, 2:]
    tmeanper_df = pd.read_csv("../EUcityProj/data/tmean_distribution.csv")

    # 117 points: 0.1% to 1.0% (10 points) 2% to 98% (97 points) 99% to 99.9% (10 points)
    tmeanper = tmeanper_df[tmeanper_df["URAU_CODE"] == urau_code].iloc[:, 2:-1]

    # B-spline basis for the temperature percentiles
    bvar = bs(
        tmeanper.values[0],
        knots=tmeanper[["10.0%", "75.0%", "90.0%"]].values[0],
        degree=2,
        include_intercept=False,
    )
    firstpred = bvar @ coefs.values.T  # 117 points x 5 age groups
    # indices of minimum mortality temperature for each age group

    # restrict to 25th to 99th percentiles
    mmt_inrange_ix = np.argmin(firstpred[33:108, :], axis=0) + 33

    # minimum mortality temperatures for each age group
    mmt = tmeanper.iloc[:, mmt_inrange_ix]
    # b-spline coefficients at MMT for each age group

    # bvar_at_mmt[a, j] = bvar[mmt_inrange_ix[a], j] = bvar[i_a, j] = B_j(T_{MMT,a})
    bvar_at_mmt = bvar[mmt_inrange_ix, :]

    # Vectorized without newaxis (using einsum)
    # Compute for all temperatures and ages at once
    log_rr = np.einsum("ij,aj->ia", bvar, coefs.values) - np.einsum(
        "aj,aj->a", bvar_at_mmt, coefs.values
    )

    rr = np.exp(log_rr)

    return rr, tmeanper.values[0]


def main(year_cordex: int = 2050, year_era5: int = 2020):
    t_cordex = load_projected_temperature_data(year=year_cordex)
    t_era5 = load_reanalysis_temperature_data(year=year_era5)

    # Plot histogram of daily temperatures
    # Use bins of 1ºC from -10ºC to 36ºC
    plt.figure(figsize=(10, 6))

    plt.hist(
        t_cordex,
        bins=range(-10, 36, 2),
        alpha=0.7,
        label=f"CORDEX {year_cordex}",
        color="orange",
    )
    plt.hist(
        t_era5,
        bins=range(-10, 36, 2),
        alpha=0.7,
        label=f"ERA5 {year_era5}",
        color="blue",
    )
    plt.title("Histogram of Daily Temperatures in Vienna")
    plt.xlabel("Temperature (°C)")
    plt.ylabel("Frequency")

    # Mark the mean temperature as a vertical line
    mean_temp_cordex = t_cordex.mean()
    plt.axvline(mean_temp_cordex, color="red", linestyle="dashed", linewidth=1)
    plt.text(
        mean_temp_cordex + 0.5,
        plt.ylim()[1] * 0.9,
        f"Mean: {mean_temp_cordex:.2f} °C",
        color="red",
    )
    mean_temp_era5 = t_era5.mean()
    plt.axvline(mean_temp_era5, color="blue", linestyle="dashed", linewidth=1)
    plt.text(
        mean_temp_era5 + 0.5,
        plt.ylim()[1] * 0.8,
        f"Mean: {mean_temp_era5:.2f} °C",
        color="blue",
    )

    # RR curve
    rr, tmean = plot_rr_curve(urau_code="AT001C")
    # Get age group
    rr = rr[:, 3]

    # Create a right y-axis for RR
    ax2 = plt.gca().twinx()
    ax2.plot(
        tmean,
        rr,
        color="black",
        label="Relative Risk (Age 65-74)",
        linewidth=2,
    )
    ax2.set_ylabel("Relative Risk", color="black")
    ax2.tick_params(axis="y", labelcolor="black")

    plt.legend()
    plt.tight_layout()
    plt.savefig("output/vienna_temperature_histogram.png")
    plt.close()


if __name__ == "__main__":
    main()
