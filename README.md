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
├── data/ # Input and downloaded data
├── scripts/ # Data processing scripts
├── static/ # JS, CSS, assets
├── templates/ # HTML views
├── app.py # Flask server
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

**Pipeline overview diagram** – [`docs/pipeline_overview.md`](docs/pipeline_overview.md)

**Step-by-step data & script details** – [`docs/pipeline_details.md`](docs/pipeline_details.md)

## License

This project is licensed under the [MIT License](LICENSE), permitting reuse with attribution. Feel free to fork and adapt for academic or personal use.

## Contacts

For questions or suggestions, feel free to reach out:

- **GitHub**: [@daniprec](https://github.com/daniprec)
- **Email**: [daniel.precioso@ie.edu](mailto:daniel.precioso@ie.edu)

We welcome feedback and contributions-help us grow this project!

[Back to top](#top)
