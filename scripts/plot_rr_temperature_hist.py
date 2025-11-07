import os
import zipfile

import cdsapi
import xarray as xr


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

    print(ds)


if __name__ == "__main__":
    main()
