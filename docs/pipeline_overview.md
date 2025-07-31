# Data-Pipeline Overview

This document summarises how external datasets flow through the repository
—from raw downloads in `data/` to the analysis products served by the Flask
application.

---

## 1 . High-level diagram

```mermaid
flowchart TD
    %% 1 ▸ Extraction %%
    subgraph Extract
        ERA5_TEMP["ERA5-Land temperature<br>(hourly, 0.25 deg)"]
        EUROSTAT_MORT["Eurostat weekly mortality<br>(NUTS-3)"]
        EEA_AQ["EEA air-quality<br>(PM₂.₅, NO₂, O₃)"]
        POP_DENS["Eurostat population-density<br>(NUTS-3)"]
    end

    %% 2 ▸ Raw storage %%
    subgraph DataDir
        RAWDIR["data/star/raw files"]
    end

    %% 3 ▸ Transform %%
    subgraph Transform
        REGRID["Re-grid / aggregate<br>ERA5 → weekly q05-q50-q95"]
        JOIN["Join with population<br>→ mortality rates"]
        QC["Quality control<br>& completeness checks"]
    end

    %% 4 ▸ Modelling %%
    subgraph Model
        DLNM["Fit DLNM & derive<br>Relative-Risk curves"]
        FORECAST["Scenario projections<br>(SSP2-4.5 / SSP5-8.5)"]
    end

    %% 5 ▸ Serving %%
    subgraph Serve
        CACHE["data/processed/star"]
        API["Flask REST API"]
        MAP["Interactive dashboard"]
    end

    ERA5_TEMP --> RAWDIR
    EUROSTAT_MORT --> RAWDIR
    EEA_AQ --> RAWDIR
    POP_DENS --> RAWDIR
    RAWDIR --> REGRID --> JOIN --> QC --> DLNM --> FORECAST --> CACHE --> API --> MAP
```

---

## 2 . Stage descriptions

| Stage           | Folder(s) in repo                                                                                                    | Main tools                                 |
| --------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Extract**     | `data/era5-land/`, `data/eurostat/`, `data/eea/`, `data/pop_density/`                                                | `cdsapi`, `requests`, `scripts/download_*` |
| **Raw storage** | Same `data/…` sub-folders; original GRIB/CSV/ZIP kept for reproducibility.                                           | —                                          |
| **Transform**   | Temporary NetCDF / Parquet in `data/interim/`; final weekly tables in `data/processed/`.                             | `xarray`, `pandas`, `geopandas`            |
| **Model**       | `scripts/rr_curve.py`, outputs saved to `data/processed/rr_curves/`.                                                 | `statsmodels`, `numpy`                     |
| **Serve**       | Flask reads pre-computed tables in `data/processed/`; JS front-end (Chart.js + Leaflet) renders map and time-series. | Flask, Folium, Chart.js                    |

---

## 3 . Update cadence & storage footprint

| Dataset               | Refresh lag | Script                       | Typical size |
| --------------------- | ----------- | ---------------------------- | ------------ |
| ERA5-Land temperature | \~5 days    | `scripts/era5_download.py`   | 1.2 GB / yr  |
| Eurostat mortality    | 2–3 weeks   | `scripts/get_mortality.py`   | 25 MB / yr   |
| EEA air-quality       | 1 day       | `scripts/get_air_quality.py` | 10 MB / yr   |
| Population density    | Annual      | `scripts/get_population.py`  | 5 MB         |

---

## 4 . Folder tree (current repo)

```
.
├── data/
│   ├── era5-land/            # raw GRIBs  (.grib)
│   ├── eurostat/             # weekly mortality CSV
│   ├── eea/                  # daily air-quality CSV
│   ├── pop_density/          # GeoTIFF / CSV
│   ├── interim/              # temp files during processing
│   └── processed/
│       ├── weekly/           # weekly aggregated tables (.parquet)
│       └── rr_curves/        # model outputs (.json / .parquet)
├── scripts/                  # ETL + modelling
└── app.py                    # Flask server
```

---

### Last updated · 2025-07-31
