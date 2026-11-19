# src/app.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
from PIL import Image

# Suppress DecompressionBombWarning for high-res plots requested by user
Image.MAX_IMAGE_PIXELS = None

import warnings
warnings.filterwarnings('ignore', message='.*Duplicate pressure.*')

import pathlib
import importlib
from stations import find_station, update_station_list
import sounding_plotly
importlib.reload(sounding_plotly)
from sounding_plotly import create_skewt_plotly
from metpy.plots import SkewT, Hodograph
from matplotlib.patches import Patch
import matplotlib.pyplot as plt
import metpy.calc as mpcalc
from metpy.units import units
from interpretation_text import get_interpretation_text
import sondehub_service
importlib.reload(sondehub_service)
from sondehub_service import (
    get_active_sondes,
    get_live_sounding,
    get_sonde_trajectory,
    get_launch_sites,
    find_nearest_site,
    extract_country_city,
)
import plotly.graph_objects as go

st.set_page_config(page_title="MeTroV", layout="centered")

# Default Dark Mode to False (light mode & default OpenStreetMap map by default)
if 'dark_mode' not in st.session_state:
    st.session_state['dark_mode'] = False

# Update station list on session start
if 'station_list_updated' not in st.session_state:
     with st.spinner("Updating station list (downloading from IGRA)..."):
         update_station_list(force=True)
         pass # La variable global se actualiza dentro de stations.py
     st.session_state['station_list_updated'] = True

st.title("Meteorological Sounding Viewer")

with st.sidebar:
    st.markdown("## ℹ️ About")
    st.markdown(
        """
        **[MeTroV](https://github.com/oscarmtr/MeTroV.git)**

        Developed by **[Óscar Mata-Romero](https://github.com/oscarmtr)**  

        **Data sources**
        - NOAA Integrated Global Radiosonde Archive (IGRA)
        - University of Wyoming Sounding Archive
        - SondeHub Global Radiosonde Live Telemetry

        **Purpose**
        Research and educational use.

        ---
        """
    )
    st.markdown("## Appearance")
    is_dark_mode = st.toggle("🌙 Dark mode", key="dark_mode")
    # st.markdown("### 📖 How to cite")
    # st.code(
    #     "Óscar Mata-Romero (2026). Meteorological Sounding Viewer. "
    #     "Radiosonde data from NOAA IGRA & University of Wyoming."
    # )

