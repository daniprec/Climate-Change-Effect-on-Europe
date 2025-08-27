# Data-Pipeline Overview

This document summarises how external datasets flow through the repository, from raw downloads in `data/` to the analysis products served by the Flask application.

---

## 1 . High-level diagram

```mermaid
flowchart TD

    %% 1 ▸ Extraction scripts / API calls %%
    subgraph Extract
        ERA5_DL["era5.py<br>downloads monthly *.nc"]
        CORDEX_DL["wget.sh<br>(CORDEX *.nc)"]
        EUROSTAT_API["eurostat.py<br>(direct API)"]
        EEA_API["eea.py<br>(direct API)"]
    end

    %% 2 %%
    subgraph Raw Data
        ERA5_DIR["data/era5_land<br>(hourly .nc)"]
        CORDEX_DIR["data/rcp45  /  data/rcp85<br>(monthly .nc)"]
    end

    %% 3 ▸ Transformation %%
    subgraph Transform
        BUILD_CSV["build_csv.py<br>+ era5.py / cordex.py / eurostat.py / eea.py"]
        CSV_TABLES["europe.csv & austria.csv"]
    end

    %% 4 ▸ Modelling %%
    subgraph Model
        DLNM["DLNM fitting<br>(Relative-Risk curves)"]
        FORECAST["Scenario projections<br>(SSP2-4.5 / SSP5-8.5)"]
    end

    %% 5 ▸ Serving %%
    subgraph Serve
        API["Flask REST API"]
        DASH["Interactive dashboard"]
    end

    %% ——— Edges ——— %%
    ERA5_DL  --> ERA5_DIR
    CORDEX_DL --> CORDEX_DIR

    ERA5_DIR  --> BUILD_CSV
    CORDEX_DIR --> BUILD_CSV
    EUROSTAT_API --> BUILD_CSV
    EEA_API      --> BUILD_CSV

    BUILD_CSV --> CSV_TABLES
    CSV_TABLES --> DLNM --> FORECAST --> API --> DASH
```

---

## 2 . Stage descriptions

| Stage        | Folder(s) in repo                                                                                          | Main tools                      |
| ------------ | ---------------------------------------------------------------------------------------------------------- | ------------------------------- |
| **Download** | `scripts/era5.py`, `data/rcp/wget.sh`,                                                                     | `cdsapi`, `wget`, `requests`    |
| **Process**  | Done by `scripts/build_csv.py` and stored in `data/europe.csv` and regional csv files                      | `xarray`, `pandas`, `geopandas` |
| **Model**    | `ccee/rr_curve.py`                                                                                         | `statsmodels`, `numpy`          |
| **Serve**    | Flask reads pre-computed tables in `data/`; JS front-end (Chart.js + Leaflet) renders map and time-series. | Flask, Folium, Chart.js         |

---

## 3 . Folder tree (current repo)

```text
.
├── data/
│   ├── era5-land/            # raw ERA5 hourly NetCDF files
│   ├── rcp45/               # raw CORDEX RCP4.5 NetCDF files
│   ├── rcp85/               # raw CORDEX RCP8.5 NetCDF files
│   ├── europe.csv          # processed Europe-wide weekly table
│   ├── austria.csv         # processed Austria-wide weekly table
├── scripts/                  # ETL + modelling
└── app.py                    # Flask server
```

---

For more details on each stage, see the following document: [Pipeline Details](pipeline_details.md).

---
