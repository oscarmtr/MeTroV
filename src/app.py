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
from stations import find_station, update_station_list
from sondeo_plotly import create_skewt_plotly
from metpy.plots import SkewT, Hodograph
from matplotlib.patches import Patch
import matplotlib.pyplot as plt
import metpy.calc as mpcalc
from metpy.units import units
from interpretation_text import get_interpretation_text

st.set_page_config(page_title="MeTroV", layout="centered")

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

        **Purpose**
        Research and educational use.

        ---
        """
    )
    # st.markdown("### 📖 How to cite")
    # st.code(
    #     "Óscar Mata-Romero (2026). Meteorological Sounding Viewer. "
    #     "Radiosonde data from NOAA IGRA & University of Wyoming."
    # )

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
                raise ValueError("Sondeo UWyo no disponible o vacío después de filtrar")

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
        raise ValueError("source_mode debe ser IGRA, UWYO o AUTO")

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




# ── Load station list ─────────────────────────────
script_dir = pathlib.Path(__file__).parent.absolute()
STATION_FILE = script_dir.parent / "data" / "igra_stations_all.csv"

# Automatically update station list if needed
with st.spinner("Checking for station updates..."):
    # Reutilizar lógica de actualización del módulo stations
    # Debe ser importado. Dado que 'from stations import find_station' está en la parte superior,
    # el módulo o la función pueden importarse aquí.
    import stations as st_module
    st_module.update_station_list()

stations_df = pd.read_csv(STATION_FILE)
cities = stations_df['display_name'].tolist()

# ── Select city and source ───────────────────────────
city = st.selectbox("Select City/Airport", cities)
source_mode = st.selectbox("Sounding Source", ["AUTO", "IGRA", "UWYO"])

# ── Date and time selection ─────────────────────────────
from datetime import timedelta
yesterday = datetime.now() - timedelta(days=1)
fecha = st.date_input("Date", value=yesterday)
# Expand selection to synoptic hours (3-hourly)
hora_options = ["AUTO", "00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]
hora_str = st.selectbox("Hour (UTC)", hora_options)

# Prepare date strings
yr, mn, dy = str(fecha.year), f"{fecha.month:02}", f"{fecha.day:02}"

# Determine target hours to try
if hora_str == "AUTO":
    # Try standard synoptic times first, then intermediate
    hours_to_try = ["00", "12", "06", "18", "03", "09", "15", "21"]
else:
    # Use selected hour
    hours_to_try = [f"{datetime.strptime(hora_str, '%H:%M').hour:02}"]

# ── Display Mode Selection ──────────────────────────────
display_mode = st.radio("Display Mode", ["Simple", "Advanced"], index=0, horizontal=True)

# ── Generate sounding button ──────────────────────────────
if st.button("Generate Sounding"):
    try:
        with st.spinner("Downloading and processing data..."):
            # BUGFIX: Se usa la búsqueda exacta en el DF en lugar de find_station (búsqueda difusa)
            selected_row = stations_df[stations_df['display_name'] == city].iloc[0]
            CodEst = selected_row['code']
            station_name = selected_row['display_name']
            
            # Loop to find first available data
            p, T, Td, u, v, source_used = None, None, None, None, None, None
            last_error = None
            found_hr = None

            for test_hr in hours_to_try:
                try:
                    (p, T, Td, u, v), source_used = get_sounding(CodEst, yr, mn, dy, test_hr, source_mode)
                    found_hr = test_hr
                    break # Success!
                except Exception as e:
                    last_error = e
                    continue
            
            if found_hr is None:
                raise ValueError(f"No sounding found for date {yr}-{mn}-{dy} (Tried: {hours_to_try}). Last error: {last_error}")
            
            # Update hr to the one actually found for display purposes
            hr = found_hr

            # Map internal source code to user-friendly display name
            if source_used == "IGRA":
                source_display = "Integrated Global Radiosonde Archive (IGRA - NOAA)"
            elif source_used.startswith("UWYO"):
                source_display = "University of Wyoming Weather Web (UWYO)"
            else:
                source_display = source_used
            # ── Calculate variables ─────────────────────────────
            lcl_p, lcl_T = mpcalc.lcl(p[0], T[0], Td[0])
            parcel_prof = mpcalc.parcel_profile(p, T[0], Td[0])
            lfc_p, _ = mpcalc.lfc(p, T, Td, parcel_prof, which='bottom')
            ccl_p, ccl_T, ccl_Tc = mpcalc.ccl(p, T, Td, which='bottom')
            el_p,  _ = mpcalc.el (p, T, Td, parcel_prof, which='bottom')
            
            # Revert to using explicit parcel profile for CAPE/CIN to match plot exactly.
            cape, cin = mpcalc.cape_cin(p, T, Td, parcel_prof)
            
            # CUSTOM ROBUST CIN CALCULATION
            # A veces mpcalc.cape_cin se detiene en el primer EL o maneja múltiples capas de forma restrictiva.
            # Se requiere la inhibición total por debajo del nivel EL más alto.
            try:
                # Encontrar todos los ELs para obtener el superior
                # el_pressure, _ = mpcalc.el(p, T, Td, parcel_prof) # Esto devuelve solo uno.
                # Se realiza integración manual para mayor robustez.
                # B = (Tv_parcel - Tv_env) / Tv_env * g
                # Pero aproximación simple: Área entre T_parcel y T_env en el Skew-T (Rd * (T_p - T_e) dlnp)
                
                # Se requiere Temp. Virtual para una flotabilidad precisa
                # Tv = T * (1 + 0.61 * q) - aproximado por T si no se dispone fácilmente de la relación de mezcla, 
                # pero se usan los arrays del perfil directamente ya que parcel_prof suele ser T_virtual. 
                # ¿MetPy parcel_profile devuelve Temperatura, no Temperatura Virtual usualmente, a menos que se configure?
                # En realidad mpcalc.parcel_profile devuelve T de la parcela.
                # CAPE/CIN usan corrección de Temperatura Virtual.
                
                # Se utilizan los arrays proporcionados.
                # Identificar capas de flotabilidad negativa por debajo del EL (EL ya calculado como el_p)
                
                if not pd.isna(el_p) and len(p) > 1:
                    # Mask profile from surface to EL
                    mask_layer = (p <= p[0]) & (p >= el_p)
                    
                    if np.any(mask_layer):
                        p_layer = p[mask_layer]
                        T_layer = T[mask_layer]
                        prof_layer = parcel_prof[mask_layer]
                        
                        # Calculate difference (Parcel - Env). Negative = Inhibition
                        # Note: This is T, not Tv, so it's approx. but consistent with visual Skew-T T-lines.
                        diff = prof_layer - T_layer
                        
                        # Identify negative areas
                        neg_mask = diff < 0 * diff.units
                        
                        if np.any(neg_mask):
                            # Integrate using trapezoidal rule
                            # Energy = - Rd * Integral( (Tp - Te) / p * dp ) ??? 
                            # Standard Skew-T Area: Rd * integral ( (Tp - Te) d (ln p) )
                            # CIN is positive integral of negative buoyancy, or negative integral. 
                            # MetPy returns negative J/kg.
                            
                            # Simple integration or metpy.calc.apparent_temperature can be used
                            # CIN ~ Rd * integral( (T_par - T_env) * d(ln p) ) for T_par < T_env
                            
                            x = np.log(p_layer.magnitude)
                            y = diff.magnitude
                            
                            # Integrate only where y < 0
                            y_neg = y.copy()
                            y_neg[y > 0] = 0
                            
                            # Trapz integration (x is decreasing because p is decreasing)
                            # Area = integral y dx
                            # Rd_dry approx 287 J/(kg K)
                            Rd = 287.05
                            area = np.trapz(y_neg, x) * Rd
                            
                            # Area will be positive because x is decreasing (log(p) goes down) and y_neg is negative?
                            # x: log(1000) -> log(200). Decreasing. dx < 0.
                            # y_neg: < 0.
                            # y*dx > 0.
                            # So Area is positive J/kg representing the "energy" (CIN is usually negative).
                            # MetPy convention: CIN is negative.
                            
                            cin_manual = -1 * abs(area) * units('J/kg')
                            
                            # This is used if it is "more negative" (more inhibition) than the standard calculation,
                            # or if standard is 0 but this is not.
                            if cin_manual.magnitude < cin.magnitude:
                                cin = cin_manual

            except Exception as e:
                print(f"Error in manual CIN calc: {e}")

            # Ensure CAPE is not negative (floating point noise)
            if cape.magnitude < 0:
                cape = 0 * cape.units
            
            # Ensure CIN is negative or zero
            if cin.magnitude > 0:
                cin = 0 * cin.units
            
            # Formulate source URL for storage
            source_url = ""
            if source_used == "IGRA":
                source_url = f"https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/access/data-por/{CodEst}-data.txt.zip"
            elif source_used.startswith("UWYO"):
                 # Determinar si es BUFR o FM35
                src_param = source_used.split("-")[1] if "-" in source_used else "BUFR"
                wmo_code = CodEst[-5:]
                # Use WSGI endpoint
                source_url = (
                    f"https://weather.uwyo.edu/wsgi/sounding?"
                    f"datetime={yr}-{mn}-{dy}%20{hr}:00:00&id={wmo_code}&type=TEXT:LIST&src={src_param}"
                )
            st.session_state['sounding_data'] = {
                'p': p, 'T': T, 'Td': Td, 'u': u, 'v': v,
                'lcl_p': lcl_p, 'lcl_T': lcl_T, 'parcel_prof': parcel_prof,
                'lfc_p': lfc_p, 'ccl_p': ccl_p, 'el_p': el_p, 'cape': cape, 'cin': cin,
                'station_name': station_name, 'CodEst': CodEst,
                'yr': yr, 'mn': mn, 'dy': dy, 'hr': hr,
                'source_used': source_used, 'source_display': source_display, 'source_url': source_url
            }

    except Exception as e:
        st.error(f"❌ Error: {e}")

# Check if data exists in session state to display results
if 'sounding_data' in st.session_state:
    data = st.session_state['sounding_data']
    
    # Unpack variables for convenience
    p, T, Td, u, v = data['p'], data['T'], data['Td'], data['u'], data['v']
    lcl_p, lcl_T, parcel_prof = data['lcl_p'], data['lcl_T'], data['parcel_prof']
    lfc_p, ccl_p, el_p, cape, cin = data['lfc_p'], data['ccl_p'], data['el_p'], data['cape'], data['cin']
    station_name, CodEst = data['station_name'], data['CodEst']
    yr, mn, dy, hr = data['yr'], data['mn'], data['dy'], data['hr']
    source_used, source_display, source_url = data['source_used'], data['source_display'], data['source_url']

    st.write(f"Sounding retrieved from: **{source_display}**")
    st.write(f"Station: **{station_name} ({CodEst})**")

    if source_url:
        st.markdown(f"🔗 [View original data source]({source_url})")

    # ── Show results in columns ─────────────────
    st.markdown("### 📊 Indices and Levels")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("LCL", f"{lcl_p.magnitude:.1f} hPa")
    col2.metric("CCL", f"{ccl_p.magnitude:.1f} hPa" if not pd.isna(ccl_p.magnitude) else "N/A")
    col3.metric("LFC", f"{lfc_p.magnitude:.1f} hPa" if not pd.isna(lfc_p.magnitude) else "N/A")
    col4.metric("EL", f"{el_p.magnitude:.1f} hPa" if not pd.isna(el_p.magnitude) else "N/A")
    
    colA, colB = st.columns(2)
    colA.metric("CAPE", f"{cape.magnitude:.0f} J/kg")
    colB.metric("CIN", f"{cin.magnitude:.0f} J/kg")


    # ── Plot Skew-T ────────────────────────────────
    tab_static, tab_interactive, tab_interpretation = st.tabs(["🖼️ Static (MetPy)", "🔍 Interactive (Plotly)", "❓ Interpretation"])
    
    with tab_static:
        import matplotlib.gridspec as gridspec
        
        # Create figure
        fig = plt.figure(figsize=(17, 12), dpi=900)
        
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
        
        # Add title: Place, Station Code, Date
        # Centered on the entire figure as requested
        if display_mode == "Advanced":
            fig.suptitle(f"{station_name} ({CodEst}) — {yr}-{mn}-{dy} {hr}Z", fontsize=16, fontweight='bold', x=0.53, y=0.925)
        else:
            fig.suptitle(f"{station_name} ({CodEst}) — {yr}-{mn}-{dy} {hr}Z", fontsize=16, fontweight='bold', x=0.515, y=0.925)

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

        # Plot Wind Barbs (Decimated)
        if not np.isnan(u).all() and not np.isnan(v).all():
                # Conditional spacing based on source
                if source_used.startswith("UWYO"):
                    step = 45 # Even more spacing for UWYO as requested
                else:
                    step = 3  # Tighter spacing for IGRA as requested (<=5)
                
                skew.plot_barbs(p[::step], u[::step], v[::step])

        if cape > 0:
            skew.shade_cape(p, T, parcel_prof)
        
        # Restrict CIN to area below LFC
        if not pd.isna(lfc_p.magnitude):
            mask_cin = p >= lfc_p
            skew.shade_cin(p[mask_cin], T[mask_cin], parcel_prof[mask_cin])

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
            try:
                # 1. Thermodynamic Indices
                sbcape, sbcin = mpcalc.surface_based_cape_cin(p, T, Td)
                ml_cape, ml_cin = mpcalc.mixed_layer_cape_cin(p, T, Td, depth=50 * units.hPa)
                mu_cape, mu_cin = mpcalc.most_unstable_cape_cin(p, T, Td, depth=50 * units.hPa)
                tt_idx = mpcalc.total_totals_index(p, T, Td)
                k_idx = mpcalc.k_index(p, T, Td)
                
                # 2. Kinematic Indices & Storm Motion
                # Drop NaNs from wind for calculations to avoid errors
                # (MetPy functions often handle this, but being safe)
                
                # Calcular altura geométrica (z) usando suposición hidrostática si no está presente
                # Se requiere la altura para SRH y Bunkers
                # Calcular aproximación de altura sobre el nivel del suelo (AGL)
                z = mpcalc.pressure_to_height_std(p)
                z = z - z[0] # AGL
                
                # Bunkers Storm Motion (Right Mover, Left Mover, Mean Wind)
                # Asegurar que no hay NaNs en el perfil usado
                mask = ~np.isnan(u) & ~np.isnan(v) & ~np.isnan(p)
                u_masked, v_masked, z_masked = u[mask], v[mask], z[mask]
                
                # Bunkers
                RM, LM, MW = mpcalc.bunkers_storm_motion(p[mask], u[mask], v[mask], z[mask])
                
                # Helper for SRH
                def calc_srh(depth_m):
                    try:
                        srh = mpcalc.storm_relative_helicity(z[mask], u[mask], v[mask], depth=depth_m * units.m,
                                                            storm_u=RM[0], storm_v=RM[1])[0]
                        return srh
                    except: return np.nan * units.m**2/units.s**2

                srh_1km = calc_srh(1000)
                srh_3km = calc_srh(3000)
                
                # Bulk Shear
                def calc_shear(depth_m):
                    try:
                        sh_u, sh_v = mpcalc.bulk_shear(p[mask], u[mask], v[mask], height=z[mask], depth=depth_m * units.m)
                        return mpcalc.wind_speed(sh_u, sh_v)
                    except: return np.nan * units.kt

                shear_1km = calc_shear(1000)
                shear_3km = calc_shear(3000)
                shear_6km = calc_shear(6000)

                # 3. Composite Indices
                # Significant Tornado Parameter (fixed layer)
                # Requires LCL height
                lcl_pressure, lcl_temperature = mpcalc.lcl(p[0], T[0], Td[0])
                # Approx LCL height AGL
                lcl_z = mpcalc.pressure_to_height_std(lcl_pressure) - mpcalc.pressure_to_height_std(p[0])
                
                sig_tor = mpcalc.significant_tornado(sbcape, lcl_z, srh_1km, shear_6km)
                
                # Supercell Composite
                # SCP = (MUCAPE / 1000) * (SRH3km / 150) * (Shear6km / 40)
                sup_comp = mpcalc.supercell_composite(mu_cape, srh_3km, shear_6km)
                
                # ── Draw Storm Motion on Hodograph ────────────────
                # Plot Bunkers RM, LM, MW
                # RM
                h.ax.text(RM[0].magnitude, RM[1].magnitude, 'RM', weight='bold', ha='left', fontsize=8, color='black', clip_on=True)
                h.ax.plot(RM[0].magnitude, RM[1].magnitude, 'ko', markersize=4)
                # LM
                h.ax.text(LM[0].magnitude, LM[1].magnitude, 'LM', weight='bold', ha='left', fontsize=8, color='black', clip_on=True)
                h.ax.plot(LM[0].magnitude, LM[1].magnitude, 'ko', markersize=4)
                
                # Arrow from origin to RM (optional, can clutter)
                
            except Exception as e:
                print(f"Error calculating advanced indices: {e}")
                sbcape, sbcin, ml_cape, ml_cin, mu_cape, mu_cin = [0*units.J/units.kg]*6
                tt_idx, k_idx = 0, 0
                srh_1km, srh_3km = 0*units.m**2/units.s**2, 0*units.m**2/units.s**2
                shear_1km, shear_3km, shear_6km = 0*units.kt, 0*units.kt, 0*units.kt
                sig_tor, sup_comp = [0], [0]


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
        license_text = (
            "MeTroV © 2026 by Óscar Mata-Romero is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International\n"
            f"Data: {source_url}"
        )
        plt.figtext(0.5, 0.01, license_text, ha="center", va="bottom", fontsize=8, color='gray')

        # Save high-res image to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        
        # Display image directly
        st.image(buf, output_format="PNG")
        
        # Add download button for full quality
        st.download_button(
            label="💾 Download High-Res Image",
            data=buf,
            file_name=f"skewt_{station_name}_{yr}{mn}{dy}_{hr}.png",
            mime="image/png"
        )
        
        # Close figure
        plt.close(fig)
        
    with tab_interactive:
        st.info("💡 Experimental interactive chart (manually transformed axes to simulate Skew-T) should not be used for quantitative interpretation.")
        fig_plotly = create_skewt_plotly(p, T, Td, station_name, f"{yr}-{mn}-{dy} {hr}Z")
        st.plotly_chart(fig_plotly, width="stretch")

    with tab_interpretation:
        st.markdown(get_interpretation_text())

st.markdown(
    f"""<hr style="margin-top: 3rem; margin-bottom: 1rem;">
<div style="text-align: center; font-size: 0.85em; color: gray;">
<div style="margin-bottom: 5px;">MeTroV (v1.1.1) — Data: NOAA IGRA & University of Wyoming</div>
<div xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/">
<a property="dct:title" rel="cc:attributionURL" href="https://metrovgit.streamlit.app/" style="color: inherit; text-decoration: none;">MeTroV</a> © <span id="copyrightYear">{datetime.now().year}</span> by <a rel="cc:attributionURL dct:creator" property="cc:attributionName" href="https://sites.google.com/view/oscarmr-en">Óscar Mata-Romero</a>.
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



