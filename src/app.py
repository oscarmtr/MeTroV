# src/app.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
from PIL import Image

# Suppress DecompressionBombWarning for high-res plots requested by user
Image.MAX_IMAGE_PIXELS = None

import pathlib
from stations import find_station
from sondeo import get_sounding
from sondeo_plotly import create_skewt_plotly
from metpy.plots import SkewT
from matplotlib.patches import Patch
import matplotlib.pyplot as plt
import metpy.calc as mpcalc

st.set_page_config(page_title="MeTroV", layout="centered")

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




# ── Load station list ─────────────────────────────
script_dir = pathlib.Path(__file__).parent.absolute()
STATION_FILE = script_dir.parent / "data" / "igra_stations_all.csv"

# Automatically update station list if needed
with st.spinner("Checking for station updates..."):
    # Reuse the update logic from stations module
    # We need to import it. Since 'from stations import find_station' is at top, 
    # we can import the module or function here.
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

# ── Generate sounding button ──────────────────────────────
if st.button("Generate Sounding"):
    try:
        with st.spinner("Downloading and processing data..."):
            # BUGFIX: Usar búsqueda exacta en el DF en lugar de find_station (que es difusa)
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
            el_p,  _ = mpcalc.el (p, T, Td, parcel_prof, which='bottom')
            cape, cin = mpcalc.cape_cin(p, T, Td, parcel_prof)
            
            # Formulate source URL for storage
            source_url = ""
            if source_used == "IGRA":
                source_url = f"https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/access/data-por/{CodEst}-data.txt.zip"
            elif source_used.startswith("UWYO"):
                 # Get if BUFR or FM35
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
                'lfc_p': lfc_p, 'el_p': el_p, 'cape': cape, 'cin': cin,
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
    lfc_p, el_p, cape, cin = data['lfc_p'], data['el_p'], data['cape'], data['cin']
    station_name, CodEst = data['station_name'], data['CodEst']
    yr, mn, dy, hr = data['yr'], data['mn'], data['dy'], data['hr']
    source_used, source_display, source_url = data['source_used'], data['source_display'], data['source_url']

    st.write(f"Sounding retrieved from: **{source_display}**")
    st.write(f"Station: **{station_name} ({CodEst})**")

    if source_url:
        st.markdown(f"🔗 [View original data source]({source_url})")

    # ── Show results in columns ─────────────────
    st.markdown("### 📊 Indices and Levels")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("LCL", f"{lcl_p.magnitude:.1f} hPa")
    col2.metric("LFC", f"{lfc_p.magnitude:.1f} hPa" if not pd.isna(lfc_p.magnitude) else "N/A")
    col3.metric("EL", f"{el_p.magnitude:.1f} hPa" if not pd.isna(el_p.magnitude) else "N/A")

    colA, colB = st.columns(2)
    colA.metric("CAPE", f"{cape.magnitude:.0f} J/kg")
    colB.metric("CIN", f"{cin.magnitude:.0f} J/kg")


    # ── Plot Skew-T ────────────────────────────────
    tab_static, tab_interactive = st.tabs(["🖼️ Static (MetPy)", "🔍 Interactive (Plotly)"])
    
    with tab_static:
        fig = plt.figure(figsize=(9, 12), dpi=1200)
        skew = SkewT(fig, rotation=45)
        
        # Add title: Place, Station Code, Date
        plt.title(f"{station_name} ({CodEst}) — {yr}-{mn}-{dy} {hr}Z", fontsize=12)

        skew.plot(p, T, 'r', label='T')
        skew.plot(p, Td, 'g', label='Td')
        skew.plot(p, parcel_prof, 'k--') # No label for Parcel as requested
        
        # Custom Legend with CAPE/CIN
        handles, labels = skew.ax.get_legend_handles_labels()
        
        # Add patches for CAPE/CIN
        patch_cape = Patch(color='orangered', alpha=0.3, label=f"CAPE")
        patch_cin  = Patch(color='cornflowerblue', alpha=0.3, label=f"CIN")
        
        handles.extend([patch_cape, patch_cin])
        
        skew.ax.legend(handles=handles, loc='upper left')

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
        # else: do not paint CIN if no LFC (stable profile)

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
            (lfc_p, 'LFC', 'blue'),
            (el_p,  'EL',  'darkorchid')
        ]

        for p_level, label, color in level_config:
            if not pd.isna(p_level.magnitude) and 75 <= p_level.magnitude <= 1050:
                skew.ax.axhline(p_level.magnitude, linestyle='--', color=color, linewidth=1.5)
                skew.ax.text(-38, p_level.magnitude - 5, label, color=color, fontsize=10, fontweight='bold')

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

st.markdown(
    f"""<hr style="margin-top: 3rem; margin-bottom: 1rem;">
<div style="text-align: center; font-size: 0.85em; color: gray;">
<div style="margin-bottom: 5px;">MeTroV (v1.0.0) — Data: NOAA IGRA & University of Wyoming</div>
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

