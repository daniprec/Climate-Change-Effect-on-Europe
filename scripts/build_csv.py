import os

import geopandas as gpd
import numpy as np
import pandas as pd

from ccee.cordex import cordex_tas_to_dataframe_per_region
from ccee.eea import download_eea_air_quality
from ccee.eurostat import (
    download_eurostat_mortality,
    download_eurostat_nuts2_population,
    download_eurostat_nuts3_population,
    download_eurostat_population_density,
)


def main(path_data: str = "./data", path_geojson: str = "./data/regions.geojson"):
    # Load the geojson file
    try:
        gdf = gpd.read_file(path_geojson)
        # Extract the NUTS_IDs from the GeoDataFrame
        ls_ids = gdf["NUTS_ID"].tolist()
    except FileNotFoundError:
        print(f"[WARNING] GeoJSON file not found at {path_geojson}.")
        return

    # Download all data
    df_demomwk = download_eurostat_mortality(ls_ids=ls_ids)
    df_popdensity = download_eurostat_population_density(ls_ids=ls_ids)
    df_pop3 = download_eurostat_nuts3_population()
    df_pop2 = download_eurostat_nuts2_population()

    # First we stack both population dataframes, so we have one for NUTS-3 and one for NUTS-2
    df_pop = pd.concat([df_pop2, df_pop3], ignore_index=True)
    # In case of duplicated (NUTS_ID, year), we prioritize the NUTS-2 population data
    df_pop = df_pop.drop_duplicates(subset=["NUTS_ID", "year"], keep="last")

    # Merge all of them by NUTS_ID and year
    df = df_demomwk.merge(df_popdensity, on=["NUTS_ID", "year"], how="outer")
    df = df.merge(df_pop, on=["NUTS_ID", "year"], how="outer")

    # Use the mortality and population to calculate the mortality rate
    df["mortality_rate"] = 100000 * df["mortality"] / df["population"]

    # Include CORDEX temperature data
    for rcp in [45, 85]:
        ls_df = []
        for year in range(2006, 2100, 10):
            df_tas = cordex_tas_to_dataframe_per_region(
                path_geojson=path_geojson, fin=path_data, year=year, rcp=rcp
            )
            ls_df.append(df_tas)
        df_tas = pd.concat(ls_df, ignore_index=True)

        # Merge the temperature data
        df = df.merge(df_tas, on=["NUTS_ID", "year", "week"], how="outer")

        # Interpolate up to 3 weeks of missing data
        df["temperature"] = df.groupby("NUTS_ID")["temperature"].transform(
            lambda x: x.interpolate(method="linear", limit=3, limit_direction="both")
        )

        # Rename "temperature" to avoid confusion
        df.rename(columns={"temperature": f"temperature_rcp{rcp}"}, inplace=True)

    # Drop any year after 2100, as we only consider the 21st century
    df = df[df["year"] <= 2100].copy()

    # Include air quality data
    # Iterate over each unique NUTS_ID in the DataFrame
    for nuts_id in df["NUTS_ID"].unique():
        # Download the air quality data for the specified pollutant and NUTS_ID
        print(f"[INFO] Downloading air quality data for NUTS_ID {nuts_id}...")
        df_aq = download_eea_air_quality(
            path_data=path_data, nuts_id=nuts_id, verbose=True
        )

        # Merge the pollutant data with the main DataFrame
        df = df.merge(df_aq, on=["NUTS_ID", "year", "week"], how="outer")

    # Reset the index after all merges
    df.reset_index(drop=True, inplace=True)

    # ------------------------------------------------------
    # Fill missing dates
    # ------------------------------------------------------

    # Create a complete date range for each NUTS_ID
    arr_years = np.arange(df["year"].min(), df["year"].max() + 1).astype(int)
    arr_weeks = np.arange(1, 53).astype(int)
    # Create all combinations of NUTS_ID, year, and week
    df_complete = pd.DataFrame(
        np.array(np.meshgrid(df["NUTS_ID"].unique(), arr_years, arr_weeks)).T.reshape(
            -1, 3
        ),
        columns=["NUTS_ID", "year", "week"],
    )

    # Merge the complete date range with the original DataFrame
    df = df_complete.merge(
        df,
        on=["NUTS_ID", "year", "week"],
        how="left",
    )

    df.sort_values(by=["NUTS_ID", "year", "week"], inplace=True)

    # Remove duplicates in case of multiple entries
    df.drop_duplicates(subset=["NUTS_ID", "year", "week"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    # ------------------------------------------------------
    # Store the dataframe
    # ------------------------------------------------------

    # Split Austria's NUTS-3 regions into their own CSV file
    mask_at = df["NUTS_ID"].str.startswith("AT") & (df["NUTS_ID"] != "AT")
    df_at = df[mask_at].copy()
    df_europe = df[~mask_at].copy()

    # Store the Austria DataFrame
    output_csv_at = os.path.join(path_data, "austria.csv")
    df_at.to_csv(output_csv_at, index=False, float_format="%.1f")
    print(f"[INFO] Successfully wrote {len(df_at)} records to {output_csv_at}!")

    # Store the Europe DataFrame
    output_csv_europe = os.path.join(path_data, "europe.csv")
    df_europe.to_csv(output_csv_europe, index=False, float_format="%.1f")
    print(f"[INFO] Successfully wrote {len(df_europe)} records to {output_csv_europe}!")


if __name__ == "__main__":
    main()
