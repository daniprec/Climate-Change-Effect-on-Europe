import logging
import pathlib
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from tqdm import tqdm


def download_file(url: str, dest: pathlib.Path, chunk=1 << 20) -> pathlib.Path:
    """Stream-download url into dest. European Environment Agency (EEA)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for block in r.iter_content(chunk_size=chunk):
                fh.write(block)


def main(
    path_csv="./data/eea/ParquetFilesUrls_NOX.csv",
    output_csv: str = "./data/airquality.csv",
    max_urls: int = 5,
    verbose: bool = True,
):
    # Read the CSV that lists all parquet URLs
    links_df = pd.read_csv(path_csv)
    if "ParquetFileUrl" not in links_df.columns:
        raise ValueError(f"`ParquetFileUrl` column not found in {path_csv}")

    urls = links_df["ParquetFileUrl"].dropna().unique().tolist()
    if not urls:
        raise ValueError("No URLs found!")

    # Sort urls alphabetically (each one contains a country code)
    urls = sorted(urls)[:max_urls] if max_urls is not None else sorted(urls)
    # TODO: We can be clever and download one country at a time

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

    # Drop all validity rows that are not 1
    mask_valid = merged_df["Validity"] == 1
    merged_df = merged_df[mask_valid].reset_index(drop=True)
    if verbose:
        num_non_valid = (~mask_valid).sum()
        print(f"Removed {num_non_valid} non-valid rows.")

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
            raise ValueError(
                f"Multiple unique values found in {col} for some combinations."
                f"{merged_df[col].unique()}"
            )

    merged_df.to_csv(output_csv, index=False)
    print(f"Wrote merged csv     -> {output_csv}")

    # Quick sanity print
    if verbose:
        print("Merged shape:", merged_df.shape)
        print(merged_df.head())


if __name__ == "__main__":
    main(verbose=True)
