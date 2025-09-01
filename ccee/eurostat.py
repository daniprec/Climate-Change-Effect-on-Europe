import os

import geopandas as gpd
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
        dtype_backend="pyarrow",
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
        # Some columns have trailing spaces, we remove them
        df.rename(columns={col: col.rstrip()}, inplace=True)

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

    # Print date range
    date_columns = df.dropna(axis=0, how="any").columns[
        df.columns.str.match(r"^\d{4}$")
    ]
    if not date_columns.empty:
        start_year = date_columns.min()
        end_year = date_columns.max()
        print(f"[INFO] Eurostat - Date range: {start_year} - {end_year}")

    # Attempt to infer better dtypes for object columns
    return df.infer_objects(copy=False)


def download_eurostat_mortality(ls_ids: list[str] | None = None) -> pd.DataFrame:
    """
    Deaths by week, sex, 20-year age group and NUTS 3 region.

    URL: https://ec.europa.eu/eurostat/databrowser/view/demo_r_mwk3_20/default/table?lang=en&category=demo.demomwk

    Parameters
    ----------
    ls_ids : list[str]
        List of NUTS-3 IDs to filter the Eurostat mortality data.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns "NUTS_ID", "year", "week", "mortality"
    """
    print("[INFO] Reading Eurostat mortality data into Pandas...")

    # Mortality data
    df_demomwk = download_eurostat_data(dataset="demo_r_mwk3_20")
    df_demomwk.rename(columns={"geo": "NUTS_ID"}, inplace=True)

    # Match the NUTS_ID with the GeoDataFrame
    if ls_ids is not None:
        ls_all = df_demomwk["NUTS_ID"].unique().tolist()
        ls_out = sorted([x for x in ls_all if x not in ls_ids])
        ls_out2 = sorted([x for x in ls_ids if x not in ls_all])
        df_demomwk = df_demomwk[df_demomwk["NUTS_ID"].isin(ls_ids)].copy()
        print("The following IDs were dropped from Eurostat data:")
        print(", ".join(ls_out))
        print("The following IDs were not found in Eurostat data:")
        print(", ".join(ls_out2))

    # Drop UNK age groups
    df_demomwk = df_demomwk[df_demomwk["age"] != "UNK"].copy()
    # Map age groups to codes
    dict_age = {
        "TOTAL": "T",
        "Y_LT20": "00",
        "Y20-39": "20",
        "Y40-59": "40",
        "Y60-79": "60",
        "Y_GE80": "80",
    }
    df_demomwk["age"] = df_demomwk["age"].map(dict_age)

    # Drop UNK sex
    df_demomwk = df_demomwk[df_demomwk["sex"] != "UNK"].copy()
    dict_sex = {"T": "T", "F": "F", "M": "M"}
    df_demomwk["sex"] = df_demomwk["sex"].map(dict_sex)

    # The column names are like "2015-W01"
    # We will turn the dataframe into a long format:
    # Columns will be "NUTS_ID", "year", "week", "mortality"
    # Drop columns "freq" and "unit" first
    df_demomwk.drop(columns=["freq", "unit"], inplace=True)
    df_demomwk = df_demomwk.melt(
        id_vars=["NUTS_ID", "age", "sex"],
        var_name="year_week",
        value_name="mortality",
    )
    # Extract year and week from "year_week"
    df_demomwk["year"] = df_demomwk["year_week"].str[:4].astype(int)
    df_demomwk["week"] = df_demomwk["year_week"].str[6:].astype(int)
    # Drop the "year_week" column
    df_demomwk.drop(columns=["year_week"], inplace=True)
    # Drop NaNs in "mortality"
    df_demomwk.dropna(subset=["mortality"], inplace=True)

    # We want a single row per NUTS_ID, year, week
    # In order to do this, we will pivot the dataframe:
    # the new columns will be "mortality_<sex>_<age>"
    df_demomwk = df_demomwk.pivot(
        index=["NUTS_ID", "year", "week"], columns=["sex", "age"], values="mortality"
    )
    df_demomwk.columns = df_demomwk.columns.map(
        lambda x: "mortality_{}_{}".format(x[0], x[1]) if isinstance(x, tuple) else x
    )

    # For consistency, "mortality_T_T" is renamed to "mortality"
    dict_rename = {"mortality_T_T": "mortality"}
    df_demomwk.rename(columns=dict_rename, inplace=True)

    # Reset index to turn the index into columns
    df_demomwk.reset_index(inplace=True)

    # Attempt to infer better dtypes for object columns
    return df_demomwk.infer_objects(copy=False)


