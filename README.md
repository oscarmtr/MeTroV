# MeTroV

Interactive web application for visualizing atmospheric soundings (radiosondes) using data from **IGRA (NOAA)** and **University of Wyoming (UWYO)**.

The app allows users to search stations by city or airport name, select date and time, and generate both **static (MetPy)** and **interactive (Plotly)** Skew-T diagrams, along with key thermodynamic indices commonly used in meteorology.

---

## 🚀 Features

- Global radiosonde station catalog with city/airport-based search
- Multiple data sources:
  - **IGRA** (Integrated Global Radiosonde Archive – NOAA)
  - **UWYO** (University of Wyoming Weather Web)
  - Automatic fallback between sources
- Automatic detection of available synoptic hours
- Skew-T Log-P diagrams:
  - Static plots using **MetPy**
  - Interactive plots using **Plotly**
- Thermodynamic diagnostics:
  - LCL (Lifted Condensation Level)
  - LFC (Level of Free Convection)
  - EL (Equilibrium Level)
  - CAPE and CIN
- Direct links to the original data source used for each sounding

---

## 📂 Project Structure

```text
MeTroV/
│
├── data/
│   └── igra_stations_active.csv      # Station catalog (auto-generated)
│
├── scripts/
│   └── build_igra_station_list.py # Script to generate station catalog
│
├── src/
│   ├── app.py                     # Streamlit application
│   ├── stations.py                # Station search and automatic list updates
│   ├── sondeo.py                  # Sounding retrieval logic (IGRA / UWYO)
│   ├── sondeo_plotly.py           # Interactive Skew-T (Plotly)
│   └── sounding_sources.py        # Data source definitions
│
├── .gitignore                     # Git exclusion rules
├── LICENSE                        # GNU AGPLv3 License
├── requirements.txt               # Python dependencies
└── README.md                      # Project documentation
```

---

## ▶️ Run the App Locally

1. Clone the repository:

```bash
git clone https://github.com/oscarmtr/MeTroV.git
cd MeTroV
```

1. Install dependencies:

```bash
pip install -r requirements.txt
```

1. Launch the app:

```bash
streamlit run src/app.py
```

---

## 📄 License

This project is licensed under a **Dual License** model:

### 💻 Source Code

The source code (software logic, scripts, Python files) is licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**.
> See [LICENSE](LICENSE) for details.

### 📊 Content & Data Visualization

The generated content, visualizations, and website presentation are licensed under **[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/)**.

**Summary**:

- You are free to view, share, and adapt the visualizations for non-commercial purposes with attribution.

- If you modify the *software code*, especially if you run it as a service, you must share your changes under the same AGPLv3 license.

---

## 📚 References

- Durre, I., Yin, X., Vose, R. S., Applequist, S., Arnfield, J., Korzeniewski, B., & Hundermark, B. (2016). *Integrated Global Radiosonde Archive (IGRA), Version 2*. NOAA National Centers for Environmental Information. <https://doi.org/10.7289/V5X63K0Q>
- Harris, C. R., et al. (2020). Array programming with NumPy. *Nature*, *585*(7825), 357–362. <https://doi.org/10.1038/s41586-020-2649-2>
- Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. *Computing in Science & Engineering*, *9*(3), 90–95.
- May, R. M., Goebbert, K. H., Thielen, J. E., Leeman, J. R., Camron, M. D., Bruick, Z., Bruning, E. C., Manser, R. P., Arms, S. C., & Marsh, P. T. (2022). MetPy: A Meteorological Python Library for Data Analysis and Visualization. *Bulletin of the American Meteorological Society*, *103*(10), E2273–E2284. <https://doi.org/10.1175/BAMS-D-21-0125.1>
- McKinney, W. (2010). Data structures for statistical computing in python. In S. van der Walt & J. Millman (Eds.), *Proceedings of the 9th Python in Science Conference* (pp. 56–61).
- Plotly Technologies Inc. (2024). *Plotly.PY* [Computer software]. Retrieved from <https://plotly.com/python/>
- Streamlit Inc. (n.d.). *Streamlit* [Computer software]. Retrieved from <https://streamlit.io>
- The pandas development team. (2020). *pandas-dev/pandas: Pandas* [Computer software]. Zenodo. <https://doi.org/10.5281/zenodo.3509134>
- University of Wyoming, Department of Atmospheric Science. (n.d.). *Wyoming Weather Web*. Retrieved January 19, 2026, from <http://www.atmos.uwyo.edu/weather/>
