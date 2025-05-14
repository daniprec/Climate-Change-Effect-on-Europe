import os

import pandas as pd
import requests


def download_eurostat_data(dataset: str, fmt: str = "TSV") -> pd.DataFrame:
    """
    Download Eurostat data from the given dataset URL.

    Parameters
    ----------
    dataset : str
        The dataset name to download from Eurostat.
    fmt : str
        The format of the data to download. Default is "TSV".

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the downloaded data.
    """
    url = (
        "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
        + dataset
        + "?format="
        + fmt
        + "&compressed=true"
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

    df = pd.read_csv(path_file, compression="gzip", encoding="utf-8", sep=",")

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