def download_eurostat_population_density(
    ls_ids: list[str] | None = None,
) -> pd.DataFrame:
    # Download population density data
    df_popdensity = download_eurostat_data(dataset="demo_r_d3dens")
    df_popdensity.rename(columns={"geo": "NUTS_ID"}, inplace=True)
    df_popdensity.drop(columns=["freq", "unit"], inplace=True)
    if ls_ids is not None:
        # Filter for NUTS-3 regions
        df_popdensity = df_popdensity[df_popdensity["NUTS_ID"].isin(ls_ids)].copy()
    # Melt the DataFrame to long format
    df_popdensity = df_popdensity.melt(
        id_vars=["NUTS_ID"],
        var_name="year",
        value_name="population_density",
    )
    # Drop NaNs in "population_density"
    df_popdensity.dropna(subset=["population_density"], inplace=True)
    # Convert year to integer
    df_popdensity["year"] = df_popdensity["year"].astype(int)
    # Sort column order: NUTS_ID, year, population_density
    df_popdensity = df_popdensity[["NUTS_ID", "year", "population_density"]]

    # Attempt to infer better dtypes for object columns
    return df_popdensity.infer_objects(copy=False)


def download_eurostat_nuts2_population(
    ls_ids: list[str] | None = None,
) -> pd.DataFrame:
    print("[INFO] Reading Eurostat population data into Pandas...")
    # Population data
    df_pop = download_eurostat_data(dataset="tps00001")
    df_pop.rename(columns={"geo": "NUTS_ID"}, inplace=True)
    df_pop.drop(columns=["freq", "indic_de"], inplace=True)

    # Filter for NUTS-2 regions only
    if ls_ids is not None:
        # Filter for NUTS-2 regions
        df_pop = df_pop[df_pop["NUTS_ID"].isin(ls_ids)].copy()

    # The column names are like "2020"
    # We will turn the dataframe into a long format:
    # Columns will be "name", "year", "population"
    df_pop = df_pop.melt(
        id_vars=["NUTS_ID"],
        var_name="year",
        value_name="population",
    )

    # Convert "year" to integer
    df_pop["year"] = df_pop["year"].astype(int)

    # Attempt to infer better dtypes for object columns
    return df_pop.infer_objects(copy=False)


