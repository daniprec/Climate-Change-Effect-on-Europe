import pathlib
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from tqdm import tqdm


def download_file(url: str, dest: pathlib.Path, chunk=1 << 20) -> pathlib.Path:
    """Stream-download url into dest and return the Path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for block in r.iter_content(chunk_size=chunk):
                fh.write(block)
    return dest


def main(
    path_csv="./data/ParquetFilesUrls_NOX.csv",
    output_csv: str = "./data/airquality.csv",
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

    merged_df.to_csv(output_csv, index=False)
    print(f"Wrote merged csv     -> {output_csv}")

    # Quick sanity print
    print("Merged shape:", merged_df.shape)
    print(merged_df.head())


if __name__ == "__main__":
    main()
