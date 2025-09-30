from __future__ import annotations

import json
import os

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds


def write_partitioned_parquet(
    df: pd.DataFrame, base_dir: str, partition_cols: list[str]
):
    os.makedirs(base_dir, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    ds.write_dataset(
        data=table,
        base_dir=base_dir,
        format="parquet",
        partitioning=partition_cols,  # hive by default
        max_rows_per_group=50_000,
        max_rows_per_file=1_000_000,
        existing_data_behavior="overwrite_or_ignore",
    )


def write_dataset_json(meta: dict, path_json: str):
    os.makedirs(os.path.dirname(path_json), exist_ok=True)
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