def download_eurostat_nuts3_population(
    ls_ids: list[str] | None = None,
) -> pd.DataFrame:
    """
    Population on 1 January by age group, sex and NUTS 3 region
    https://ec.europa.eu/eurostat/databrowser/view/demo_r_pjangrp3/default/table?lang=en
    Valid from 2015 onwards
    """
    print("[INFO] Reading Eurostat population data into Pandas...")
    # Population data
    df_pop = download_eurostat_data(dataset="demo_r_pjangrp3")
    df_pop.rename(columns={"geo": "NUTS_ID"}, inplace=True)
    df_pop.drop(columns=["freq", "unit"], inplace=True)

    # If ls_ids is provided, filter for NUTS-3 regions
    if ls_ids is not None:
        # Filter for NUTS-3 regions
        df_pop = df_pop[df_pop["NUTS_ID"].isin(ls_ids)].copy()

    # Drop UNK age groups
    df_pop = df_pop[df_pop["age"] != "UNK"].copy()
    # Group age classes to match the mortality data
    dict_age = {
        "TOTAL": "T",
        "Y_LT5": "00",
        "Y5-9": "00",
        "Y10-14": "00",
        "Y15-19": "00",
        "Y20-24": "20",
        "Y25-29": "20",
        "Y30-34": "20",
        "Y35-39": "20",
        "Y40-44": "40",
        "Y45-49": "40",
        "Y50-54": "40",
        "Y55-59": "40",
        "Y60-64": "60",
        "Y65-69": "60",
        "Y70-74": "60",
        "Y75-79": "60",
        "Y80-84": "80",
        "Y85-89": "80",
        "Y_GE85": "80",
        "Y_GE90": "80",
    }
    df_pop["age"] = df_pop["age"].map(dict_age)

    # The column names are like "2020"
    # We will turn the dataframe into a long format:
    # Columns will be "NUTS_ID", "sex", "age", "year", "population"
    year_cols = df_pop.columns[df_pop.columns.str.match(r"^\d{4}$")]
    df_pop = df_pop[["NUTS_ID", "sex", "age"] + year_cols.tolist()]
    df_pop = df_pop.melt(
        id_vars=["NUTS_ID", "sex", "age"],
        var_name="year",
        value_name="population",
    )
    df_pop.dropna(subset=["population"], inplace=True)

    # Convert "year" to integer
    df_pop["year"] = df_pop["year"].astype(int)

    # Sum the population by age group and sex
    cols_group = ["NUTS_ID", "year", "sex", "age"]
    df_pop = df_pop.groupby(cols_group, as_index=False)["population"].sum()

    # We want a single row per NUTS_ID, year with columns population_<sex>_<age>
    df_pop = df_pop.pivot(
        index=["NUTS_ID", "year"], columns=["sex", "age"], values="population"
    )
    df_pop.columns = [f"population_{s}_{a}" for (s, a) in df_pop.columns]
    df_pop = df_pop.reset_index()

    # For consistency, "population_T_T" is renamed to "population"
    if "population_T_T" in df_pop.columns:
        df_pop.rename(columns={"population_T_T": "population"}, inplace=True)

    # Attempt to infer better dtypes for object columns
    return df_pop.infer_objects(copy=False)


def compute_population_from_density(
    df: pd.DataFrame, path_geojson: str = "./data/regions.geojson"
) -> pd.DataFrame:
    """
    Compute the population from the population density and area of each NUTS region.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with columns "NUTS_ID", "population_density", and "population".
    path_geojson : str
        Path to a GeoJSON file containing NUTS regions with their geometries.

    Returns
    -------
    pd.DataFrame
        DataFrame with the population computed from the density and area.
    """
    # Load a NUTS boundary layer
    nuts = gpd.read_file(path_geojson)  # contains all NUTS levels
    nuts = nuts[["NUTS_ID", "geometry"]]  # keep what we need

    # Compute each region's area in km2
    # Use an equal‑area projection for Europe (EPSG:3035 = ETRS‑LAEA).
    nuts = nuts.to_crs(3035)
    nuts["area_km2"] = nuts.geometry.area / 1_000_000  # m2 -> km2
    nuts = nuts[["NUTS_ID", "area_km2"]]

    # Merge the areas into our DataFrame
    df = df.merge(nuts, on="NUTS_ID", how="left")

    # Compute population
    population = (df["population_density"] * df["area_km2"]).astype(
        int, errors="ignore"
    )

    # Fill "population" when missing
    df["population"] = df["population"].fillna(population)

    # Drop the "area_km2" column as it's no longer needed
    df.drop(columns=["area_km2"], inplace=True)

    # Attempt to infer better dtypes for object columns
    return df.infer_objects(copy=False)


def compute_mortality_rate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the mortality rate per 100,000 inhabitants.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with columns "mortality" and "population".

    Returns
    -------
    pd.DataFrame
        DataFrame with an additional column "mortality_rate".
    """
    # Find all columns starting with "mortality"
    mortality_cols = [col for col in df.columns if col.startswith("mortality")]
    # Make the same list with "population"
    population_cols = [col.replace("mortality", "population") for col in mortality_cols]
    # For each mortality column, compute the mortality rate
    for mort_col, pop_col in zip(mortality_cols, population_cols):
        if pop_col in df.columns:
            rate_col = mort_col.replace("mortality", "mortality_rate")
            df[rate_col] = 100000 * df[mort_col] / df[pop_col]

    # Attempt to infer better dtypes for object columns
    return df.infer_objects(copy=False)
