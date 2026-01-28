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
from metpy.units import units

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
            # Ensure CAPE is not negative
            if cape.magnitude < 0:
                cape = 0 * cape.units
            
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
    tab_static, tab_interactive, tab_interpretation = st.tabs(["🖼️ Static (MetPy)", "🔍 Interactive (Plotly)", "❓ Interpretation"])
    
    with tab_static:
        fig = plt.figure(figsize=(9, 12), dpi=900)
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
        # Add patches for CAPE/CIN
        patch_cape = Patch(color='orangered', alpha=0.3, label=f"CAPE")
        patch_cin  = Patch(color='cornflowerblue', alpha=0.3, label=f"CIN")
        patch_clouds = Patch(color='gray', alpha=0.4, label='Cloud layer')

        handles.extend([patch_cape, patch_cin, patch_clouds])
        
        skew.ax.legend(handles=handles, loc='upper left')

        # ── Cloud Layer Indicator ───────────────────────
        # Estimate clouds where Dewpoint Depression is low (< 3-5 C)
        # Using 3 degC as a threshold for "cloudy"
        try:
            # Calculate depression.
            # Convert to numpy magnitudes to avoid issues with fill_betweenx and transforms
            t_vals = T.to(units.degC).magnitude
            td_vals = Td.to(units.degC).magnitude
            p_vals = p.to(units.hPa).magnitude
            
            dd = t_vals - td_vals
            
            # Threshold: 3 degrees C
            # We treat NaNs as False (no cloud)
            is_cloud = (dd < 3.0) & (~np.isnan(dd))
            
            # Plot vertical strip
            # Using simple values for p and x limits
            # x values in axes coordinates (0-1), y values in data coordinates (pressure)
            skew.ax.fill_betweenx(p_vals, 0, 0.03, where=is_cloud, color='gray', alpha=0.4, transform=skew.ax.get_yaxis_transform())
            
        except Exception as e:
            # Fallback
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

    with tab_interpretation:
        st.markdown("""
       ### 1. LCL: Lifting Condensation Level

        *   It is the height at which the air, upon rising and cooling, becomes saturated (reaches 100% humidity) and water vapor begins to condense into droplets.
        *   It marks the **cloud base** (usually cumulus).
        *   **What happens here?** Below this level, the air is "dry" (unsaturated); right at this level, the cloud forms (Yau & Rogers, 1996; Lohmann et al., 2016).

        ### 2. CIN: Convective Inhibition

        *   It is the "negative energy" or barrier that prevents air from rising on its own. It is usually caused by a thermal inversion (warm air over cold air) acting as a lid.
        *   It represents the amount of external energy we need to apply (push) to the air parcel so it can cross that stable zone and reach the point where it can rise on its own (Lohmann et al., 2016; Houze, 2014).
        *   **Thresholds** (Houze, 2014):
            *   **Low:** < 15 J/kg (Easy to break, storms form early).
            *   **High:** > 100 J/kg (It is very difficult for storms to form unless there is a very strong external forcing, like a cold front).

        ### 3. LFC: Level of Free Convection

        *   It is the exact height where the air parcel becomes warmer (and less dense) than the surrounding air.
        *   It is the "release point". Once the parcel exceeds this height, it no longer needs to be pushed; it starts rising spontaneously like a hot air balloon due to its positive buoyancy (Iribarne & Godson, 1981).
        *   If the CIN is not broken, the parcel never reaches the LFC and there is no storm.

        ### 4. CAPE: Convective Available Potential Energy

        *   It is the storm's "fuel". It measures the total amount of energy the parcel accumulates while rising freely (from the LFC upwards) being warmer than the environment.
        *   The higher the CAPE, the faster the ascent velocity (updraft) and the more intense the storm can be (Lohmann et al., 2016; Houze, 2014).
        *   **Thresholds** (Lohmann et al., 2016; Wallace & Hobbs, 2006):
            *   **0 J/kg:** Stable (no convection).
            *   **< 1000 J/kg:** Marginal instability (weak convection).
            *   **1000 - 2500 J/kg:** Moderate instability (ordinary storms).
            *   **2500 - 4000 J/kg:** Very unstable (severe storms, possible large hail or tornadoes).
            *   **> 4000 J/kg:** Extremely unstable.

        ### 5. EL: Equilibrium Level (or LNB)
        *(Level of Neutral Buoyancy)*

        *   It is the height where the air parcel stops being warmer than the environment. Its temperature equalizes with the ambient temperature and it loses its buoyancy.
        *   It marks the **cloud top** (the anvil of the cumulonimbus). Although inertia may cause the cloud to rise a bit more ("overshooting top"), this is where the cloud stops growing actively (Lohmann et al., 2016; Houze, 2014).

        ### 6. Cloud Layers & Formation Analysis
        
        To identify potential cloud layers from a sounding, we analyze the proximity of Temperature ($T$) and Dewpoint ($T_d$) curves and parcel ascent paths.

        #### A. Stratiform Clouds (Layered)
        For stable cloud layers (Stratus, Altostratus), we look for high relative humidity:
        *   **Proximity of curves:** Clouds likely exist where the $T$ and $T_d$ lines are very close or touching.
        *   **Dewpoint Depression:** In practice, a depression ($T - T_d$) of **< 3°C to 5°C** usually indicates cloud formation.
        *   **Thickness:** The cloud layer extends vertically as long as these lines remain close. A sudden separation indicates dry air and the cloud top/base.

        #### B. Convective Clouds (Cumulus)
        For clouds formed by rising air currents:
        *   **Cloud Base:** Marked by the **LCL** (forced ascent) or **CCL** (Convective Condensation Level, from surface heating).
        *   **Vertical Development:** Occurs along the saturated adiabat as long as the parcel is warmer than the environment ($T_{parcel} > T_{env}$), indicated by positive **CAPE**.
        *   **Cloud Top:** Theoretically at the **EL/LNB**, where buoyancy becomes neutral. Strong updrafts may penetrate higher (overshooting tops).

        #### C. Boundary Layer & Fog
        *   **Stratocumulus:** Often found at the top of the planetary boundary layer, capped by a temperature inversion (T increases with height) and a sharp drying (lines separate).
        *   **Fog:** Essentially a cloud on the ground. Indicated when $T \approx T_d$ at the surface pressure level.

        ---

        ### References
        *   Lohmann, U., Lüönd, F., & Mahrt, F. (2016). *An introduction to clouds: From the microscale to climate*. Cambridge University Press.
        *   Houze, R. A., Jr. (2014). *Cloud dynamics* (2nd ed., Vol. 104). Academic Press. https://doi.org/10.1016/C2010-0-66412-6
        *   Wallace, J. M., & Hobbs, P. V. (2006). *Atmospheric science: An introductory survey* (2nd ed.). Academic Press.
        *   Iribarne, J. V., & Godson, W. L. (1981). *Atmospheric thermodynamics*. D. Reidel Publishing Company.
        *   Yau, M. K., & Rogers, R. R. (1996). *A short course in cloud physics* (3rd ed.). Pergamon.
        """)

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

