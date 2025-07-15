import logging
import os
import pathlib
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

DICT_POLLUTANTS = {5: "pm10", 7: "O3", 9: "NOx"}


def download_file(url: str, dest: pathlib.Path, chunk=1 << 20) -> pathlib.Path:
    """Stream-download url into dest. European Environment Agency (EEA)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for block in r.iter_content(chunk_size=chunk):
                fh.write(block)


def download_eea_air_quality_by_station(
    path_data: str = "./data/",
    pollutant: str = "PM10",
    nuts_id: str = "AT",
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Download and process EEA pollutant data for a specific NUTS region.
    This is a very heavy download.

    Parameters
    ----------
    path_data : str
        Path to the directory where the CSV file with parquet URLs is located.
    pollutant : str
        Pollutant to filter by. Options are "PM10", "O3", "NOx".
    nuts_id : str
        NUTS ID to filter the data by (e.g., "AT" for Austria).
    verbose : bool
        If True, print additional information during processing.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the averaged pollutant data for the specified NUTS region.
    """
    path_data = pathlib.Path(path_data)
    path_csv = path_data / "eea" / f"ParquetFilesUrls_{pollutant}.csv"
    if not path_csv.exists():
        raise FileNotFoundError(
            f"CSV file with parquet URLs not found at {path_csv}. "
            "Please download it from the EEA website."
        )

    # Read the CSV that lists all parquet URLs
    links_df = pd.read_csv(path_csv)
    if "ParquetFileUrl" not in links_df.columns:
        raise ValueError(f"`ParquetFileUrl` column not found in {path_csv}")

    urls = links_df["ParquetFileUrl"].dropna().unique().tolist()
    if not urls:
        raise ValueError("No URLs found!")

    # Take urls containing the specified NUTS_ID
    urls = [url for url in urls if f"/{nuts_id}/" in url]

    if len(urls) == 0:
        logging.warning(
            f"No URLs found for NUTS_ID '{nuts_id}' and pollutant '{pollutant}'."
        )
        # Return an empty DataFrame with the expected columns
        return pd.DataFrame(
            columns=[
                "NUTS_ID",
                "year",
                "week",
                "Pollutant",
                "Unit",
                "AggType",
                "Verification",
                "Value",
            ]
        )

    # Temporary folder to hold the downloads
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = pathlib.Path(tmp_dir)
        dfs = []

        for url in tqdm(urls, desc="Downloading + reading"):
            filename = tmp_dir / pathlib.Path(url).name
            try:
                download_file(url, filename)
                table = pq.read_table(filename)  # Arrow Table
                dfs.append(table)
            except Exception as exc:
                logging.warning(f"Skipped {url}: {exc}")

        if not dfs:
            raise RuntimeError("No parquet files could be read.")

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

    # Group by NUTS_ID, Year, Week, Pollutant. Average the Value
    merged_df = (
        merged_df.groupby(
            [
                "NUTS_ID",
                "Year",
                "Week",
                "Pollutant",
                "Unit",
                "AggType",
                "Verification",
            ],
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

    # Sort by NUTS_ID, Year, Week, Pollutant
    merged_df = merged_df.sort_values(
        by=["NUTS_ID", "Year", "Week", "Pollutant"], ignore_index=True
    )

    # Convert pollutant numbers to names
    merged_df["Pollutant"] = (
        merged_df["Pollutant"].map(DICT_POLLUTANTS).fillna("Unknown")
    )

    # Rename columns to match the rest of the project
    merged_df.rename(
        columns={"Year": "year", "Week": "week"},
        inplace=True,
    )

    return merged_df


def find_pollutant_eea_datastore_folders(
    pollutant: str = "NOx",
    url: str = "https://sdi.eea.europa.eu/webdav/datastore/public/",
) -> list[str]:
    """Find folders containing pollutant data on the EEA website.

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


def main():
    for pollutant in DICT_POLLUTANTS.values():
        nox_folders = find_pollutant_eea_datastore_folders(pollutant=pollutant)
        for folder_url in nox_folders:
            download_tif_from_eea_datastore_folder(folder_url)
        print("All .tif files downloaded!")


if __name__ == "__main__":
    main()
