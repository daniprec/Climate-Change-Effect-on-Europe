# VIG-IE Insurance and Tech Lab

[![Language](https://img.shields.io/badge/language-Python-3776AB)](https://www.python.org/)
[![Last Commit](https://img.shields.io/github/last-commit/daniprec/flask-demo)](https://github.com/daniprec/flask-demo)
![License](https://img.shields.io/badge/license-MIT-blue)
[![Flask](https://img.shields.io/badge/framework-Flask-000000?logo=flask)](https://flask.palletsprojects.com/)
[![Folium](https://img.shields.io/badge/map-viz--Folium-77B829)](https://python-visualization.github.io/folium/)

⭐ Star this project - it helps others discover it and supports development!

## Map Visualization with Flask and Folium

This Flask application visualizes European population, mortality, and temperature data interactively on a map. It supports multi-scale zoom and analysis, with additional granularity for Vienna at the NUTS-3 level.

It is hosted on [Python Anywhere](https://ixlabs-daniprec.pythonanywhere.com/) for easy access and exploration.

## Table of Contents

- [About](#about)
- [Features](#features)
- [Project Structure](#project-structure)
- [Quick‑Start Guide](#quick-start-quide)
- [How to Download Data](#how-to-download-data)
- [License](#license)
- [Contacts](#contacts)

## About

This project provides an interactive dashboard using **Flask** and **Folium** to explore the Climate Change Effect on Europe (CCEE):

- **Population & Mortality**: Monthly data per capita, visualized regionally.
- **Temperature (tas)**: Monthly near-surface air temperature data.
- Vienna supports detailed NUTS-3 level analysis.

See the project structure here: [http://danielprecioso.com/Climate-Change-Effect-on-Europe/]

## Features

- Interactive map with zoom and tooltip support
- Time-series visualization by region
- Population-normalized mortality overlays
- NUTS-level granularity (with detailed view for Vienna)
- Responsive Flask backend with pre-processed data cache

## Project Structure

```plaintext
├── app.py # Flask server
├── templates/ # HTML views
├── static/ # JS, CSS, assets
├── scripts/ # Data processing scripts
├── data/ # Input and downloaded data
├── requirements.txt
└── README.md
```

## Quick‑Start Guide

### 1 . Clone the repository

```bash
git clone https://github.com/daniprec/Climate-Change-Effect-on-Europe.git
cd Climate-Change-Effect-on-Europe
```

### 2 . Choose which dependencies to install

| Scenario                                   | File to install        | Typical use           |
| ------------------------------------------ | ---------------------- | --------------------- |
| **Run the web app only**                   | `requirements.txt`     | PythonAnywhere / prod |
| **Do data prep, notebooks, model fitting** | `requirements‑dev.txt` | Local dev / CI        |

```bash
# minimal runtime stack
pip install -r requirements.txt

# OR full analytics stack
pip install -r requirements‑dev.txt
```

### 3 . Install the project package itself

This makes the `ccee` library importable:

```bash
pip install .
```

_(Editable mode for active development)_

```bash
pip install -e .
```

### 4 . Launch the Flask server

```bash
python app.py
```

Open your browser at [http://127.0.0.1:5000/](http://127.0.0.1:5000/) to explore the interactive map.

---

**Tips**

- If you work in a virtual‑env, create and activate it **before** step 2.

  ```bash
  python -m venv .venv && source .venv/bin/activate
  ```

- For hot‑reload during development, set `FLASK_ENV=development` or run

  ```bash
  flask --app app run --debug
  ```

- On PythonAnywhere deploy only `requirements.txt` to keep the footprint small; use `requirements‑dev.txt` locally for notebooks and batch jobs.

## How to Download Data

Most of the data used in this project is available through public APIs or data portals. You can build the files used by the map just by running:

```bash
python scripts/build_geojson.py
python scripts/build_csv.py
```

The only data that needs to be downloaded manually is the CORDEX CMIP data, which requires a WGET script. Below are the instructions for downloading and preparing the data.

### CORDEX - CMIP (Climate Projections)

Source: [ESGF Data Browser (LiU Node)](https://esg-dn1.nsc.liu.se/search/esgf-liu/)

[Official tutorial link](https://cordex.org/wp-content/uploads/2023/08/How-to-download-CORDEX-data-from-the-ESGF.pdf)

**Step-by-step**:

1. Register to access the ESGF data.
2. Search with the following filters:
   - **Project**: CORDEX
   - **Experiment**: rcp85 OR rcp45
   - **Variable**: tas (air temperature)
   - **Domain**: EUR-11
   - **Time Frequency**: mon
3. Select a dataset, e.g.:

   ```plaintext
   cordex.output.EUR-11.SMHI.MPI-M-MPI-ESM-LR.rcp85.r2i1p1.RCA4.v1.mon.tas
   ```

4. Download the WGET script and run:

```bash
bash ./data/wget-YYYYMMDDHHMMSS.sh -H
```

**Tip**: You will need a Linux-based system (e.g., Ubuntu) to execute WGET scripts.

Make sure you store the data inside the `data/rcp45` and `data/rcp85` directories. The functions inside `ccee/cordex.py` will take care of the rest.

**Variables**:

- `temperature_rcp45`: Near-surface air temperature (in Celsius) for RCP 4.5 scenario.
- `temperature_rcp85`: Near-surface air temperature (in Celsius) for RCP 8.5 scenario.

### ERA5 - Land Reanalysis Data

Source: [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=overview)

[How to **authorize** the execution of the Python code on Windows?](https://cds.climate.copernicus.eu/how-to-api) (only once)

- If you do not have an account, please register on the CDS registration page.
- Log in.
- Copy the code with your personal key into the file "USER/.cdsapirc" (in Windows environment)
  > The file starting with a dot can be created using Notepad: File > Save as > Type: All files > File name: .cdsfapirc

Once you have completed the steps above, the ERA5 data can be downloaded using the functions inside `ccee/era5.py`.

**Variables**:

- `temperature`: Hourly near-surface air temperature data from ERA5-Land, in degrees Celsius.

### Eurostat - Population and Mortality

Source: [Eurostat](https://ec.europa.eu/eurostat/web/health/database)

The Eurostat data can be downloaded directly from the website. Use the functions in `ccee/eurostat.py` to automate the process.

**Variables:**

- `population_density`: Yearly population density data. People per square kilometer. Eurostat ID: "demo_r_d3dens". Coverage: 2000 - today.
- `population`: Yearly population data. Eurostat IDs: "tps00001" (country level, NUTS-2), "demo_r_pjanaggr3" (region level, NUTS-3). Coverage: 2014 - today. When not covered, we estimate it from the `population_density` and the country area.
- `mortality`: Weekly number of total deaths by any cause. Eurostat ID: "demo_r_mwk3_t". Coverage: 2000 - today.
- `mortality_rate`: Weekly mortality rate per 100,000 inhabitants. This value is derived from `mortality` and `population`.

### European Environment Agency (EEA)

Source: [European Air Quality Portal](https://aqportal.discomap.eea.europa.eu/download-data/)

Air quality data can be downloaded from the EEA portal. The functions in `ccee/eea.py` call EEA's API to automate the process.

**Variables:**

- `O3`: Ozone (O3) concentration in the air, measured in micrograms per cubic meter (µg/m³).
- `NOx`: Nitrogen oxides (NOx) concentration in the air, measured in micrograms per cubic meter (µg/m³).
- `pm10`: Particulate matter (PM10) concentration in the air, measured in micrograms per cubic meter (µg/m³).

## License

This project is licensed under the [MIT License](LICENSE), permitting reuse with attribution. Feel free to fork and adapt for academic or personal use.

## Contacts

For questions or suggestions, feel free to reach out:

- **GitHub**: [@daniprec](https://github.com/daniprec)
- **Email**: [daniel.precioso@ie.edu](mailto:daniel.precioso@ie.edu)

We welcome feedback and contributions-help us grow this project!

[Back to top](#top)
