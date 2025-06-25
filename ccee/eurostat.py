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
        print(f"Date range: {start_year} - {end_year}")

    return df


def download_eurostat_mortality(ls_ids: list[str] | None = None) -> pd.DataFrame:
    """
    ls_ids : list[str]
        List of NUTS-3 IDs to filter the Eurostat mortality data.
    """
    print("[INFO] Reading Eurostat mortality data into Pandas...")

    # Mortality data
    df_demomwk = download_eurostat_data(dataset="demo_r_mwk3_t")
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

    # The column names are like "2015-W01"
    # We will turn the dataframe into a long format:
    # Columns will be "NUTS_ID", "year", "week", "mortality"
    # Drop columns "freq" and "unit" first
    df_demomwk.drop(columns=["freq", "unit"], inplace=True)
    df_demomwk = df_demomwk.melt(
        id_vars=["NUTS_ID"],
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
    # Sort column order: NUTS_ID, year, week, mortality
    df_demomwk = df_demomwk[["NUTS_ID", "year", "week", "mortality"]]

    return df_demomwk


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

    return df_popdensity


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

    return df_pop


def download_eurostat_nuts3_population(
    ls_ids: list[str] | None = None,
) -> pd.DataFrame:
    print("[INFO] Reading Eurostat population data into Pandas...")
    # Population data
    df_pop = download_eurostat_data(dataset="demo_r_pjanaggr3")
    # Filter for total sex and age class
    mask_sex = df_pop["sex"] == "Total"
    mask_age = df_pop["age"] == "Total"
    df_pop = df_pop[mask_sex & mask_age].copy()
    df_pop.rename(columns={"geo": "NUTS_ID"}, inplace=True)
    df_pop.drop(columns=["freq", "unit", "sex", "age"], inplace=True)

    # If ls_ids is provided, filter for NUTS-3 regions
    if ls_ids is not None:
        # Filter for NUTS-3 regions
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

    return df_pop
