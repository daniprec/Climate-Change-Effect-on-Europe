<a name="top"></a>
[![Language](https://img.shields.io/badge/language-Python-3776AB)](https://www.python.org/)
[![Last Commit](https://img.shields.io/github/last-commit/daniprec/flask-demo)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](#)
[![Flask](https://img.shields.io/badge/framework-Flask-000000?logo=flask)](https://flask.palletsprojects.com/)
[![Folium](https://img.shields.io/badge/map-viz--Folium-77B829)](https://python-visualization.github.io/folium/)

⭐ Star this project - it helps others discover it and supports development!

## 🌍 Map Visualization with Flask and Folium

This Flask application visualizes European population, mortality, and temperature data interactively on a map. It supports multi-scale zoom and analysis, with additional granularity for Vienna at the NUTS-3 level.

## 📑 Table of Contents

- [About](#-about)
- [How to Build](#-how-to-build)
- [How to Download Data](#-how-to-download-data)
- [License](#-license)
- [Contacts](#-contacts)

## 🚀 About

This project provides an interactive dashboard using **Flask** and **Folium** to explore the Climate Change Effect on Europe (CCEE):

- **Population & Mortality**: Monthly data per capita, visualized regionally.
- **Temperature (tas)**: Monthly near-surface air temperature data.
- Vienna supports detailed NUTS-3 level analysis.

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

### 🌡️ CORDEX - CMIP (Climate Projections)

Source: [ESGF Data Browser (LiU Node)](https://esg-dn1.nsc.liu.se/search/esgf-liu/)

**Step-by-step**:

1. Register to access the ESGF data.
2. Search with the following filters:
   - **Project**: CORDEX
   - **Experiment**: rcp85
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

🧠 **Tip**: You'll need a Linux-based system (e.g., Ubuntu) to execute WGET scripts.

## 📃 License

This project is licensed under the [MIT License](LICENSE), permitting reuse with attribution. Feel free to fork and adapt for academic or personal use.

## 🗨️ Contacts

For questions or suggestions, feel free to reach out:

- **GitHub**: [@daniprec](https://github.com/daniprec)
- **Email**: daniel.precioso@ie.edu

We welcome feedback and contributions-help us grow this project!

[Back to top](#top)
