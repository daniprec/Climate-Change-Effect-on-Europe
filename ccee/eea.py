import logging
import os
import pathlib
import zipfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from bs4 import BeautifulSoup

DICT_POLLUTANTS = {5: "pm10", 7: "O3", 9: "NOx"}


def download_eea_air_quality_by_station(
    path_data: str = "./data/",
    nuts_id: str = "AT",
    agg_type: str = "day",
    dataset: int = 3,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Download and process EEA pollutant data for a specific NUTS region.
    NOTE: This is a heavy operation that downloads multiple parquet files
    and processes them into a single DataFrame.

    Source: https://eeadmz1-downloads-webapp.azurewebsites.net/
    Instructions:
    https://eeadmz1-downloads-webapp.azurewebsites.net/content/documentation/How_To_Downloads.pdf

    Parameters
    ----------
    path_data : str, optional
        Path to the directory where the CSV file with parquet URLs is located.
    nuts_id : str, optional
        NUTS ID to filter the data by (e.g., "AT" for Austria).
    agg_type : str, optional
        Aggregation type for the data. Options are "hour", "day" and "var" (variable)
        Default is "day".
    dataset : int, optional
        (1) Unverified data transmitted continuously (Up-To-Date/UTD/E2a) data from the beginning of 2023.
        (2) Verified data (E1a) from 2013 to 2022 reported by countries by 30 September each year for the previous year.
        (3) Historical Airbase data delivered between 2002 and 2012 before Air Quality Directive 2008/50/EC entered into force
    verbose : bool, optional
        If True, print additional information during processing.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the averaged pollutant data for the specified NUTS region.
    """
    # Check if the path_data exists, if not create it
    path_data = pathlib.Path(path_data)
    if not path_data.exists():
        os.makedirs(path_data)
        if verbose:
            print(f"Created directory: {path_data}")

    api_url = "https://eeadmz1-downloads-api-appservice.azurewebsites.net/"
    # Both endpoints are invoked exactly the same way
    endpoint = "ParquetFile/dynamic"
    # Request body
    request_body = {
        "countries": [nuts_id],
        "cities": [],
        "pollutants": [
            f"http://dd.eionet.europa.eu/vocabulary/aq/pollutant/{poll_id}"
            for poll_id in DICT_POLLUTANTS.keys()
        ],
        "dataset": dataset,
        "dateTimeStart": "2000-01-01T00:00:00.000Z",
        "dateTimeEnd": "2050-12-31T23:59:59.000Z",
        "aggregationType": agg_type,
        "email": "daniel.precioso@ie.edu",
    }

    # A get request to the API
    download_file = requests.post(api_url + endpoint, json=request_body).content
    # Store in local path
    path_zip = path_data / f"eea_{nuts_id}.zip"
    with open(path_zip, "wb") as output:
        output.write(download_file)

    # Take a snapshot of the path_data directory before unpacking
    list_files_before = list(path_data.rglob("*"))

    # Unzip the downloaded file in the same folder
    try:
        with zipfile.ZipFile(path_zip, "r") as zip_ref:
            zip_ref.extractall(path_data)
    except zipfile.BadZipFile:
        print(
            "The downloaded file is not a valid zip file. Please check the API response."
        )
        # Remove the zip file
        os.remove(path_zip)
        # Return an empty DataFrame with the expected columns
        return pd.DataFrame(columns=["NUTS_ID", "year", "week"])

    # Remove the zip file
    os.remove(path_zip)

    # Find the new extracted files
    list_files_after = list(path_data.rglob("*.parquet"))
    new_files = list(set(list_files_after) - set(list_files_before))

    if len(new_files) == 0:
        print("No parquet files could be read.")
        # Return an empty DataFrame with the expected columns
        return pd.DataFrame(columns=["NUTS_ID", "year", "week"])

    # Read the parquet files extracted from the zip file
    # The can be in subfolders, so we use glob
    dfs = []
    for parquet_file in new_files:
        table = pq.read_table(parquet_file)  # Arrow Table
        dfs.append(table)
        os.remove(parquet_file)

    # Concatenate the Arrow tables efficiently
    merged_table = pa.concat_tables(dfs, promote=True)
    merged_df = merged_table.to_pandas()

    # Keep only valid rows
    mask_valid = merged_df["Validity"] == 1
    merged_df = merged_df[mask_valid].reset_index(drop=True)
    if verbose:
        num_non_valid = (~mask_valid).sum()
        print(
            f"Removed {num_non_valid} non-valid rows out of {len(merged_df)} total rows."
        )

    # The letters before "/" in each element in "Samplingpoint" is the NUTS # code. For instance "BA/SPO-BA0038A_00009_100" -> "BA"
    merged_df["NUTS_ID"] = merged_df["Samplingpoint"].str.split("/").str[0]

    # The "Start" column has the format "2024-01-01 00:00:00"
    # We extract from them "Year" and "Week" using pandas after conversion
    merged_df["Start"] = pd.to_datetime(merged_df["Start"])
    merged_df["Year"] = merged_df["Start"].dt.year
    merged_df["Week"] = merged_df["Start"].dt.isocalendar().week
    # Turn None in "Unit" to "Unknown" to avoid issues later (with the groupby)
    merged_df["Unit"] = merged_df["Unit"].fillna("Unknown")

    # Group by NUTS_ID, Year, Week, Pollutant. Average the Value
    merged_df = (
        merged_df.groupby(
            ["NUTS_ID", "Year", "Week", "Pollutant", "Unit", "AggType", "Verification"],
            as_index=False,
        )
        .agg({"Value": "mean"})
        .reset_index(drop=True)
    )

    # Extra check: ensure the is a single "Unit" and "AggType" per NUTS_ID, Year, Week, Pollutant
    for col in ["Unit", "AggType", "Verification"]:
        if (
            merged_df.groupby(["NUTS_ID", "Year", "Week", "Pollutant"])[col].nunique()
            > 1
        ).any():
            logging.warning(
                f"Multiple unique values found in {col} for some combinations."
                f"{merged_df[col].unique()}"
            )
            # Average the values in case of multiple unique values
            merged_df[col] = merged_df.groupby(
                ["NUTS_ID", "Year", "Week", "Pollutant"]
            )[col].transform("first")
    # Drop these columns as they are not needed in the final output
    merged_df.drop(columns=["Unit", "AggType", "Verification"], inplace=True)

    # Sort by NUTS_ID, Year, Week, Pollutant
    merged_df = merged_df.sort_values(
        by=["NUTS_ID", "Year", "Week", "Pollutant"], ignore_index=True
    )

    # Convert pollutant numbers to names
    merged_df["Pollutant"] = (
        merged_df["Pollutant"].map(DICT_POLLUTANTS).fillna("Unknown")
    )

    # Rename columns to match the rest of the project
    merged_df.rename(columns={"Year": "year", "Week": "week"}, inplace=True)

    # Pivot the table:
    # Columns: NUTS_ID, year, week, pollutant names (from "Pollutant")
    # Value in each pollutant cell is the old "Value" column
    merged_df = merged_df.pivot_table(
        index=["NUTS_ID", "year", "week"],
        columns="Pollutant",
        values="Value",
        aggfunc="mean",
    ).reset_index()

    return merged_df


def find_pollutant_eea_datastore_folders(
    pollutant: str = "NOx",
    url: str = "https://sdi.eea.europa.eu/webdav/datastore/public/",
) -> list[str]:
    """Find folders containing pollutant data on the EEA website.
    NOTE: This function is not used because the interpolated data is a yearly
    average. We want finer granularity, so we download the data by station.

    Parameters
    ----------
    pollutant : str
        Pollutant to search for, by default "NOx".
    url : str
        Base URL of the EEA datastore.

    Returns
    -------
    list[str]
        List of URLs to folders containing the specified pollutant data.
    """
    print(f"Scanning main index at {url}")
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.find_all("a")

    nox_folders = []
    for link in links:
        href = link.get("href")
        if href and pollutant in href and href.endswith("/"):
            full_url = url + href
            nox_folders.append(full_url)

    print(f"Found {len(nox_folders)} {pollutant} folders.")
    return nox_folders


def download_tif_from_eea_datastore_folder(folder_url: str, path_data: str = "./data"):
    """Download all .tif files from a specified EEA datastore folder.
    NOTE: The .tif files contain yearly averages, which are not suitable for
    fine-grained analysis. This function is provided for completeness, but
    it is not used in the main workflow.

    Parameters
    ----------
    folder_url : str
        URL of the EEA datastore folder containing .tif files.
    path_data : str
        Path to the directory where the .tif files will be saved.
        Defaults to "./data".
    """
    path_data = pathlib.Path(path_data)
    output_folder = path_data / "eea"
    print(f"Checking {folder_url}")
    try:
        response = requests.get(folder_url)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        print(f"Failed to access {folder_url}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.find_all("a")

    for link in links:
        href = link.get("href")
        if href and href.endswith(".tif"):
            file_url = folder_url + href
            filename = output_folder / href

            if os.path.exists(filename):
                print(f"Already downloaded: {filename}")
                return

            print(f"Downloading: {file_url}")
            tif_resp = requests.get(file_url)
            if tif_resp.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(tif_resp.content)
                print(f"Saved to {filename}")
            else:
                print(f"Failed to download {file_url}")


def main(download_tif: bool = False):
    if not download_tif:
        df = download_eea_air_quality_by_station(verbose=True)
        print(df.head())
    else:
        for pollutant in DICT_POLLUTANTS.values():
            nox_folders = find_pollutant_eea_datastore_folders(pollutant=pollutant)
            for folder_url in nox_folders:
                download_tif_from_eea_datastore_folder(folder_url)
            print("All .tif files downloaded!")


if __name__ == "__main__":
    main()
