import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(".")
from utils.cordex import load_eurocordex_data
from utils.eurostat import download_eurostat_data


def main():
    df = download_eurostat_data(dataset="demo_r_mwk2_20")
    # Drop columns that are all NaN
    df.dropna(axis=1, how="all", inplace=True)

    # --------------------------

    # Get the NUTS code for Vienna
    mask_vienna = df["geo"].str.startswith("AT13")
    mask_age = df["age"] == "TOTAL"
    mask_sex = df["sex"] == "T"
    df_sub = df[mask_vienna & mask_age & mask_sex]

    # Take the columns with the format "YYYY-W00" where YYYY is the year and W00 is the week number
    ls_match = df_sub.columns.str.match(r"^\d{4}-W\d{2}$")
    df_sub = df_sub.loc[:, ls_match]

    # This leads to a single row, which we can convert to a Series
    ser = df_sub.iloc[0]
    # Convert the column names to datetime objects
    ser.index = pd.to_datetime(ser.index + "-1", format="%Y-W%W-%w")

    # And finally we can plot it
    fig, ax = plt.subplots()
    ser.plot(ax=ax)
    ax.set_title("Mortality in Vienna (AT13) by week")
    ax.set_xlabel("Date")
    ax.set_ylabel("Population")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("output/demomwk_vienna.jpg")
    plt.close()

    # ---------------------------

    # Now let's plot one series per year, all in the same plot, stacked vertically
    # We will define a color ranging from blue to red
    cmap = plt.get_cmap("coolwarm")
    # Create a color map
    colors = cmap(np.linspace(0, 1, len(ser.index.year.unique())))
    year_min = ser.index.year.min()
    year_max = ser.index.year.max()
    fig, ax = plt.subplots()
    for year in ser.index.year.unique():
        mask_year = ser.index.year == year
        ser_sub = ser[mask_year]
        # Extract the weeks
        weeks = ser_sub.index.strftime("%W").astype(int)
        ax.plot(weeks, ser_sub, color=colors[year - year_min])
    ax.set_title(f"Mortality in Vienna (AT13) by week ({year_min}-{year_max})")
    ax.set_xlabel("Week")
    ax.set_ylabel("Number of deaths")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("output/demomwk_vienna_years.jpg")
    plt.close()

    # -----------------------------

    cordex = load_eurocordex_data("./data", year=2000)

    # cordex is an nc file with coordinates "rlat", "rlot"
    # We will find the point closest to Vienna
    lat_vienna = 48.2082
    lon_vienna = 16.3738
    # Index in the nc file
    cordex_vienna = cordex.sel(rlat=lat_vienna, rlon=lon_vienna, method="nearest")

    # The variable "tas" is the temperature and the index "time" appears on a monthly basis
    # We will match the time index to the time index of the Eurostat data
    # The Eurostat data is weekly, so we will convert the temperature to weekly
    temperature = cordex_vienna.tas.values  # in Kelvin
    temperature = temperature - 273.15  # Convert to Celsius
    date = cordex_vienna.time.values
    ser_cordex = pd.Series(temperature, index=date)
    # Convert the index and resample to weekly
    ser_cordex.index = pd.to_datetime(ser_cordex.index)
    ser_cordex = ser_cordex.resample("W").mean()
    # Fill NaN values interpolating
    ser_cordex.interpolate(method="linear", inplace=True)
    # Make sure each week has the first day of the week as the index
    ser_cordex.index = ser_cordex.index - pd.to_timedelta(
        ser_cordex.index.weekday, unit="d"
    )

    # Finally, match the CORDEX and the mortality series
    df = ser.to_frame(name="mortality")
    df = df.join(ser_cordex.to_frame(name="temperature"), how="inner")

    # Plot scatter of temperature vs mortality
    fig, ax = plt.subplots()
    ax.scatter(df["temperature"], df["mortality"], alpha=0.5)
    ax.set_title("Mortality in Vienna (AT13) by week")
    ax.set_xlabel("Temperature (Celsius)")
    ax.set_ylabel("Number of deaths")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("output/demomwk_vienna_temp.jpg")
    plt.close()


if __name__ == "__main__":
    main()
