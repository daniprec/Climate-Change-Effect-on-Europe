import os

import pandas as pd
import requests


def download_eurostat_data(dataset: str) -> pd.DataFrame:
    """
    Download Eurostat data from the given dataset URL.

    Parameters
    ----------
    dataset : str
        The dataset name to download from Eurostat.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the downloaded data.
    """
    url = (
        "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
        + dataset
        + "?format=TSV&compressed=true"
    )
    # Create a cache directory if it doesn't exist
    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)
    path_file = os.path.join(cache_dir, "dataset.csv.gz")
    response = requests.get(url)
    if response.status_code == 200:
        with open(path_file, "wb") as file:
            file.write(response.content)
    else:
        print(f"Failed to download file: {response.status_code}")

    df = pd.read_csv(
        path_file,
        compression="gzip",
        encoding="utf-8",
        sep=",|\t",
        na_values=":",
        engine="python",
    )

    # If a column name has "\", drop all after the first "\" in that column name
    df.columns = df.columns.str.split("\\").str[0]

    # The columns which name starts with any year "YYYY" are all numeric
    # We force that numeric columns to be float64
    for col in df.columns:
        # Check the column name matches our criteria
        if col.startswith(tuple(str(year) for year in range(1900, 2100))):
            # Convert the column to numeric, forcing errors to NaN
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Remove the gzip file after reading
    try:
        os.remove(path_file)
    except PermissionError:
        print(
            f"Warning: Could not delete temporary file {path_file}. You may need to delete it manually."
        )
    except OSError as e:
        print(
            f"Warning: Error while trying to delete temporary file {path_file}: {str(e)}"
        )
    return df