# Apply Dark / Light Mode CSS dynamically based on the toggle
if st.session_state.get('dark_mode', False):
    st.markdown(
        """
        <style>
        :root, .stApp {
            --text-color: #fafafa !important;
            --background-color: #0e1117 !important;
            --secondary-background-color: #262730 !important;
            background-color: #0e1117 !important;
            color: #fafafa !important;
        }
        /* Top horizontal header bar: 100% opaque so scrolling text never bleeds through */
        [data-testid="stHeader"], [data-testid="stAppHeader"] {
            background-color: #0e1117 !important;
            backdrop-filter: none !important;
            border-bottom: 1px solid rgba(250, 250, 250, 0.08) !important;
        }
        [data-testid="stSidebar"] {
            background-color: #262730 !important;
            color: #fafafa !important;
        }
        .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
        [data-testid="stMarkdownContainer"] > p, [data-testid="stWidgetLabel"] p {
            color: #fafafa !important;
        }
        /* Radio buttons (Simple/Advanced, Source Mode, Hours 12h/9h/6h/3h) */
        label[data-baseweb="radio"] > div:first-of-type {
            background-color: #fafafa !important;
        }
        label[data-baseweb="radio"]:has(input:checked) > div:first-of-type {
            background-color: #ff4b4b !important;
        }
        label[data-baseweb="radio"] > div:first-of-type > div {
            background-color: #0e1117 !important;
        }
        /* Toggle switch (st.toggle uses > div:first-child) */
        label[data-baseweb="checkbox"] > div:first-child {
            background-color: #4b5563 !important;
        }
        label[data-baseweb="checkbox"]:has(input:checked) > div:first-child {
            background-color: #ff4b4b !important;
        }
        label[data-baseweb="checkbox"] > div:first-child > div {
            background-color: #ffffff !important;
        }
        /* Square Checkbox (st.checkbox uses > span:first-child) */
        label[data-baseweb="checkbox"] > span:first-child {
            background-color: transparent !important;
            border-color: rgba(250, 250, 250, 0.45) !important;
        }
        label[data-baseweb="checkbox"]:has(input:checked) > span:first-child {
            background-color: #ff4b4b !important;
            border-color: #ff4b4b !important;
        }
        /* Selectboxes & Date Input field */
        [data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"] {
            background-color: #1e222b !important;
            color: #fafafa !important;
            border-color: rgba(250, 250, 250, 0.22) !important;
        }
        [data-baseweb="select"] div, [data-baseweb="select"] input, [data-baseweb="input"] input {
            color: #fafafa !important;
            -webkit-text-fill-color: #fafafa !important;
        }
        [data-baseweb="select"] svg, [data-testid="stDateInput"] svg {
            fill: #fafafa !important;
            color: #fafafa !important;
        }
        /* Open Dropdown Menus & MainMenu Popover */
        [data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="menu"],
        ul[role="listbox"], [data-testid="stSelectboxVirtualDropdown"],
        [data-testid="stMainMenuPopover"], [data-testid="stMainMenuList"] {
            background-color: #1e222b !important;
            color: #fafafa !important;
            border-color: rgba(250, 250, 250, 0.2) !important;
        }
        li[role="option"], li[role="option"] *,
        [data-testid="stMainMenuList"] *, [data-baseweb="menu"] li, [data-baseweb="menu"] li * {
            background-color: transparent !important;
            color: #fafafa !important;
        }
        li[role="option"]:hover, li[role="option"][aria-selected="true"],
        [data-baseweb="menu"] li:hover {
            background-color: #2d3343 !important;
        }
        /* Calendar popup (header, month/year selectors, weekday row, day grid) */
        [data-baseweb="calendar"],
        [data-baseweb="calendar"] div:not([role="gridcell"]) {
            background-color: #1e222b !important;
            color: #fafafa !important;
        }
        [data-baseweb="calendar"] button {
            background-color: transparent !important;
            color: #fafafa !important;
            border: none !important;
        }
        [data-baseweb="calendar"] button:hover {
            background-color: #2d3343 !important;
        }
        [data-baseweb="calendar"] button svg {
            fill: #fafafa !important;
            color: #fafafa !important;
        }
        [data-baseweb="calendar"] [role="gridcell"] {
            background-color: transparent !important;
            color: #fafafa !important;
        }
        [data-baseweb="calendar"] [role="gridcell"] > div {
            background-color: transparent !important;
            color: #fafafa !important;
        }
        [data-baseweb="calendar"] [role="gridcell"]:not([aria-selected="true"])::before,
        [data-baseweb="calendar"] [role="gridcell"]:not([aria-selected="true"])::after {
            background-color: transparent !important;
        }
        [data-baseweb="calendar"] [role="gridcell"]:not([aria-selected="true"]):hover::after {
            background-color: #2d3343 !important;
        }
        [data-baseweb="calendar"] [role="gridcell"][aria-selected="true"],
        [data-baseweb="calendar"] [role="gridcell"][aria-selected="true"]::after,
        [data-baseweb="calendar"] [role="gridcell"][aria-selected="true"] > div {
            background-color: #ff4b4b !important;
            color: #ffffff !important;
        }
        /* Action & Download buttons */
        .stButton > button, .stDownloadButton > button,
        [data-testid="stDownloadButton"] button, [data-testid="stBaseButton-secondary"] {
            background-color: #1e222b !important;
            color: #fafafa !important;
            border: 1px solid rgba(250, 250, 250, 0.25) !important;
        }
        .stButton > button *, .stDownloadButton > button *,
        [data-testid="stDownloadButton"] button *, [data-testid="stBaseButton-secondary"] * {
            color: #fafafa !important;
        }
        .stButton > button:hover, .stDownloadButton > button:hover,
        [data-testid="stDownloadButton"] button:hover, [data-testid="stBaseButton-secondary"]:hover {
            background-color: #2b303c !important;
            border-color: #ff4b4b !important;
        }
        /* Sidebar expand/collapse & top-right Deploy / 3-dots menu buttons */
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapseButton"] button,
        [data-testid="stBaseButton-header"],
        [data-testid="stBaseButton-headerNoPadding"],
        [data-testid="stToolbar"] button,
        [data-testid="stAppDeployButton"] button,
        [data-testid="stMainMenu"] button {
            background-color: transparent !important;
            color: #fafafa !important;
            border: none !important;
            box-shadow: none !important;
        }
        [data-testid="stExpandSidebarButton"] *,
        [data-testid="stSidebarCollapseButton"] button *,
        [data-testid="stBaseButton-header"] *,
        [data-testid="stBaseButton-headerNoPadding"] *,
        [data-testid="stToolbar"] button *,
        [data-testid="stAppDeployButton"] button *,
        [data-testid="stMainMenu"] button * {
            color: #fafafa !important;
        }
        [data-testid="stExpandSidebarButton"] svg,
        [data-testid="stSidebarCollapseButton"] button svg,
        [data-testid="stBaseButton-header"] svg,
        [data-testid="stBaseButton-headerNoPadding"] svg,
        [data-testid="stToolbar"] button svg,
        [data-testid="stAppDeployButton"] button svg,
        [data-testid="stMainMenu"] button svg {
            fill: #fafafa !important;
            color: #fafafa !important;
        }
        [data-testid="stExpandSidebarButton"]:hover,
        [data-testid="stSidebarCollapseButton"] button:hover,
        [data-testid="stBaseButton-header"]:hover,
        [data-testid="stBaseButton-headerNoPadding"]:hover,
        [data-testid="stToolbar"] button:hover,
        [data-testid="stAppDeployButton"] button:hover,
        [data-testid="stMainMenu"] button:hover {
            background-color: rgba(250, 250, 250, 0.12) !important;
        }
        #copyrightYear {
            color: inherit !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <style>
        :root, .stApp {
            --text-color: #1f2937 !important;
            --background-color: #ffffff !important;
            --secondary-background-color: #f3f4f6 !important;
            background-color: #ffffff !important;
            color: #1f2937 !important;
        }
        /* Top horizontal header bar: 100% opaque so scrolling text never bleeds through */
        [data-testid="stHeader"], [data-testid="stAppHeader"] {
            background-color: #ffffff !important;
            backdrop-filter: none !important;
            border-bottom: 1px solid rgba(31, 41, 55, 0.08) !important;
        }
        [data-testid="stSidebar"] {
            background-color: #f3f4f6 !important;
            color: #1f2937 !important;
        }
        .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
        [data-testid="stMarkdownContainer"] > p, [data-testid="stWidgetLabel"] p {
            color: #1f2937 !important;
        }
        /* Radio buttons (Simple/Advanced, Source Mode, Hours 12h/9h/6h/3h) */
        label[data-baseweb="radio"] > div:first-of-type {
            background-color: #6b7280 !important;
        }
        label[data-baseweb="radio"]:has(input:checked) > div:first-of-type {
            background-color: #ff4b4b !important;
        }
        label[data-baseweb="radio"] > div:first-of-type > div {
            background-color: #ffffff !important;
        }
        /* Toggle switch (st.toggle uses > div:first-child) */
        label[data-baseweb="checkbox"] > div:first-child {
            background-color: #cbd5e1 !important;
        }
        label[data-baseweb="checkbox"]:has(input:checked) > div:first-child {
            background-color: #ff4b4b !important;
        }
        label[data-baseweb="checkbox"] > div:first-child > div {
            background-color: #ffffff !important;
        }
        /* Square Checkbox (st.checkbox uses > span:first-child) */
        label[data-baseweb="checkbox"] > span:first-child {
            background-color: transparent !important;
            border-color: rgba(31, 41, 55, 0.45) !important;
        }
        label[data-baseweb="checkbox"]:has(input:checked) > span:first-child {
            background-color: #ff4b4b !important;
            border-color: #ff4b4b !important;
        }
        /* Selectboxes & Date Input field */
        [data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"] {
            background-color: #f9fafb !important;
            color: #1f2937 !important;
            border-color: rgba(31, 41, 55, 0.22) !important;
        }
        [data-baseweb="select"] div, [data-baseweb="select"] input, [data-baseweb="input"] input {
            color: #1f2937 !important;
            -webkit-text-fill-color: #1f2937 !important;
        }
        [data-baseweb="select"] svg, [data-testid="stDateInput"] svg {
            fill: #1f2937 !important;
            color: #1f2937 !important;
        }
        /* Open Dropdown Menus & MainMenu Popover */
        [data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="menu"],
        ul[role="listbox"], [data-testid="stSelectboxVirtualDropdown"],
        [data-testid="stMainMenuPopover"], [data-testid="stMainMenuList"] {
            background-color: #ffffff !important;
            color: #1f2937 !important;
            border-color: rgba(31, 41, 55, 0.2) !important;
        }
        li[role="option"], li[role="option"] *,
        [data-testid="stMainMenuList"] *, [data-baseweb="menu"] li, [data-baseweb="menu"] li * {
            background-color: transparent !important;
            color: #1f2937 !important;
        }
        li[role="option"]:hover, li[role="option"][aria-selected="true"],
        [data-baseweb="menu"] li:hover {
            background-color: #e5e7eb !important;
        }
        /* Calendar popup (header, month/year selectors, weekday row, day grid) */
        [data-baseweb="calendar"],
        [data-baseweb="calendar"] div:not([role="gridcell"]) {
            background-color: #ffffff !important;
            color: #1f2937 !important;
        }
        [data-baseweb="calendar"] button {
            background-color: transparent !important;
            color: #1f2937 !important;
            border: none !important;
        }
        [data-baseweb="calendar"] button:hover {
            background-color: #e5e7eb !important;
        }
        [data-baseweb="calendar"] button svg {
            fill: #1f2937 !important;
            color: #1f2937 !important;
        }
        [data-baseweb="calendar"] [role="gridcell"] {
            background-color: transparent !important;
            color: #1f2937 !important;
        }
        [data-baseweb="calendar"] [role="gridcell"] > div {
            background-color: transparent !important;
            color: #1f2937 !important;
        }
        [data-baseweb="calendar"] [role="gridcell"]:not([aria-selected="true"])::before,
        [data-baseweb="calendar"] [role="gridcell"]:not([aria-selected="true"])::after {
            background-color: transparent !important;
        }
        [data-baseweb="calendar"] [role="gridcell"]:not([aria-selected="true"]):hover::after {
            background-color: #e5e7eb !important;
        }
        [data-baseweb="calendar"] [role="gridcell"][aria-selected="true"],
        [data-baseweb="calendar"] [role="gridcell"][aria-selected="true"]::after,
        [data-baseweb="calendar"] [role="gridcell"][aria-selected="true"] > div {
            background-color: #ff4b4b !important;
            color: #ffffff !important;
        }
        /* Action & Download buttons */
        .stButton > button, .stDownloadButton > button,
        [data-testid="stDownloadButton"] button, [data-testid="stBaseButton-secondary"] {
            background-color: #ffffff !important;
            color: #1f2937 !important;
            border: 1px solid rgba(31, 41, 55, 0.25) !important;
        }
        .stButton > button *, .stDownloadButton > button *,
        [data-testid="stDownloadButton"] button *, [data-testid="stBaseButton-secondary"] * {
            color: #1f2937 !important;
        }
        .stButton > button:hover, .stDownloadButton > button:hover,
        [data-testid="stDownloadButton"] button:hover, [data-testid="stBaseButton-secondary"]:hover {
            background-color: #f3f4f6 !important;
            border-color: #ff4b4b !important;
        }
        /* Sidebar expand/collapse & top-right Deploy / 3-dots menu buttons */
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapseButton"] button,
        [data-testid="stBaseButton-header"],
        [data-testid="stBaseButton-headerNoPadding"],
        [data-testid="stToolbar"] button,
        [data-testid="stAppDeployButton"] button,
        [data-testid="stMainMenu"] button {
            background-color: transparent !important;
            color: #1f2937 !important;
            border: none !important;
            box-shadow: none !important;
        }
        [data-testid="stExpandSidebarButton"] *,
        [data-testid="stSidebarCollapseButton"] button *,
        [data-testid="stBaseButton-header"] *,
        [data-testid="stBaseButton-headerNoPadding"] *,
        [data-testid="stToolbar"] button *,
        [data-testid="stAppDeployButton"] button *,
        [data-testid="stMainMenu"] button * {
            color: #1f2937 !important;
        }
        [data-testid="stExpandSidebarButton"] svg,
        [data-testid="stSidebarCollapseButton"] button svg,
        [data-testid="stBaseButton-header"] svg,
        [data-testid="stBaseButton-headerNoPadding"] svg,
        [data-testid="stToolbar"] button svg,
        [data-testid="stAppDeployButton"] button svg,
        [data-testid="stMainMenu"] button svg {
            fill: #1f2937 !important;
            color: #1f2937 !important;
        }
        [data-testid="stExpandSidebarButton"]:hover,
        [data-testid="stSidebarCollapseButton"] button:hover,
        [data-testid="stBaseButton-header"]:hover,
        [data-testid="stBaseButton-headerNoPadding"]:hover,
        [data-testid="stToolbar"] button:hover,
        [data-testid="stAppDeployButton"] button:hover,
        [data-testid="stMainMenu"] button:hover {
            background-color: rgba(31, 41, 55, 0.08) !important;
        }
        #copyrightYear {
            color: inherit !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# Parameterized CSS for widget help (?) icons & tooltip popovers across both themes
_is_dark_tt = st.session_state.get('dark_mode', False)
_tt_bg = "#1e222b" if _is_dark_tt else "#ffffff"
_tt_fg = "#fafafa" if _is_dark_tt else "#1f2937"
_tt_border = "rgba(250, 250, 250, 0.22)" if _is_dark_tt else "rgba(31, 41, 55, 0.16)"
_tt_shadow = "0 4px 16px rgba(0, 0, 0, 0.45)" if _is_dark_tt else "0 4px 14px rgba(0, 0, 0, 0.12)"
_tt_icon = "rgba(250, 250, 250, 0.72)" if _is_dark_tt else "rgba(31, 41, 55, 0.65)"
st.markdown(
    f"""
    <style>
    [data-testid="stTooltipIcon"] svg, .stTooltipHoverTarget svg.icon {{
        stroke: {_tt_icon} !important;
        color: {_tt_icon} !important;
        fill: none !important;
    }}
    [data-testid="stTooltipIcon"]:hover svg, .stTooltipHoverTarget:hover svg.icon {{
        stroke: {_tt_fg} !important;
        color: {_tt_fg} !important;
        fill: none !important;
    }}
    [data-baseweb="tooltip"] {{
        background-color: transparent !important;
    }}
    [data-baseweb="tooltip"] > div {{
        background-color: {_tt_bg} !important;
        color: {_tt_fg} !important;
        border: 1px solid {_tt_border} !important;
        border-radius: 0.5rem !important;
        box-shadow: {_tt_shadow} !important;
        overflow: hidden !important;
    }}
    [data-testid="stTooltipContent"] {{
        background-color: {_tt_bg} !important;
        color: {_tt_fg} !important;
    }}
    [data-baseweb="tooltip"] *,
    [data-testid="stTooltipContent"] *,
    [data-testid="stTooltipContent"] p,
    [data-testid="stTooltipContent"] [data-testid="stMarkdownContainer"] > p {{
        color: {_tt_fg} !important;
        -webkit-text-fill-color: {_tt_fg} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

import requests
import zipfile
from io import StringIO

# =====================================
# LECTURA SONDEO IGRA
# =====================================
def lecturaSondeoIGRA(CodEst, yr, mn, dy, hr):
    url = (
        "https://www.ncei.noaa.gov/data/"
        "integrated-global-radiosonde-archive/access/data-por/"
        f"{CodEst}-data.txt.zip"
    )

    r = requests.get(url, timeout=30)
    r.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        fname = z.namelist()[0]
        lines = z.read(fname).decode("utf-8").splitlines()

    target_time = f"{yr} {mn} {dy} {hr}"

    p_list, T_list, Td_list = [], [], []
    wdir_list, wspd_list = [], []
    
    reading = False
    n_expected = 0
    n_read = 0

    for line in lines:
        if line.startswith("#"):
            time = line[13:26]
            nlines = int(line[32:36])
            reading = (time == target_time)
            n_expected = nlines if reading else 0
            n_read = 0
            continue

        if not reading or n_read >= n_expected:
            continue

        try:
            pres = int(line[9:15])
            temp = int(line[22:27])
            dtd  = int(line[34:39])
            wdir = int(line[40:45])
            wspd = int(line[46:51])
        except ValueError:
            n_read += 1
            continue

        if pres < 0 or temp < -900:
            n_read += 1
            continue

        pres_val = pres / 100.0
        temp_val = temp / 10.0
        
        if dtd < -900:
            td_val = np.nan
        else:
            td_val = (temp - dtd) / 10.0

        if wdir < -900 or wspd < -900:
            wdir_val = np.nan
            wspd_val = np.nan
        else:
            wdir_val = float(wdir)
            wspd_val = float(wspd) / 10.0
            
        p_list.append(pres_val)
        T_list.append(temp_val)
        Td_list.append(td_val)
        wdir_list.append(wdir_val)
        wspd_list.append(wspd_val)

        n_read += 1

    if len(p_list) < 10:
        raise ValueError("IGRA sounding not available")

    p = np.array(p_list) * units.hPa
    T = np.array(T_list) * units.degC
    Td = np.array(Td_list) * units.degC
    
    wdir = np.array(wdir_list) * units.degrees
    wspd = np.array(wspd_list) * units('m/s')
    
    u, v = mpcalc.wind_components(wspd, wdir)

    idx = np.argsort(p.magnitude)[::-1]
    
    return p[idx], T[idx], Td[idx], u[idx], v[idx]


# =====================================
# LECTURA SONDEO UWYO
# =====================================
def lecturaSondeoUWyo(CodEst_WMO, yr, mn, dy, hr):
    sources = ["FM35", "BUFR"]
    last_exception = None

    for src in sources:
        try:
            url = (
                "https://weather.uwyo.edu/wsgi/sounding?"
                f"datetime={yr}-{mn}-{dy}%20{hr}:00:00&id={CodEst_WMO}&type=TEXT:CSV&src={src}"
            )

            r = requests.get(url, timeout=30)
            r.raise_for_status()
            csv_text = r.text

            df = pd.read_csv(StringIO(csv_text))

            if df.empty or "pressure" not in str(df.columns).lower():
                 raise ValueError(f"Invalid or empty response with src={src}")

            def get_col(candidates):
                for c in candidates:
                    if c in df.columns:
                        return df[c], c
                raise KeyError(f"Ninguna de las columnas {candidates} encontrada")

            try:
                p_col, _ = get_col(['pressure', 'pressure_hPa', 'pres'])
                p = pd.to_numeric(p_col, errors='coerce')
                
                T_col, _ = get_col(['temperature', 'temperature_C', 'temp'])
                T = pd.to_numeric(T_col, errors='coerce')

                Td_col, _ = get_col(['dew point', 'dew point temperature_C', 'dwpt'])
                Td = pd.to_numeric(Td_col, errors='coerce')

                wdir_col, _ = get_col(['direction', 'wind direction_degree', 'drct'])
                wdir = pd.to_numeric(wdir_col, errors='coerce')

                wspd_raw_col, wspd_col_name = get_col(['speed', 'wind speed_m/s', 'sknt', 'wind speed_kn'])
                wspd = pd.to_numeric(wspd_raw_col, errors='coerce')
                
                if 'm/s' in wspd_col_name:
                    wind_units = units('m/s')
                elif 'kn' in wspd_col_name or 'sknt' in wspd_col_name:
                    wind_units = units.knots
                else:
                    wind_units = units.knots

            except KeyError as e:
                 cols_found = df.columns.tolist()
                 snippet = csv_text[:200].replace('\n', ' ')
                 raise ValueError(f"Formato UWyo inesperado o columna faltante ({e}). Columnas encontradas: {cols_found}. Inicio contenido: {snippet}")

            mask = (~p.isna()) & (~T.isna())
            
            p_clean = p[mask].to_numpy() * units.hPa
            T_clean = T[mask].to_numpy() * units.degC
            Td_clean = Td[mask].to_numpy() * units.degC
            
            wdir_clean = wdir[mask].to_numpy() * units.degrees
            wspd_clean = wspd[mask].to_numpy() * wind_units
            
            u, v = mpcalc.wind_components(wspd_clean, wdir_clean)

            if len(p_clean) == 0:
                raise ValueError("UWyo sounding not available or empty after filtering")

            idx = np.argsort(p_clean.magnitude)[::-1]
            return p_clean[idx], T_clean[idx], Td_clean[idx], u[idx], v[idx], f"UWYO-{src}"

        except Exception as e:
            last_exception = e
            continue

    raise ValueError(f"Could not download UWyo sounding with any source. Last error: {last_exception}")

# =====================================
# GESTOR DE FUENTES
# =====================================
def get_sounding(CodEst, yr, mn, dy, hr, source_mode="IGRA"):
    source_mode = source_mode.upper()
    if source_mode not in ("IGRA", "UWYO", "AUTO"):
        raise ValueError("source_mode must be IGRA, UWYO or Auto")

    if source_mode == "IGRA":
        return lecturaSondeoIGRA(CodEst, yr, mn, dy, hr), "IGRA"

    if source_mode == "UWYO":
        wmo = CodEst[-5:]
        data_tuple = lecturaSondeoUWyo(wmo, yr, mn, dy, hr)
        return data_tuple[:5], data_tuple[5]

    try:
        return lecturaSondeoIGRA(CodEst, yr, mn, dy, hr), "IGRA"
    except Exception:
        wmo = CodEst[-5:]
        data_tuple = lecturaSondeoUWyo(wmo, yr, mn, dy, hr)
        return data_tuple[:5], data_tuple[5]




# =====================================
# CALCULO DE NIVELES E INDICES TERMODINAMICOS
# =====================================
def calculate_thermo_levels(p, T, Td):
    # Ensure Td is in degC (not delta_degC) and find first valid level with p, T, Td
    T = T.to(units.degC)
    Td = Td.to(units.degC)
    valid_start = np.where((~np.isnan(p.magnitude)) & (~np.isnan(T.magnitude)) & (~np.isnan(Td.magnitude)))[0]
    i0 = int(valid_start[0]) if len(valid_start) > 0 else 0

    try:
        lcl_p, lcl_T = mpcalc.lcl(p[i0], T[i0], Td[i0])
    except Exception:
        lcl_p, lcl_T = np.nan * units.hPa, np.nan * units.degC

    try:
        parcel_prof = mpcalc.parcel_profile(p, T[i0], Td[i0]).to(units.degC)
    except Exception:
        parcel_prof = np.full(len(p), np.nan) * units.degC

    try:
        lfc_p, _ = mpcalc.lfc(p, T, Td, parcel_prof, which='bottom')
    except Exception:
        lfc_p = np.nan * units.hPa
    try:
        ccl_p, ccl_T, ccl_Tc = mpcalc.ccl(p, T, Td, which='bottom')
    except Exception:
        ccl_p = np.nan * units.hPa
    try:
        el_p, _ = mpcalc.el(p, T, Td, parcel_prof, which='bottom')
    except Exception:
        el_p = np.nan * units.hPa

    try:
        el_p_top, _ = mpcalc.el(p, T, Td, parcel_prof, which='top')
    except Exception:
        el_p_top = None

    if not pd.isna(lfc_p.magnitude):
        if not pd.isna(el_p.magnitude) and el_p.magnitude > lfc_p.magnitude:
            el_p = np.nan * units.hPa
        if el_p_top is not None and not pd.isna(el_p_top.magnitude) and el_p_top.magnitude > lfc_p.magnitude:
            el_p_top = None

    if el_p_top is not None and not pd.isna(el_p_top) and len(p) > 1:
        calc_mask = p >= el_p_top
        p_calc = p[calc_mask]
        T_calc = T[calc_mask]
        Td_calc = Td[calc_mask]
        prof_calc = parcel_prof[calc_mask]
    else:
        p_calc, T_calc, Td_calc, prof_calc = p, T, Td, parcel_prof

    cape = 0 * units('J/kg')
    cin = 0 * units('J/kg')

    try:
        if len(p_calc) > 1:
            diff = prof_calc - T_calc
            x = np.log(p_calc.magnitude)
            y = diff.magnitude
            Rd = 287.05
            
            y_neg = y.copy()
            y_neg[y > 0] = 0
            if not pd.isna(lfc_p.magnitude):
                mask_cin_graphic = p_calc >= lfc_p
                y_neg[~mask_cin_graphic] = 0
            else:
                y_neg[:] = 0
                
            if np.any(y_neg < 0):
                area_cin = np.trapezoid(y_neg, x) * Rd
                cin = -1 * abs(area_cin) * units('J/kg')
                
            y_pos = y.copy()
            y_pos[y < 0] = 0
            if not pd.isna(lfc_p.magnitude):
                mask_cape_graphic = p_calc <= lfc_p
                if not pd.isna(el_p.magnitude):
                    mask_cape_graphic &= (p_calc >= el_p)
                y_pos[~mask_cape_graphic] = 0
            else:
                y_pos[:] = 0
                
            if np.any(y_pos > 0):
                area_cape = np.trapezoid(y_pos, x) * Rd
                cape = abs(area_cape) * units('J/kg')
    except Exception as e:
        print(f"Error in robust CAPE/CIN calc: {e}")
        try:
            cape, cin = mpcalc.cape_cin(p_calc, T_calc, Td_calc, prof_calc)
        except Exception:
            cape, cin = 0 * units('J/kg'), 0 * units('J/kg')

    return {
        'lcl_p': lcl_p, 'lcl_T': lcl_T, 'parcel_prof': parcel_prof,
        'lfc_p': lfc_p, 'ccl_p': ccl_p, 'el_p': el_p, 'el_p_top': el_p_top,
        'cape': cape, 'cin': cin
    }

def compute_averaged_wind_barbs(p, u, v, num_barbs=22):
    """
    Reduce la frecuencia de aparición de los ticks de viento en el margen derecho del Skew-T,
    promediando un número de niveles posteriores con niveles anteriores (media móvil / layer average)
    y representando los datos de forma espaciada entre el suelo (~1000 hPa) y 100 hPa.
    """
    if p is None or u is None or v is None:
        return p, u, v

    try:
        p_mag = p.to(units.hPa).magnitude if hasattr(p, "magnitude") else np.asarray(p, dtype=float)
        u_mag = u.magnitude if hasattr(u, "magnitude") else np.asarray(u, dtype=float)
        v_mag = v.magnitude if hasattr(v, "magnitude") else np.asarray(v, dtype=float)

        u_unit = getattr(u, "units", units.knot)
        v_unit = getattr(v, "units", units.knot)

        # Filtrar valores no nulos y restringir al rango entre suelo (~1000 hPa) y 100 hPa
        valid = (~np.isnan(p_mag)) & (~np.isnan(u_mag)) & (~np.isnan(v_mag))
        valid = valid & (p_mag <= 1025) & (p_mag >= 95)

        p_v = p_mag[valid]
        u_v = u_mag[valid]
        v_v = v_mag[valid]

        if len(p_v) < 4:
            return p[valid], u[valid], v[valid]

        # Ordenar por presión descendente (desde el suelo hacia arriba)
        sort_idx = np.argsort(p_v)[::-1]
        p_v = p_v[sort_idx]
        u_v = u_v[sort_idx]
        v_v = v_v[sort_idx]

        # Rango vertical: desde el suelo (máximo 1000 hPa o presión superficial) hasta 100 hPa
        p_max = min(1000.0, float(np.nanmax(p_v)))
        p_min = max(100.0, float(np.nanmin(p_v)))

        if p_max <= p_min:
            return p_v * units.hPa, u_v * u_unit, v_v * v_unit

        # Determinar número de barbas objetivo espaciadas verticalmente (~20 a 22 niveles)
        n_targets = min(num_barbs, max(6, len(p_v) // 2))

        # Niveles objetivo espaciados en la escala logarítmica de presión (Skew-T)
        p_targets = np.logspace(np.log10(p_max), np.log10(p_min), n_targets)

        log_p_v = np.log10(p_v)
        d_log_p = (np.log10(p_max) - np.log10(p_min)) / (n_targets - 1) * 0.55

        barb_p, barb_u, barb_v = [], [], []
        for pt in p_targets:
            target_log_p = np.log10(pt)
            mask = np.abs(log_p_v - target_log_p) <= d_log_p
            if np.sum(mask) >= 2:
                barb_p.append(pt)
                barb_u.append(float(np.mean(u_v[mask])))
                barb_v.append(float(np.mean(v_v[mask])))
            else:
                # Ventana de niveles anterior y posterior más cercanos (media móvil)
                idx = int(np.argmin(np.abs(p_v - pt)))
                k = max(1, min(10, len(p_v) // 20))
                i_start = max(0, idx - k)
                i_end = min(len(p_v), idx + k + 1)
                barb_p.append(pt)
                barb_u.append(float(np.mean(u_v[i_start:i_end])))
                barb_v.append(float(np.mean(v_v[i_start:i_end])))

        return (
            np.array(barb_p) * units.hPa,
            np.array(barb_u) * u_unit,
            np.array(barb_v) * v_unit
        )
    except Exception as e:
        print(f"Error calculando barbas promediadas: {e}")
        return p, u, v

# ── Display Mode Selection (Global) ──────────────────────────────
display_mode = st.radio("Display mode", ["Simple", "Advanced"], index=0, horizontal=True)

# ── Application Mode Selection ──────────────────────────────
MODE_HISTORICAL = "Historical archive"
MODE_LIVE = "Real-Time Live"
app_mode = st.radio(
    "Sounding source mode",
    [MODE_HISTORICAL, MODE_LIVE],
    index=0,
    horizontal=True,
    help="Select between historical archived soundings or tracking balloons in flight right now."
)

if app_mode == MODE_HISTORICAL:
    # ── Load station list ─────────────────────────────
    script_dir = pathlib.Path(__file__).parent.absolute()
    STATION_FILE = script_dir.parent / "data" / "igra_stations_all.csv"

    # Automatically update station list if needed
    with st.spinner("Checking for station updates..."):
        import stations as st_module
        st_module.update_station_list()

    if STATION_FILE.exists():
        stations_df = pd.read_csv(STATION_FILE)
        cities = stations_df['display_name'].tolist()
    else:
        stations_df = pd.DataFrame(columns=["code", "display_name", "city", "raw_name"])
        cities = ["Download Failed - NOAA IGRA Unreachable"]

    # ── Select city and source ───────────────────────────
    city = st.selectbox("Select city/airport", cities)
    source_mode = st.selectbox("Sounding source", ["Auto", "IGRA", "UWYO"])

    # ── Date and time selection ─────────────────────────────
    from datetime import timedelta
    yesterday = datetime.now() - timedelta(days=1)
    fecha = st.date_input("Date", value=yesterday)
    hora_options = ["Auto", "00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]
    hora_str = st.selectbox("Hour (UTC)", hora_options)

    # Prepare date strings
    yr, mn, dy = str(fecha.year), f"{fecha.month:02}", f"{fecha.day:02}"

    if hora_str == "Auto":
        hours_to_try = ["00", "12", "06", "18", "03", "09", "15", "21"]
    else:
        hours_to_try = [f"{datetime.strptime(hora_str, '%H:%M').hour:02}"]

    # ── Generate sounding button ──────────────────────────────
    if st.button("Generate sounding"):
        try:
            with st.spinner("Downloading and processing data..."):
                selected_row = stations_df[stations_df['display_name'] == city].iloc[0]
                CodEst = selected_row['code']
                station_name = selected_row['display_name']
                
                p, T, Td, u, v, source_used = None, None, None, None, None, None
                last_error = None
                found_hr = None

                for test_hr in hours_to_try:
                    try:
                        (p, T, Td, u, v), source_used = get_sounding(CodEst, yr, mn, dy, test_hr, source_mode)
                        found_hr = test_hr
                        break
                    except Exception as e:
                        last_error = e
                        continue
                
                if found_hr is None:
                    raise ValueError(f"No sounding found for date {yr}-{mn}-{dy} (Tried: {hours_to_try}). Last error: {last_error}")
                
                hr = found_hr

                if source_used == "IGRA":
                    source_display = "Integrated Global Radiosonde Archive (IGRA - NOAA)"
                elif source_used.startswith("UWYO"):
                    source_display = "University of Wyoming Weather Web (UWYO)"
                else:
                    source_display = source_used

                source_url = ""
                if source_used == "IGRA":
                    source_url = f"https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/access/data-por/{CodEst}-data.txt.zip"
                elif source_used.startswith("UWYO"):
                    src_param = source_used.split("-")[1] if "-" in source_used else "BUFR"
                    wmo_code = CodEst[-5:]
                    source_url = (
                        f"https://weather.uwyo.edu/wsgi/sounding?"
                        f"datetime={yr}-{mn}-{dy}%20{hr}:00:00&id={wmo_code}&type=TEXT:LIST&src={src_param}"
                    )

                thermo = calculate_thermo_levels(p, T, Td)

                st.session_state['sounding_data'] = {
                    'p': p, 'T': T, 'Td': Td, 'u': u, 'v': v,
                    'lcl_p': thermo['lcl_p'], 'lcl_T': thermo['lcl_T'], 'parcel_prof': thermo['parcel_prof'],
                    'lfc_p': thermo['lfc_p'], 'ccl_p': thermo['ccl_p'], 'el_p': thermo['el_p'],
                    'el_p_top': thermo['el_p_top'], 'cape': thermo['cape'], 'cin': thermo['cin'],
                    'station_name': station_name, 'CodEst': CodEst,
                    'yr': yr, 'mn': mn, 'dy': dy, 'hr': hr,
                    'source_used': source_used, 'source_display': source_display, 'source_url': source_url,
                    'live_meta': None
                }

        except Exception as e:
            st.error(f"❌ Error: {e}")

else:
    # ── SondeHub Real-Time Live Mode ──────────────────────────
    is_dark = bool(st.session_state.get('dark_mode', False))

    # Default map style ("open-street-map") in Light Mode; black map ("carto-darkmatter") when Dark Mode is active
    chosen_style = "carto-darkmatter" if is_dark else "open-street-map"
    bg_color = "#0e1117" if is_dark else "#ffffff"

    # ── Time Window Selector (12h, 9h, 6h, 3h) ──────────────────
    selected_window = st.radio(
        "Updated within last",
        ["12h", "9h", "6h", "3h"],
        index=0,
        horizontal=True,
        key="live_time_window_selector",
        help="Filter radiosondes by how recently their telemetry was updated (last 12, 9, 6, or 3 hours)."
    )
    window_hours = int(selected_window.rstrip("h"))

    # Download / Cache active sondes (up to 12h base window, filtered dynamically by selected_window)
    if 'active_sondes_df' not in st.session_state:
        with st.spinner("Downloading global telemetry for the last 12 hours from SondeHub..."):
            try:
                st.session_state['active_sondes_df'] = get_active_sondes(duration="12h", only_ascending=False)
            except Exception as e:
                st.error(f"Error connecting to SondeHub: {e}")
                st.session_state['active_sondes_df'] = pd.DataFrame()

    df_all_active = st.session_state.get('active_sondes_df', pd.DataFrame())
    if not df_all_active.empty and 'age_seconds' in df_all_active.columns:
        df_active = df_all_active[
            df_all_active['age_seconds'].isna() | (df_all_active['age_seconds'] <= window_hours * 3600)
        ].reset_index(drop=True)
    else:
        df_active = df_all_active

    if df_active.empty:
        st.warning(f"⚠️ No radiosondes found in the last {window_hours} hours or connection issue with SondeHub.")
    else:
        map_df = df_active[df_active['lat'].notnull() & df_active['lon'].notnull()].copy()

        # 1. Synchronize pending selection change (e.g. from Deselect button)
        if 'pending_live_selection' in st.session_state:
            st.session_state['live_sonde_selector'] = st.session_state.pop('pending_live_selection')

        # 2. Callback for interactive map point selection (only runs when user clicks on the map)
        def _on_live_map_select():
            map_state = st.session_state.get('live_map_points')
            if not map_state or not isinstance(map_state, dict):
                return
            selection = map_state.get('selection', {})
            pts = selection.get('points', [])
            if not pts:
                return

            clicked_pt = pts[0]
            clicked_serial = None
            cdata = clicked_pt.get("customdata")
            if cdata is not None:
                clicked_serial = cdata[0] if (isinstance(cdata, (list, tuple)) and len(cdata) > 0) else cdata

            # Fallback to point_index and curve_number (0 is layer of all balloons)
            if (not clicked_serial or clicked_serial not in map_df['serial'].values) and clicked_pt.get("curve_number") == 0:
                pt_idx = clicked_pt.get("point_index")
                if pt_idx is not None and 0 <= pt_idx < len(map_df):
                    clicked_serial = map_df.iloc[pt_idx]['serial']

            if clicked_serial and clicked_serial in map_df['serial'].values:
                matching_label = df_active[df_active['serial'] == clicked_serial].iloc[0]['display_name']
                # Toggle behavior: clicking already selected balloon toggles it OFF (deselects)
                if matching_label == st.session_state.get('live_sonde_selector'):
                    st.session_state['live_sonde_selector'] = None
                else:
                    st.session_state['live_sonde_selector'] = matching_label

        sonde_options = df_active['display_name'].tolist()

        if st.session_state.get('live_sonde_selector') not in sonde_options:
            st.session_state['live_sonde_selector'] = None

        # ── RADIOSONDE SEARCH SELECTBOX (DIRECTLY ABOVE MAP, MATCHING HISTORICAL STYLE) ───
        selected_sonde_label = st.selectbox(
            "Select radiosonde (active balloons)",
            sonde_options,
            index=None,
            key="live_sonde_selector",
            placeholder="-- Select a radiosonde or click on the map --"
        )

        if selected_sonde_label:
            picked_rows = df_active[df_active['display_name'] == selected_sonde_label]
            current_serial = picked_rows.iloc[0]['serial'] if not picked_rows.empty else None
        else:
            current_serial = None

        st.session_state['selected_live_serial'] = current_serial

        # Data row and flight trajectory of selected sonde (if any)
        is_auto_tick = st.session_state.pop('_auto_track_tick', False)
        traj_cache = st.session_state.setdefault('traj_cache', {})

        if current_serial is not None and current_serial in map_df['serial'].values:
            selected_row = map_df[map_df['serial'] == current_serial].iloc[0].copy()
            serial = selected_row['serial']
            if serial not in traj_cache or is_auto_tick:
                fresh_traj = get_sonde_trajectory(serial)
                if not fresh_traj.empty:
                    traj_cache[serial] = fresh_traj
            df_traj = traj_cache.get(serial, pd.DataFrame())

            # Update selected_row live position & telemetry from latest trajectory point if available
            if not df_traj.empty:
                last_pt = df_traj.iloc[-1]
                if pd.notnull(last_pt.get('lat')) and pd.notnull(last_pt.get('lon')):
                    selected_row['lat'] = float(last_pt['lat'])
                    selected_row['lon'] = float(last_pt['lon'])
                if pd.notnull(last_pt.get('pressure_hpa')):
                    selected_row['pressure_hpa'] = float(last_pt['pressure_hpa'])
                if pd.notnull(last_pt.get('alt')):
                    selected_row['alt_m'] = float(last_pt['alt'])
                if pd.notnull(last_pt.get('temp')):
                    selected_row['temp_c'] = float(last_pt['temp'])
                if pd.notnull(last_pt.get('vel_v')):
                    selected_row['vel_v_ms'] = float(last_pt['vel_v'])
                if pd.notnull(last_pt.get('vel_h')):
                    selected_row['vel_h_ms'] = float(last_pt['vel_h'])
                if last_pt.get('datetime'):
                    selected_row['telemetry_time_utc'] = str(last_pt['datetime'])

            if not df_traj.empty and 'lat' in df_traj.columns and 'lon' in df_traj.columns:
                _l_lat = float(df_traj['lat'].iloc[0])
                _l_lon = float(df_traj['lon'].iloc[0])
                _l_site, _ = find_nearest_site(_l_lat, _l_lon, get_launch_sites(), max_dist_km=500)
                if _l_site:
                    _l_country, _l_city = extract_country_city(_l_site.get('station_name', 'Station'))
                    launch_location_label = f"{_l_city}, {_l_country}"
                else:
                    launch_location_label = f"Coord: {_l_lat:.2f}°, {_l_lon:.2f}°"
            else:
                launch_location_label = selected_row['location_label']
        else:
            selected_row = None
            serial = None
            df_traj = pd.DataFrame()
            launch_location_label = None

        # ── BUILD INTERACTIVE MAP WITH FLIGHT PATH FOCUS ───
        fig_map = go.Figure()

        hover_style = dict(
            bgcolor="#1e222b" if is_dark else "#ffffff",
            bordercolor="rgba(250, 250, 250, 0.35)" if is_dark else "rgba(31, 41, 55, 0.35)",
            font=dict(color="#fafafa" if is_dark else "#1f2937", size=12)
        )

        launch_col = map_df['launch_time_utc'] if 'launch_time_utc' in map_df.columns else pd.Series('N/A', index=map_df.index)
        tel_col = map_df['telemetry_time_utc'] if 'telemetry_time_utc' in map_df.columns else pd.Series('N/A', index=map_df.index)

        # 1. Layer of all balloons, colored by pressure in hPa
        custom_data = list(zip(
            map_df['serial'],
            map_df['location_label'],
            map_df['pressure_hpa'].fillna(1013.25),
            map_df['vel_v_ms'].fillna(0),
            map_df['temp_c'].fillna(0),
            map_df['model'],
            map_df['vel_h_ms'].fillna(0),
            map_df['alt_m'].fillna(0),
            launch_col.fillna('N/A'),
            tel_col.fillna('N/A')
        ))

        fig_map.add_trace(go.Scattermap(
            lat=map_df['lat'],
            lon=map_df['lon'],
            mode='markers',
            marker=dict(
                size=9,
                color=-map_df['pressure_hpa'].fillna(1013.25),
                colorscale='Turbo',
                cmin=-1000,
                cmax=-75,
                reversescale=False,
                showscale=True,
                colorbar=dict(
                    title=dict(
                        text='Pressure (hPa)',
                        font=dict(color='white' if is_dark else '#222222', size=11)
                    ),
                    tickfont=dict(color='white' if is_dark else '#222222', size=10),
                    tickvals=[-1000, -850, -700, -500, -300, -200, -100],
                    ticktext=['1000', '850', '700', '500', '300', '200', '100'],
                    bgcolor='rgba(14, 17, 23, 0.78)' if is_dark else 'rgba(255, 255, 255, 0.82)',
                    len=0.75,
                    thickness=13,
                    x=0.99
                )
            ),
            customdata=custom_data,
            hoverlabel=hover_style,
            hovertemplate=(
                '<b>🎈 %{customdata[0]} (%{customdata[5]})</b><br>'
                '📍 %{customdata[1]}<br>'
                '🚀 Launch: <b>%{customdata[8]}</b><br>'
                '🕒 Last telemetry: <b>%{customdata[9]}</b><br>'
                '📏 Pressure: <b>%{customdata[2]:.1f} hPa</b><br>'
                '📐 Altitude: <b>%{customdata[7]:.0f} m</b><br>'
                '⬆️ Ascent: <b>%{customdata[3]:+.1f} m/s</b><br>'
                '🌡️ Temp: <b>%{customdata[4]:.1f} °C</b><br>'
                '💨 Horiz. Wind: <b>%{customdata[6]:.1f} m/s</b>'
                '<extra></extra>'
            ),
            name=f'Sounding ({selected_window})',
            showlegend=False
        ))

        # If a sonde is selected, always draw all 4 layers so legend items never disappear
        if selected_row is not None:
            traj_color = '#00E5FF' if is_dark else '#D84315'
            if not df_traj.empty:
                t_lats = df_traj['lat']
                t_lons = df_traj['lon']
                step = max(1, len(df_traj) // 10)
                traj_sub = df_traj.iloc[::step].copy()
                traj_p_vals = traj_sub['pressure_hpa'].fillna(1013.25)
                traj_temp_vals = traj_sub['temp'].fillna(0) if 'temp' in traj_sub.columns else pd.Series(0, index=traj_sub.index)
                traj_alt_vals = traj_sub['alt'].fillna(0) if 'alt' in traj_sub.columns else pd.Series(0, index=traj_sub.index)
                traj_time_vals = traj_sub['datetime'] if 'datetime' in traj_sub.columns else pd.Series('', index=traj_sub.index)
                launch_lat_0 = float(df_traj['lat'].iloc[0])
                launch_lon_0 = float(df_traj['lon'].iloc[0])
                launch_time_0 = str(df_traj['datetime'].iloc[0]) if 'datetime' in df_traj.columns else selected_row.get('launch_time_utc', 'N/A')
            else:
                t_lats = [selected_row['lat']]
                t_lons = [selected_row['lon']]
                traj_p_vals = [selected_row['pressure_hpa'] if pd.notnull(selected_row['pressure_hpa']) else 1013.25]
                traj_temp_vals = [selected_row['temp_c'] if pd.notnull(selected_row['temp_c']) else 0.0]
                traj_alt_vals = [selected_row['alt_m'] if pd.notnull(selected_row['alt_m']) else 0.0]
                traj_time_vals = [selected_row.get('telemetry_time_utc', 'N/A')]
                launch_lat_0 = float(selected_row['lat'])
                launch_lon_0 = float(selected_row['lon'])
                launch_time_0 = selected_row.get('launch_time_utc', 'N/A')

            # 2. Flight path line layer
            fig_map.add_trace(go.Scattermap(
                lat=t_lats,
                lon=t_lons,
                mode='lines',
                line=dict(width=3.8, color=traj_color),
                name=f'Flight path ({serial})',
                hoverinfo='skip'
            ))

            # 2b. Flight path sampled points layer
            fig_map.add_trace(go.Scattermap(
                lat=traj_sub['lat'] if not df_traj.empty else t_lats,
                lon=traj_sub['lon'] if not df_traj.empty else t_lons,
                mode='markers',
                marker=dict(
                    size=5,
                    color=traj_color,
                    opacity=0.75
                ),
                customdata=list(zip(traj_p_vals, traj_time_vals, traj_temp_vals, traj_alt_vals)),
                hoverlabel=hover_style,
                hovertemplate=(
                    f"<b>Flight point ({serial})</b><br>"
                    "📏 Pressure: <b>%{customdata[0]:.1f} hPa</b> (%{customdata[3]:.0f} m)<br>"
                    "🕒 Time: <b>%{customdata[1]}</b><br>"
                    "🌡️ Temp: <b>%{customdata[2]:.1f} °C</b><br><extra></extra>"
                ),
                name='Flight path points'
            ))

            # 3. Launch site marker
            fig_map.add_trace(go.Scattermap(
                lat=[launch_lat_0],
                lon=[launch_lon_0],
                mode='markers+text',
                text=['🚩'],
                textposition='top center',
                textfont=dict(size=14),
                marker=dict(size=12, color='#00E676' if is_dark else '#00C853'),
                hoverlabel=hover_style,
                hovertemplate=f"<b>Launch point</b><br>{launch_location_label}<br>Start time: {launch_time_0}<extra></extra>",
                name='Launch point'
            ))

            # 4. Highlighted current position marker
            p_sel = selected_row['pressure_hpa']
            p_sel_str = f"{p_sel:.1f} hPa" if pd.notnull(p_sel) else "N/A"
            alt_sel_str = f"({selected_row['alt_m']:.0f} m)" if pd.notnull(selected_row['alt_m']) else ""
            exact_launch_str = df_traj['datetime'].iloc[0] if (not df_traj.empty and 'datetime' in df_traj.columns) else selected_row.get('launch_time_utc', 'N/A')
            fig_map.add_trace(go.Scattermap(
                lat=[selected_row['lat']],
                lon=[selected_row['lon']],
                mode='markers+text',
                text=['🎯'],
                textposition='top right',
                textfont=dict(size=16),
                marker=dict(
                    size=18,
                    color='#FF1744' if is_dark else '#D50000'
                ),
                customdata=[[selected_row['serial']]],
                hoverlabel=hover_style,
                hovertemplate=(
                    f"<b>Current position: {selected_row['serial']}</b><br>"
                    f"{selected_row['location_label']}<br>"
                    f"Launch: <b>{exact_launch_str}</b><br>"
                    f"Pressure: <b>{p_sel_str}</b> {alt_sel_str}<extra></extra>"
                ),
                name='Current position'
            ))

            # Focus on the flight path
            if not df_traj.empty and len(df_traj) > 1:
                lats = df_traj['lat'].tolist()
                lons = df_traj['lon'].tolist()
                center_lat = float(sum(lats) / len(lats))
                center_lon = float(sum(lons) / len(lons))
                span = max(max(lats) - min(lats), max(lons) - min(lons))
                if span > 15:
                    zoom_level = 3.5
                elif span > 8:
                    zoom_level = 4.5
                elif span > 4:
                    zoom_level = 5.2
                elif span > 2:
                    zoom_level = 5.8
                elif span > 0.8:
                    zoom_level = 6.4
                else:
                    zoom_level = 6.9
            else:
                center_lat = float(selected_row['lat'])
                center_lon = float(selected_row['lon'])
                zoom_level = 6.5
        else:
            # Global overview when no radiosonde is selected
            center_lat = 25.0
            center_lon = 10.0
            zoom_level = 1.6

        fig_map.update_layout(
            map=dict(
                style=chosen_style,
                center=dict(lat=center_lat, lon=center_lon),
                zoom=zoom_level
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            height=510,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            hoverlabel=hover_style,
            showlegend=(selected_row is not None),
            legend=dict(
                x=0.01,
                y=0.99,
                xanchor="left",
                yanchor="top",
                bgcolor="rgba(20, 24, 33, 0.88)" if is_dark else "rgba(255, 255, 255, 0.88)",
                bordercolor="rgba(255, 255, 255, 0.2)" if is_dark else "rgba(0, 0, 0, 0.2)",
                borderwidth=1,
                font=dict(color="#fafafa" if is_dark else "#1f2937", size=11)
            )
        )

        map_event = st.plotly_chart(
            fig_map,
            on_select=_on_live_map_select,
            selection_mode="points",
            key="live_map_points",
            theme=None,
            width="stretch"
        )

        # ── MAP FOOTER: REFRESH AND DATA SOURCE ────────
        col_map_footer_left, col_map_footer_mid, col_map_footer_right = st.columns([1.2, 1.3, 1.5])
        with col_map_footer_left:
            if st.button("🔄 Refresh map", key="btn_refresh_map"):
                st.session_state.pop('active_sondes_df', None)
                st.rerun()
        with col_map_footer_mid:
            if selected_row is not None:
                if st.button("Reset", key="btn_deselect_sonde"):
                    st.session_state['pending_live_selection'] = None
                    st.rerun()
        with col_map_footer_right:
            st.markdown(
                """
                <div style="text-align: right; font-size: 0.85em; color: gray; padding-top: 6px;">
                    Source <a href="https://sondehub.org" target="_blank" style="color: #0288D1; text-decoration: underline;">SondeHub.org</a>
                </div>
                """,
                unsafe_allow_html=True
            )



        # ── SELECTED RADIOSONDE TELEMETRY PANEL (OR PROMPT MESSAGE) ──
        if selected_row is not None:
            telemetry_panel_container = st.container()

            REFRESH_INTERVALS = {
                "15 s": 15,
                "30 s": 30,
                "1 min": 60,
                "5 min": 300,
                "10 min": 600,
                "30 min": 1800,
                "1 h": 3600,
                "2 h": 7200,
            }

            col_act1, col_act2, col_act3, col_act4 = st.columns(
                [1.15, 1.08, 0.85, 1.15],
                vertical_alignment="center"
            )
            with col_act1:
                track_clicked = st.button("Generate sounding", key="generate_live_sounding")
            with col_act2:
                auto_refresh = st.checkbox(
                    "Auto-tracking:",
                    value=False,
                    key="live_auto_tracking",
                    help="Automatically refresh the selected radiosonde telemetry at the chosen interval"
                )
            with col_act3:
                refresh_label = st.selectbox(
                    "Refresh interval",
                    options=list(REFRESH_INTERVALS.keys()),
                    index=0,
                    key="live_refresh_interval",
                    label_visibility="collapsed",
                    help="Select the auto-tracking refresh interval"
                )
                refresh_seconds = REFRESH_INTERVALS[refresh_label]
            with col_act4:
                st.markdown(f"<div style='text-align: right; white-space: nowrap;'><a href='https://sondehub.org/#!mt=Mapnik&mz=9&qm=3h&q={serial}' target='_blank' style='text-decoration:none;'>🔗 View on SondeHub.org</a></div>", unsafe_allow_html=True)

            def process_live_sonde():
                with st.spinner(f"Downloading vertical telemetry profile for {serial}..."):
                    (p, T, Td, u, v), live_meta = get_live_sounding(serial)
                    thermo = calculate_thermo_levels(p, T, Td)

                    site_name = live_meta['nearest_site']['station_name'] if live_meta['nearest_site'] else live_meta['serial']
                    st.session_state['sounding_data'] = {
                        'p': p, 'T': T, 'Td': Td, 'u': u, 'v': v,
                        'lcl_p': thermo['lcl_p'], 'lcl_T': thermo['lcl_T'], 'parcel_prof': thermo['parcel_prof'],
                        'lfc_p': thermo['lfc_p'], 'ccl_p': thermo['ccl_p'], 'el_p': thermo['el_p'],
                        'el_p_top': thermo['el_p_top'], 'cape': thermo['cape'], 'cin': thermo['cin'],
                        'station_name': site_name, 'CodEst': serial,
                        'yr': live_meta['yr'], 'mn': live_meta['mn'], 'dy': live_meta['dy'], 'hr': live_meta['hr'],
                        'source_used': "SondeHub Live",
                        'source_display': f"SondeHub Global Tracker ({live_meta['type']})",
                        'source_url': live_meta['source_url'],
                        'live_meta': live_meta,
                        '_sanitized_v2': True
                    }

            sounding_already_generated = (
                st.session_state.get('sounding_generated_for_serial') == serial
                and 'sounding_data' in st.session_state
                and st.session_state['sounding_data'].get('CodEst') == serial
            )

            if track_clicked:
                try:
                    process_live_sonde()
                    st.session_state['sounding_generated_for_serial'] = serial
                    sounding_already_generated = True
                except Exception as e:
                    st.error(f"❌ Error processing real-time sounding: {e}")
            elif auto_refresh and is_auto_tick and sounding_already_generated:
                try:
                    process_live_sonde()
                except Exception as e:
                    st.warning(f"Update notice: {e}")

            if auto_refresh:
                if sounding_already_generated:
                    st.success(f"⚡ Auto-tracking active (every {refresh_label}) — Map, telemetry & sounding figure updated at {datetime.now().strftime('%H:%M:%S')}")
                else:
                    st.success(f"⚡ Auto-tracking active (every {refresh_label}) — Map trajectory & telemetry updated at {datetime.now().strftime('%H:%M:%S')} (press 'Generate sounding' to plot Skew-T)")

            # Populate pre-button telemetry banner & metrics with latest live_meta if available for this serial
            active_sd = st.session_state.get('sounding_data', {})
            active_meta = active_sd.get('live_meta') if (active_sd and active_sd.get('CodEst') == serial) else None

            if active_meta:
                cur_p_val = active_meta.get('current_pressure_hpa')
                if cur_p_val is None and len(active_sd.get('p', [])) > 0:
                    cur_p_val = float(active_sd['p'][-1].magnitude)
                disp_p_str = f"{cur_p_val:.1f} hPa" if cur_p_val is not None and pd.notnull(cur_p_val) else p_sel_str
                cur_vv = active_meta.get('current_vel_v_ms')
                disp_vel_str = f"{cur_vv:+.1f} m/s" if cur_vv is not None and pd.notnull(cur_vv) else (f"{selected_row['vel_v_ms']:+.1f} m/s" if selected_row['vel_v_ms'] is not None else "N/A")
                cur_tc = active_meta.get('current_temp_c')
                disp_temp_str = f"{cur_tc:.1f} °C" if cur_tc is not None and pd.notnull(cur_tc) else (f"{selected_row['temp_c']:.1f} °C" if selected_row['temp_c'] is not None else "N/A")
                cur_vh = active_meta.get('current_vel_h_ms')
                disp_wind_str = f"{cur_vh:.1f} m/s" if cur_vh is not None and pd.notnull(cur_vh) else (f"{selected_row['vel_h_ms']:.1f} m/s" if selected_row['vel_h_ms'] is not None else "N/A")
                disp_traj_count = active_meta.get('num_points', len(df_traj) if not df_traj.empty else 0)
                disp_launch_str = active_meta.get('launch_time') or (df_traj['datetime'].iloc[0] if (not df_traj.empty and 'datetime' in df_traj.columns) else selected_row.get('launch_time_utc', 'N/A'))
                disp_last_tel_str = active_meta.get('latest_time') or selected_row.get('telemetry_time_utc', 'N/A')
                disp_lat = active_meta.get('current_lat') if active_meta.get('current_lat') is not None else selected_row['lat']
                disp_lon = active_meta.get('current_lon') if active_meta.get('current_lon') is not None else selected_row['lon']
            else:
                disp_p_str = p_sel_str
                disp_vel_str = f"{selected_row['vel_v_ms']:+.1f} m/s" if selected_row['vel_v_ms'] is not None else "N/A"
                disp_temp_str = f"{selected_row['temp_c']:.1f} °C" if selected_row['temp_c'] is not None else "N/A"
                disp_wind_str = f"{selected_row['vel_h_ms']:.1f} m/s" if selected_row['vel_h_ms'] is not None else "N/A"
                disp_traj_count = len(df_traj) if not df_traj.empty else 0
                disp_launch_str = df_traj['datetime'].iloc[0] if (not df_traj.empty and 'datetime' in df_traj.columns) else selected_row.get('launch_time_utc', 'N/A')
                disp_last_tel_str = selected_row.get('telemetry_time_utc', 'N/A')
                disp_lat = selected_row['lat']
                disp_lon = selected_row['lon']

            with telemetry_panel_container:
                st.markdown(
                    f"""
                    <div style="background: rgba(120, 140, 160, 0.08); padding: 12px 18px; border-radius: 8px; border-left: 4px solid #FF3D00; margin-top: 5px; margin-bottom: 12px;">
                        <div style="font-size: 1.1em; font-weight: bold;">
                            🎈 {launch_location_label} <span style="font-weight: normal; color: gray;">({selected_row['serial']} — {selected_row['model']})</span>
                        </div>
                        <div style="font-size: 0.85em; color: gray; margin-top: 2px;">
                            🚀 Launch ({launch_location_label}): <b>{disp_launch_str}</b> | 🕒 Last telemetry: <b>{disp_last_tel_str}</b><br>
                            Manufacturer: <b>{selected_row['manufacturer']}</b> | Recorded flight path points: <b>{disp_traj_count}</b> | Current position ({selected_row['location_label']}): <b>{disp_lat:.3f}°, {disp_lon:.3f}°</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Current pressure", disp_p_str)
                c2.metric("Vertical velocity", disp_vel_str)
                c3.metric("Top temperature", disp_temp_str)
                c4.metric("Horizontal wind", disp_wind_str)

            if auto_refresh:
                _auto_tick_state = {"first": True}

                @st.fragment(run_every=refresh_seconds)
                def live_auto_updater():
                    if _auto_tick_state["first"]:
                        _auto_tick_state["first"] = False
                        return
                    st.session_state['_auto_track_tick'] = True
                    st.rerun()

                live_auto_updater()
        else:
            st.info("👆 **Select a radiosonde** in the list above or click on any balloon (dot) on the map to inspect its telemetry and generate the sounding.")


# Check if data exists in session state to display results
_show_sounding_results = False
if 'sounding_data' in st.session_state:
    _sd_cur = st.session_state['sounding_data']
    if app_mode == MODE_HISTORICAL:
        _show_sounding_results = (_sd_cur.get('source_used') != "SondeHub Live")
    else:
        _cur_live_ser = st.session_state.get('selected_live_serial')
        _show_sounding_results = (
            _cur_live_ser is not None
            and st.session_state.get('sounding_generated_for_serial') == _cur_live_ser
            and _sd_cur.get('CodEst') == _cur_live_ser
        )

if _show_sounding_results:
    data = st.session_state['sounding_data']
    if data.get('source_used') == "SondeHub Live" and not data.get('_sanitized_v2'):
        try:
            (p_new, T_new, Td_new, u_new, v_new), live_meta_new = get_live_sounding(data['CodEst'])
            thermo_new = calculate_thermo_levels(p_new, T_new, Td_new)
            data.update({
                'p': p_new, 'T': T_new, 'Td': Td_new, 'u': u_new, 'v': v_new,
                'lcl_p': thermo_new['lcl_p'], 'lcl_T': thermo_new['lcl_T'], 'parcel_prof': thermo_new['parcel_prof'],
                'lfc_p': thermo_new['lfc_p'], 'ccl_p': thermo_new['ccl_p'], 'el_p': thermo_new['el_p'],
                'el_p_top': thermo_new['el_p_top'], 'cape': thermo_new['cape'], 'cin': thermo_new['cin'],
                'yr': live_meta_new['yr'], 'mn': live_meta_new['mn'], 'dy': live_meta_new['dy'], 'hr': live_meta_new['hr'],
                'live_meta': live_meta_new,
                '_sanitized_v2': True
            })
        except Exception:
            pass
    
    # Unpack variables for convenience
    p, T, Td, u, v = data['p'], data['T'], data['Td'], data['u'], data['v']
    lcl_p, lcl_T, parcel_prof = data['lcl_p'], data['lcl_T'], data['parcel_prof']
    lfc_p, ccl_p, el_p, el_p_top, cape, cin = data['lfc_p'], data['ccl_p'], data['el_p'], data.get('el_p_top', None), data['cape'], data['cin']
    station_name, CodEst = data['station_name'], data['CodEst']
    yr, mn, dy, hr = data['yr'], data['mn'], data['dy'], data['hr']
    source_used, source_display, source_url = data['source_used'], data['source_display'], data['source_url']
    live_meta = data.get('live_meta', None)

    if live_meta:
        alt_str = f"{live_meta['current_alt_m']/1000.0:.2f} km ({live_meta['current_alt_m']:.0f} m)" if live_meta.get('current_alt_m') is not None else "N/A"
        vel_str = f"+{live_meta['current_vel_v_ms']:.1f} m/s" if live_meta.get('current_vel_v_ms') is not None else "N/A"
        temp_str = f"{live_meta['current_temp_c']:.1f} °C" if live_meta.get('current_temp_c') is not None else "N/A"
        st.info(
            f"**Live sounding in progress** | Serial: **{CodEst}** ({live_meta['type']}) | "
            f"Current alt: **{alt_str}** | "
            f"Ascent: **{vel_str}** | "
            f"Top temp: **{temp_str}** | "
            f"Levels: **{live_meta['num_points']}** | "
            f"Packet: **{live_meta.get('latest_time', '')}**"
        )

    st.write(f"Sounding retrieved from: **{source_display}**")
    st.write(f"Station: **{station_name} ({CodEst})**")

    if source_url:
        st.markdown(f"🔗 [View original data source]({source_url})")

    # ── Show results in columns ─────────────────
    st.markdown("### Indices and levels")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("LCL", f"{lcl_p.magnitude:.1f} hPa")
    col2.metric("CCL", f"{ccl_p.magnitude:.1f} hPa" if not pd.isna(ccl_p.magnitude) else "N/A")
    col3.metric("LFC", f"{lfc_p.magnitude:.1f} hPa" if not pd.isna(lfc_p.magnitude) else "N/A")
    col4.metric("EL", f"{el_p.magnitude:.1f} hPa" if not pd.isna(el_p.magnitude) else "N/A")
    
    colA, colB = st.columns(2)
    colA.metric("CAPE", f"{cape.magnitude:.0f} J/kg")
    colB.metric("CIN", f"{cin.magnitude:.0f} J/kg")


    # ── Plot Skew-T ────────────────────────────────
    tab_static, tab_interactive, tab_interpretation = st.tabs(["Static (MetPy)", "Interactive (Plotly)", "❓ Interpretation"])
    
    with tab_static:
        import matplotlib.gridspec as gridspec
        
        # Create figure (reduced dpi to prevent memory crashes on Streamlit Cloud)
        fig = plt.figure(figsize=(17, 12), dpi=300)
        
        # Define GridSpec based on display mode
        if display_mode == "Advanced":
            # Left (SkewT) vs Right (Hodo + Stats)
            gs = gridspec.GridSpec(1, 2, figure=fig, width_ratios=[1.4, 0.6], wspace=0.01)
            
            # Right column sub-grid: 2 Rows (Hodograph top, Stats bottom)
            gs_right = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[1], height_ratios=[0.9, 1.1], hspace=0.1)
        else:
            # Simple Mode: Single Panel for SkewT using full width
            gs = gridspec.GridSpec(1, 1, figure=fig)
            gs_right = None

        # ── Skew-T Axis ─────────────────────────────────
        # Place SkewT in the first column
        skew = SkewT(fig, rotation=45, subplot=gs[0])
        
        # Add title: Place, Station Code, Date & 24h UTC time (no trailing Z after UTC)
        hr_display = hr if "UTC" in str(hr) else f"{hr}:00 UTC"
        if display_mode == "Advanced":
            fig.suptitle(f"{station_name} ({CodEst}) — {yr}-{mn}-{dy} {hr_display}", fontsize=16, fontweight='bold', x=0.53, y=0.925)
        else:
            fig.suptitle(f"{station_name} ({CodEst}) — {yr}-{mn}-{dy} {hr_display}", fontsize=16, fontweight='bold', x=0.515, y=0.925)

        skew.plot(p, T, 'r', label='T')
        skew.plot(p, Td, 'g', label='Td')
        skew.plot(p, parcel_prof, 'k--') # No label for Parcel as requested
        
        # Custom Legend with CAPE/CIN
        handles, labels = skew.ax.get_legend_handles_labels()
        
        # Add patches for CAPE/CIN
        patch_cape = Patch(color='orangered', alpha=0.3, label=f"CAPE")
        patch_cin  = Patch(color='cornflowerblue', alpha=0.3, label=f"CIN")
        patch_clouds = Patch(color='gray', alpha=0.4, label='Cloud layer')

        handles.extend([patch_cape, patch_cin, patch_clouds])
        
        skew.ax.legend(handles=handles, loc='upper left', framealpha=1)

        # ── Cloud Layer Indicator ───────────────────────
        try:
            # Calculate depression.
            t_vals = T.to(units.degC).magnitude
            td_vals = Td.to(units.degC).magnitude
            p_vals = p.to(units.hPa).magnitude
            
            dd = t_vals - td_vals
            
            # Threshold: 3 degrees C
            is_cloud = (dd < 3.0) & (~np.isnan(dd))
            
            skew.ax.fill_betweenx(p_vals, 0, 0.03, where=is_cloud, color='gray', alpha=0.4, transform=skew.ax.get_yaxis_transform())
            
        except Exception as e:
            print(f"Could not plot cloud layers: {e}")

        # Plot Wind Barbs (Decimated with Moving Average from 1000 to 100 hPa)
        if not np.isnan(u).all() and not np.isnan(v).all():
            try:
                p_b, u_b, v_b = compute_averaged_wind_barbs(p, u, v, num_barbs=22)
                if len(p_b) > 0:
                    skew.plot_barbs(p_b, u_b, v_b)
            except Exception as e_barbs:
                print(f"Error trazando barbas de viento: {e_barbs}")
                skew.plot_barbs(p[::40], u[::40], v[::40])

        # Restrict CIN to area below LFC and EL
        if not pd.isna(lfc_p.magnitude):
            mask_cin = (p >= lfc_p)
            if not pd.isna(el_p.magnitude):
                mask_cin = mask_cin & (p >= el_p)
            skew.shade_cin(p[mask_cin], T[mask_cin], parcel_prof[mask_cin])

        # Shade CAPE
        if not pd.isna(lfc_p):
            mask_cape = p <= lfc_p
            if not pd.isna(el_p.magnitude):
                mask_cape = mask_cape & (p >= el_p)
            skew.shade_cape(p[mask_cape], T[mask_cape], parcel_prof[mask_cape])

        skew.ax.set_ylim(1050, 75)
        skew.ax.set_xlim(-40, 40)
        
        # Explicit axis labels as requested
        skew.ax.set_ylabel("Pressure (hPa)")
        skew.ax.set_xlabel("Temperature (ºC)")

        skew.plot_dry_adiabats()
        skew.plot_moist_adiabats()
        skew.plot_mixing_lines()
        
        # Reference lines & Labels
        level_config = [
            (lcl_p, 'LCL', 'sienna'),
            (ccl_p, 'CCL', 'darkorange'),
            (lfc_p, 'LFC', 'blue'),
            (el_p,  'EL',  'darkorchid')
        ]

        for p_level, label, color in level_config:
            if not pd.isna(p_level.magnitude) and 75 <= p_level.magnitude <= 1050:
                skew.ax.axhline(p_level.magnitude, linestyle='--', color=color, linewidth=1.5)
                # Keep text inside SkewT limits
                skew.ax.text(-38, p_level.magnitude - 5, label, color=color, fontsize=10, fontweight='bold')


        # ── Hodograph Axis ──────────────────────────────
        # Use top-right cell
        if display_mode == "Advanced":
            try:
                ax_hod = fig.add_subplot(gs_right[0])
                
                h = Hodograph(ax_hod, component_range=80.)
                # Add two separate grid increments (SPC Style)
                h.add_grid(increment=20, ls='-', lw=1.5, alpha=0.5)
                h.add_grid(increment=10, ls='--', lw=1, alpha=0.2)
                
                # Hide standard labels
                h.ax.set_yticklabels([])
                h.ax.set_xticklabels([])
                h.ax.set_xticks([])
                h.ax.set_yticks([])
                h.ax.set_xlabel(' ')
                h.ax.set_ylabel(' ')

                # Custom internal labels (SPC Style)
                for i in range(10, 90, 20):
                    h.ax.annotate(str(i), (i, 0), xytext=(0, 2), textcoords='offset pixels',
                                clip_on=True, fontsize=8, weight='bold', alpha=0.5, zorder=0)
                for i in range(10, 90, 20):
                    h.ax.annotate(str(i), (0, i), xytext=(0, 2), textcoords='offset pixels',
                                clip_on=True, fontsize=8, weight='bold', alpha=0.5, zorder=0)
                
                # Calculate wind speed for coloring
                wind_speed = mpcalc.wind_speed(u, v)
                
                # Plot
                lc = h.plot_colormapped(u, v, wind_speed)
                
                # Añadir barra de color (¿Inserta en el eje del hodógrafo o separada?)
                # Se debe verificar la alineación con la lógica.
                # Usando ejes insertados para anclarla a ax_hod
                ax_cbar = ax_hod.inset_axes([1.02, 0.25, 0.05, 0.5]) # relative to Hodo axes
                cbar = plt.colorbar(lc, cax=ax_cbar)
                cbar.set_label('Wind Speed (knots)', fontsize=10)
                cbar.ax.tick_params(labelsize=8)
                
            except Exception as e:
                print(f"Error plotting hodograph: {e}")

        # ── Advanced Parameters & Layout ────────────────
        if display_mode == "Advanced":
            # 1. Thermodynamic Indices (each guarded independently)
            try:
                sbcape, sbcin = mpcalc.surface_based_cape_cin(p, T, Td)
            except Exception:
                sbcape, sbcin = 0 * units.J / units.kg, 0 * units.J / units.kg
            try:
                ml_cape, ml_cin = mpcalc.mixed_layer_cape_cin(p, T, Td, depth=50 * units.hPa)
            except Exception:
                ml_cape, ml_cin = 0 * units.J / units.kg, 0 * units.J / units.kg
            try:
                mu_cape, mu_cin = mpcalc.most_unstable_cape_cin(p, T, Td, depth=50 * units.hPa)
            except Exception:
                mu_cape, mu_cin = 0 * units.J / units.kg, 0 * units.J / units.kg
            try:
                tt_idx = mpcalc.total_totals_index(p, T, Td)
            except Exception:
                tt_idx = np.nan
            try:
                k_idx = mpcalc.k_index(p, T, Td)
            except Exception:
                k_idx = np.nan

            # 2. Kinematic Indices & Storm Motion
            z = mpcalc.pressure_to_height_std(p)
            z = z - z[0]  # AGL

            mask = ~np.isnan(u) & ~np.isnan(v) & ~np.isnan(p)
            u_masked, v_masked, z_masked = u[mask], v[mask], z[mask]

            try:
                RM, LM, MW = mpcalc.bunkers_storm_motion(p[mask], u[mask], v[mask], z[mask])
                h.ax.text(RM[0].magnitude, RM[1].magnitude, 'RM', weight='bold', ha='left', fontsize=8, color='black', clip_on=True)
                h.ax.plot(RM[0].magnitude, RM[1].magnitude, 'ko', markersize=4)
                h.ax.text(LM[0].magnitude, LM[1].magnitude, 'LM', weight='bold', ha='left', fontsize=8, color='black', clip_on=True)
                h.ax.plot(LM[0].magnitude, LM[1].magnitude, 'ko', markersize=4)
            except Exception:
                RM = [np.nan * units('m/s'), np.nan * units('m/s')]
                LM = [np.nan * units('m/s'), np.nan * units('m/s')]
                MW = [np.nan * units('m/s'), np.nan * units('m/s')]

            def calc_srh(depth_m):
                try:
                    srh = mpcalc.storm_relative_helicity(
                        z[mask], u[mask], v[mask], depth=depth_m * units.m,
                        storm_u=RM[0], storm_v=RM[1]
                    )[0]
                    return srh
                except Exception:
                    return np.nan * units.m**2 / units.s**2

            srh_1km = calc_srh(1000)
            srh_3km = calc_srh(3000)

            def calc_shear(depth_m):
                try:
                    sh_u, sh_v = mpcalc.bulk_shear(p[mask], u[mask], v[mask], height=z[mask], depth=depth_m * units.m)
                    return mpcalc.wind_speed(sh_u, sh_v)
                except Exception:
                    return np.nan * units.kt

            shear_1km = calc_shear(1000)
            shear_3km = calc_shear(3000)
            shear_6km = calc_shear(6000)

            # 3. Composite Indices
            try:
                lcl_pressure, _ = mpcalc.lcl(p[0], T[0], Td[0])
                lcl_z = mpcalc.pressure_to_height_std(lcl_pressure) - mpcalc.pressure_to_height_std(p[0])
                sig_tor = mpcalc.significant_tornado(sbcape, lcl_z, srh_1km, shear_6km)
            except Exception:
                sig_tor = [np.nan]

            try:
                sup_comp = mpcalc.supercell_composite(mu_cape, srh_3km, shear_6km)
            except Exception:
                sup_comp = [np.nan]


        # ── Statistics Panel (Dual Column) ────────────────
        if display_mode == "Advanced":
            # Use bottom-right cell
            ax_stats = fig.add_subplot(gs_right[1])
            ax_stats.axis('off') # Ocultar eje, se usa solo para texto
            
            # Border for stats (using plot on axes instead of fig rectangle)
            rect = plt.Rectangle((0, 0), 1, 1, fill=False, color='black', lw=1, transform=ax_stats.transAxes)
            ax_stats.add_patch(rect)
            
            # Helper
            def fmt(val, precision=0):
                try:
                    # Handle MetPy Quantity
                    if hasattr(val, 'magnitude'):
                        v = val.magnitude
                    else:
                        v = val
                    
                    # Handle numpy array (0-d or singleton)
                    if hasattr(v, 'item'):
                        v = v.item()
                        
                    if pd.isna(v):
                        return "-"
                    
                    return f"{v:.{precision}f}"
                except:
                    return "-"

            # Text Layout using AXES coordinates (0-1 relative to stat box)
            
            # Cols center
            c1_center = 0.25
            c2_center = 0.75
            
            # Headers
            ax_stats.text(c1_center, 0.92, "THERMODYNAMIC", weight='bold', fontsize=9, ha='center', color='black', transform=ax_stats.transAxes)
            ax_stats.text(c2_center, 0.92, "KINEMATIC", weight='bold', fontsize=9, ha='center', color='black', transform=ax_stats.transAxes)
            
            # Separators
            ax_stats.plot([0, 1], [0.88, 0.88], color='black', lw=0.5, transform=ax_stats.transAxes) # Horizontal below header
            ax_stats.plot([0.5, 0.5], [0, 1], color='black', lw=0.5, transform=ax_stats.transAxes) # Vertical middle

            # Lines data
            y_start = 0.80
            y_step = 0.10
            
            # Columns X positions for labels and values
            # Col 1
            x1_lbl = 0.05
            x1_val = 0.45
            # Col 2
            x2_lbl = 0.55
            x2_val = 0.95

            y_curr = y_start

            # Row 1: SBCAPE | Shear 0-1km
            ax_stats.text(x1_lbl, y_curr, "SBCAPE", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x1_val, y_curr, fmt(sbcape), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)
            
            ax_stats.text(x2_lbl, y_curr, "Sfc-1km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x2_val, y_curr, fmt(shear_1km) + " kt", fontsize=9, weight='bold', color='blue', ha='right', transform=ax_stats.transAxes)
            
            y_curr -= y_step
            # Row 2: SBCIN | Shear 0-3km
            ax_stats.text(x1_lbl, y_curr, "SBCIN", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x1_val, y_curr, fmt(sbcin), fontsize=9, weight='bold', color='cornflowerblue', ha='right', transform=ax_stats.transAxes)
            
            ax_stats.text(x2_lbl, y_curr, "Sfc-3km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x2_val, y_curr, fmt(shear_3km) + " kt", fontsize=9, weight='bold', color='blue', ha='right', transform=ax_stats.transAxes)

            y_curr -= y_step
            # Row 3: MLCAPE | Shear 0-6km
            ax_stats.text(x1_lbl, y_curr, "MLCAPE", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x1_val, y_curr, fmt(ml_cape), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)
            
            ax_stats.text(x2_lbl, y_curr, "Sfc-6km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x2_val, y_curr, fmt(shear_6km) + " kt", fontsize=9, weight='bold', color='blue', ha='right', transform=ax_stats.transAxes)
            
            y_curr -= y_step
            # Row 4: MLCIN | SRH 0-1km
            ax_stats.text(x1_lbl, y_curr, "MLCIN", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x1_val, y_curr, fmt(ml_cin), fontsize=9, weight='bold', color='cornflowerblue', ha='right', transform=ax_stats.transAxes)
            
            ax_stats.text(x2_lbl, y_curr, "SRH 1km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x2_val, y_curr, fmt(srh_1km), fontsize=9, weight='bold', color='navy', ha='right', transform=ax_stats.transAxes)

            y_curr -= y_step
            # Row 5: MUCAPE | SRH 0-3km
            ax_stats.text(x1_lbl, y_curr, "MUCAPE", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x1_val, y_curr, fmt(mu_cape), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)
            
            ax_stats.text(x2_lbl, y_curr, "SRH 3km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x2_val, y_curr, fmt(srh_3km), fontsize=9, weight='bold', color='navy', ha='right', transform=ax_stats.transAxes)

            y_curr -= y_step
            # Row 6: MUCIN | EMPTY
            ax_stats.text(x1_lbl, y_curr, "MUCIN", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x1_val, y_curr, fmt(mu_cin), fontsize=9, weight='bold', color='cornflowerblue', ha='right', transform=ax_stats.transAxes)

            y_curr -= 1.5*y_step # Space
            
            # Row 7: TT Index | Sig Tornado
            ax_stats.text(x1_lbl, y_curr, "TT Index", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x1_val, y_curr, fmt(tt_idx), fontsize=9, weight='bold', color='black', ha='right', transform=ax_stats.transAxes)
            
            ax_stats.text(x2_lbl, y_curr, "SIGTOR", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            # sig_tor is dimensionless quantity usually
            stpv = sig_tor[0] if isinstance(sig_tor, list) else sig_tor
            ax_stats.text(x2_val, y_curr, fmt(stpv, 1), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)

            y_curr -= y_step
            # Row 8: K Index | Supercell
            ax_stats.text(x1_lbl, y_curr, "K Index", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            ax_stats.text(x1_val, y_curr, fmt(k_idx), fontsize=9, weight='bold', color='black', ha='right', transform=ax_stats.transAxes)
            
            ax_stats.text(x2_lbl, y_curr, "SUPCELL", fontsize=9, weight='bold', transform=ax_stats.transAxes)
            scpv = sup_comp[0] if isinstance(sup_comp, list) else sup_comp
            ax_stats.text(x2_val, y_curr, fmt(scpv, 1), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)


        # Add copyright text to the bottom of the figure
        if source_used == "SondeHub Live":
            _cc_license_name = "Creative Commons Attribution-ShareAlike 4.0 International"
        else:
            _cc_license_name = "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International"
        license_text = (
            f"MeTroV © {datetime.now().year} by Óscar Mata-Romero is licensed under {_cc_license_name}\n"
            f"Data: {source_url}"
        )
        plt.figtext(0.5, 0.01, license_text, ha="center", va="bottom", fontsize=8, color='gray')

        # Save standard-res image to buffer for UI display
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')  # uses fig's dpi=150
        buf.seek(0)
        
        # Display image directly
        st.image(buf, output_format="PNG")
        
        # Save high-res version to another buffer for the download button
        buf_high = io.BytesIO()
        fig.savefig(buf_high, format='png', bbox_inches='tight', dpi=900)
        buf_high.seek(0)
        
        # Add download button for full quality
        safe_hr = str(hr).replace(":", "").replace(" ", "_")
        st.download_button(
            label="💾 Download image",
            data=buf_high,
            file_name=f"skewt_{station_name}_{yr}{mn}{dy}_{safe_hr}.png",
            mime="image/png"
        )
        
        # Close figure to free memory
        plt.close(fig)
        
    with tab_interactive:
        st.info("💡 Experimental interactive chart (manually transformed axes to simulate Skew-T) should not be used for quantitative interpretation.")
        hr_display_plotly = hr if "UTC" in str(hr) else f"{hr}:00 UTC"
        _is_dark_plotly = bool(st.session_state.get('dark_mode', False))
        fig_plotly = create_skewt_plotly(p, T, Td, station_name, f"{yr}-{mn}-{dy} {hr_display_plotly}", is_dark=_is_dark_plotly)
        st.plotly_chart(fig_plotly, theme=None, width="stretch")

    with tab_interpretation:
        st.markdown(get_interpretation_text())

st.markdown(
    f"""<hr style="margin-top: 3rem; margin-bottom: 1rem;">
<div style="text-align: center; font-size: 0.85em; color: gray;">
<div style="margin-bottom: 5px;">MeTroV (v1.2.1) — Data: NOAA IGRA, University of Wyoming & SondeHub</div>
<div xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/">
<a property="dct:title" rel="cc:attributionURL" href="https://metrovgit.streamlit.app/" style="color: inherit; text-decoration: none;">MeTroV</a> © <span id="copyrightYear" style="color: inherit !important;">{datetime.now().year}</span> by <a rel="cc:attributionURL dct:creator" property="cc:attributionName" href="https://sites.google.com/view/oscarmr-en">Óscar Mata-Romero</a>.
<br>
Content licensed under <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">CC BY-NC-SA 4.0</a>.
Source code licensed under <a href="https://www.gnu.org/licenses/agpl-3.0.html" target="_blank" style="display:inline-block;">GNU AGPLv3</a>.
</div>
</div>
<script>
const copyrightYear = document.getElementById('copyrightYear');
if (copyrightYear) {{ copyrightYear.textContent = new Date().getFullYear(); }}
</script>""",
    unsafe_allow_html=True
)



