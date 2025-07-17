<a name="top"></a>
[![Language](https://img.shields.io/badge/language-Python-3776AB)](https://www.python.org/)
[![Last Commit](https://img.shields.io/github/last-commit/daniprec/flask-demo)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](#)
[![Flask](https://img.shields.io/badge/framework-Flask-000000?logo=flask)](https://flask.palletsprojects.com/)
[![Folium](https://img.shields.io/badge/map-viz--Folium-77B829)](https://python-visualization.github.io/folium/)

⭐ Star this project - it helps others discover it and supports development!

## 🌍 Map Visualization with Flask and Folium

This Flask application visualizes European population, mortality, and temperature data interactively on a map. It supports multi-scale zoom and analysis, with additional granularity for Vienna at the NUTS-3 level.

It is hosted on [Python Anywhere](https://ixlabs-daniprec.pythonanywhere.com/) for easy access and exploration.

## 📑 Table of Contents

- [About](#-about)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [How to Build](#-how-to-build)
- [How to Download Data](#-how-to-download-data)
- [License](#-license)
- [Contacts](#-contacts)

## 🚀 About

This project provides an interactive dashboard using **Flask** and **Folium** to explore the Climate Change Effect on Europe (CCEE):

- **Population & Mortality**: Monthly data per capita, visualized regionally.
- **Temperature (tas)**: Monthly near-surface air temperature data.
- Vienna supports detailed NUTS-3 level analysis.

## ✨ Features

- Interactive map with zoom and tooltip support
- Time-series visualization by region
- Population-normalized mortality overlays
- NUTS-level granularity (with detailed view for Vienna)
- Responsive Flask backend with pre-processed data cache

## 📁 Project Structure

```
├── app.py # Flask server
├── templates/ # HTML views
├── static/ # JS, CSS, assets
├── scripts/ # Data processing scripts
├── data/ # Input and downloaded data
├── requirements.txt
└── README.md
```

## 🛠️ How to Build

Clone the repo and install dependencies:

```bash
pip install -r requirements.txt
```

Start the Flask server:

```bash
python app.py
```

Then open your browser at [http://127.0.0.1:5000/](http://127.0.0.1:5000/) to begin exploring the map.

## 📥 How to Download Data

Most of the data used in this project is available through public APIs or data portals. You can build the files used by the map just by running:

```bash
python scripts/build_geojson.py
python scripts/build_csv.py
```

The only data that needs to be downloaded manually is the CORDEX CMIP data, which requires a WGET script. Below are the instructions for downloading and preparing the data.

### 🌡️ CORDEX - CMIP (Climate Projections)

Source: [ESGF Data Browser (LiU Node)](https://esg-dn1.nsc.liu.se/search/esgf-liu/)

Official tutorial [link](https://cordex.org/wp-content/uploads/2023/08/How-to-download-CORDEX-data-from-the-ESGF.pdf)

**Step-by-step**:

1. Register to access the ESGF data.
2. Search with the following filters:
   - **Project**: CORDEX
   - **Experiment**: rcp85 OR rcp45
   - **Variable**: tas (air temperature)
   - **Domain**: EUR-11
   - **Time Frequency**: mon
3. Select a dataset, e.g.:
   ```
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

### 👥 Eurostat - Population and Mortality

Source: [Eurostat](https://ec.europa.eu/eurostat/web/health/database)

The Eurostat data can be downloaded directly from the website. Use the functions in `ccee/eurostat.py` to automate the process.

**Variables:**

- `population_density`: Yearly population density data. People per square kilometer.
- `mortality_rate`: Weekly mortality rate per 100,000 inhabitants.

### 🌍 European Environment Agency (EEA)

Source: [European Air Quality Portal](https://aqportal.discomap.eea.europa.eu/download-data/)

Air quality data can be downloaded from the EEA portal. The functions in `ccee/eea.py` call EEA's API to automate the process.

**Variables:**

- `O3`: Ozone (O3) concentration in the air, measured in micrograms per cubic meter (µg/m³).
- `NOx`: Nitrogen oxides (NOx) concentration in the air, measured in micrograms per cubic meter (µg/m³).
- `pm10`: Particulate matter (PM10) concentration in the air, measured in micrograms per cubic meter (µg/m³).

## 📃 License

This project is licensed under the [MIT License](LICENSE), permitting reuse with attribution. Feel free to fork and adapt for academic or personal use.

## 🗨️ Contacts

For questions or suggestions, feel free to reach out:

- **GitHub**: [@daniprec](https://github.com/daniprec)
- **Email**: daniel.precioso@ie.edu

We welcome feedback and contributions-help us grow this project!

[Back to top](#top)
