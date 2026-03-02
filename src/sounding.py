# =========================
# sounding.py
# =========================

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import pathlib
import io
import requests
import zipfile
from io import StringIO

import metpy.calc as mpcalc
from metpy.plots import SkewT, Hodograph
from metpy.units import units
from matplotlib.patches import Patch
import matplotlib.gridspec as gridspec

# =====================================
# USER CONFIGURATION
# =====================================
STATION_CODE = "AAA00001111"  # "AAA00001111" (ID used to download data) check "/data/igra_stations.csv"
CITY = "City"               # String to display in the plot title
DATE_YEAR = "2026"
DATE_MONTH = "01"
DATE_DAY = "14"
TIME_HOUR = "00"
SOURCE_MODE = "AUTO"     # "IGRA" | "UWYO" | "AUTO"
PLOT_MODE = "SIMPLE"   # "SIMPLE" | "ADVANCED"

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

# =====================================
# SCRIPT PRINCIPAL
# =====================================
if __name__ == "__main__":
    CodEst = STATION_CODE.strip()
    station_name = CITY.strip()
    yr, mn, dy, hr = DATE_YEAR, DATE_MONTH, DATE_DAY, TIME_HOUR
    source_mode = SOURCE_MODE

    print(f"Searching sounding for {station_name} ({CodEst}) on {yr}-{mn}-{dy} at {hr}Z...")

    # Descargar sondeo según fuente elegida
    (p, T, Td, u, v), source_used = get_sounding(CodEst, yr, mn, dy, hr, source_mode)
    print(f"Sounding downloaded from: {source_used}")

    # =====================================
    # METPY - CALCULOS
    # =====================================
    lcl_p, lcl_T = mpcalc.lcl(p[0], T[0], Td[0])
    parcel_prof = mpcalc.parcel_profile(p, T[0], Td[0])
    lfc_p, _ = mpcalc.lfc(p, T, Td, parcel_prof, which='bottom')
    ccl_p, ccl_T, ccl_Tc = mpcalc.ccl(p, T, Td, which='bottom')
    el_p,  _ = mpcalc.el(p, T, Td, parcel_prof, which='bottom')
    
    # Custom Graphic-matched CIN and CAPE
    el_p_top, _ = mpcalc.el(p, T, Td, parcel_prof, which='top')
    
    cape = 0 * units('J/kg')
    cin = 0 * units('J/kg')
    
    try:
        mask_calc_all = (p >= el_p_top)
        p_calc = p[mask_calc_all]
        T_calc = T[mask_calc_all]
        prof_calc = parcel_prof[mask_calc_all]
        
        diff = prof_calc - T_calc
        x = np.log(p_calc.magnitude)
        y = diff.magnitude
        Rd = 287.05 # Gas constant for dry air
        
        # 1. Calculate Graphic-matched CIN (Negative areas below LFC)
        y_neg = y.copy()
        y_neg[y > 0] = 0
        if not pd.isna(lfc_p.magnitude):
            mask_cin_graphic = p_calc >= lfc_p
            y_neg[~mask_cin_graphic] = 0
            
        if np.any(y_neg < 0):
            area_cin = np.trapezoid(y_neg, x) * Rd
            cin = -1 * abs(area_cin) * units('J/kg')
            
        # 2. Calculate Graphic-matched CAPE (Positive areas above LFC)
        y_pos = y.copy()
        y_pos[y < 0] = 0
        if not pd.isna(lfc_p.magnitude):
            mask_cape_graphic = p_calc <= lfc_p
            y_pos[~mask_cape_graphic] = 0
            
        if np.any(y_pos > 0):
            area_cape = np.trapezoid(y_pos, x) * Rd
            cape = abs(area_cape) * units('J/kg')
            
    except Exception as e:
        cape, cin = mpcalc.cape_cin(p, T, Td, parcel_prof)

    # =====================================
    # METPY - INDICES AVANZADOS
    # =====================================
    sbcape, sbcin = mpcalc.surface_based_cape_cin(p, T, Td)
    ml_cape, ml_cin = mpcalc.mixed_layer_cape_cin(p, T, Td, depth=50 * units.hPa)
    mu_cape, mu_cin = mpcalc.most_unstable_cape_cin(p, T, Td, depth=50 * units.hPa)
    tt_idx = mpcalc.total_totals_index(p, T, Td)
    k_idx = mpcalc.k_index(p, T, Td)
    
    z = mpcalc.pressure_to_height_std(p)
    z = z - z[0] # AGL
    
    mask = ~np.isnan(u) & ~np.isnan(v) & ~np.isnan(p)
    u_masked, v_masked, z_masked = u[mask], v[mask], z[mask]
    
    try:
        RM, LM, MW = mpcalc.bunkers_storm_motion(p[mask], u[mask], v[mask], z[mask])
    except:
        RM, LM, MW = [np.nan]*3, [np.nan]*3, [np.nan]*3

    def calc_srh(depth_m):
        try:
            srh = mpcalc.storm_relative_helicity(z[mask], u[mask], v[mask], depth=depth_m * units.m,
                                                storm_u=RM[0], storm_v=RM[1])[0]
            return srh
        except: return np.nan * units.m**2/units.s**2

    srh_1km = calc_srh(1000)
    srh_3km = calc_srh(3000)
    
    def calc_shear(depth_m):
        try:
            sh_u, sh_v = mpcalc.bulk_shear(p[mask], u[mask], v[mask], height=z[mask], depth=depth_m * units.m)
            return mpcalc.wind_speed(sh_u, sh_v)
        except: return np.nan * units.kt

    shear_1km = calc_shear(1000)
    shear_3km = calc_shear(3000)
    shear_6km = calc_shear(6000)

    lcl_pressure, lcl_temperature = mpcalc.lcl(p[0], T[0], Td[0])
    lcl_z = mpcalc.pressure_to_height_std(lcl_pressure) - mpcalc.pressure_to_height_std(p[0])
    
    try:
        sig_tor = mpcalc.significant_tornado(sbcape, lcl_z, srh_1km, shear_6km)
    except:
        sig_tor = [np.nan]
        
    try:
        sup_comp = mpcalc.supercell_composite(mu_cape, srh_3km, shear_6km)
    except:
        sup_comp = [np.nan]

    # =====================================
    # GRAPHICS (APP.PY - ADVANCED STYLE)
    # =====================================
    print(f"Generating {PLOT_MODE} plot...")
    fig = plt.figure(figsize=(17, 12), dpi=900)
    
    if PLOT_MODE == "ADVANCED":
        gs = gridspec.GridSpec(1, 2, figure=fig, width_ratios=[1.4, 0.6], wspace=0.01)
        gs_right = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[1], height_ratios=[0.9, 1.1], hspace=0.1)
    else:
        gs = gridspec.GridSpec(1, 1, figure=fig)
        gs_right = None

    # --- SkewT Panel ---
    skew = SkewT(fig, rotation=45, subplot=gs[0])
    
    if PLOT_MODE == "ADVANCED":
        fig.suptitle(f"{station_name} ({CodEst}) — {yr}-{mn}-{dy} {hr}Z", fontsize=16, fontweight='bold', x=0.53, y=0.925)
    else:
        fig.suptitle(f"{station_name} ({CodEst}) — {yr}-{mn}-{dy} {hr}Z", fontsize=16, fontweight='bold', x=0.515, y=0.925)

    skew.plot(p, T, 'r', label='T')
    skew.plot(p, Td, 'g', label='Td')
    skew.plot(p, parcel_prof, 'k--') 
    
    handles, labels = skew.ax.get_legend_handles_labels()
    patch_cape = Patch(color='orangered', alpha=0.3, label=f"CAPE")
    patch_cin  = Patch(color='cornflowerblue', alpha=0.3, label=f"CIN")
    patch_clouds = Patch(color='gray', alpha=0.4, label='Cloud layer')
    handles.extend([patch_cape, patch_cin, patch_clouds])
    skew.ax.legend(handles=handles, loc='upper left', framealpha=1)

    try:
        t_vals = T.to(units.degC).magnitude
        td_vals = Td.to(units.degC).magnitude
        p_vals = p.to(units.hPa).magnitude
        dd = t_vals - td_vals
        is_cloud = (dd < 3.0) & (~np.isnan(dd))
        skew.ax.fill_betweenx(p_vals, 0, 0.03, where=is_cloud, color='gray', alpha=0.4, transform=skew.ax.get_yaxis_transform())
    except Exception as e:
        pass

    if not np.isnan(u).all() and not np.isnan(v).all():
        step = 45 if source_used.startswith("UWYO") else 3
        skew.plot_barbs(p[::step], u[::step], v[::step])

    # Restrict CIN to area below LFC and EL
    if not pd.isna(lfc_p.magnitude):
        mask_cin = (p >= lfc_p)
        if el_p_top is not None and not pd.isna(el_p_top):
            mask_cin = mask_cin & (p >= el_p_top)
        skew.shade_cin(p[mask_cin], T[mask_cin], parcel_prof[mask_cin])

    # Shade CAPE
    if not pd.isna(lfc_p):
        mask_cape = p <= lfc_p
        if el_p_top is not None and not pd.isna(el_p_top):
            mask_cape = mask_cape & (p >= el_p_top)
        skew.shade_cape(p[mask_cape], T[mask_cape], parcel_prof[mask_cape])

    skew.ax.set_ylim(1050, 75)
    skew.ax.set_xlim(-40, 40)
    skew.ax.set_ylabel("Pressure (hPa)")
    skew.ax.set_xlabel("Temperature (ºC)")

    skew.plot_dry_adiabats()
    skew.plot_moist_adiabats()
    skew.plot_mixing_lines()
    
    level_config = [
        (lcl_p, 'LCL', 'sienna'),
        (ccl_p, 'CCL', 'darkorange'),
        (lfc_p, 'LFC', 'blue'),
        (el_p,  'EL',  'darkorchid')
    ]

    for p_level, label, color in level_config:
        if not pd.isna(p_level.magnitude) and 75 <= p_level.magnitude <= 1050:
            skew.ax.axhline(p_level.magnitude, linestyle='--', color=color, linewidth=1.5)
            skew.ax.text(-38, p_level.magnitude - 5, label, color=color, fontsize=10, fontweight='bold')

    if PLOT_MODE == "ADVANCED" and gs_right is not None:
        # --- Hodograph Panel ---
        ax_hod = fig.add_subplot(gs_right[0])
        h = Hodograph(ax_hod, component_range=80.)
        h.add_grid(increment=20, ls='-', lw=1.5, alpha=0.5)
        h.add_grid(increment=10, ls='--', lw=1, alpha=0.2)
        h.ax.set_yticklabels([])
        h.ax.set_xticklabels([])
        h.ax.set_xticks([])
        h.ax.set_yticks([])
        h.ax.set_xlabel(' ')
        h.ax.set_ylabel(' ')

        for i in range(10, 90, 20):
            h.ax.annotate(str(i), (i, 0), xytext=(0, 2), textcoords='offset pixels', clip_on=True, fontsize=8, weight='bold', alpha=0.5, zorder=0)
            h.ax.annotate(str(i), (0, i), xytext=(0, 2), textcoords='offset pixels', clip_on=True, fontsize=8, weight='bold', alpha=0.5, zorder=0)
    
        wind_speed = mpcalc.wind_speed(u, v)
        lc = h.plot_colormapped(u, v, wind_speed)
    
        ax_cbar = ax_hod.inset_axes([1.02, 0.25, 0.05, 0.5])
        cbar = plt.colorbar(lc, cax=ax_cbar)
        cbar.set_label('Wind Speed (knots)', fontsize=10)
        cbar.ax.tick_params(labelsize=8)

        try:
            h.ax.text(RM[0].magnitude, RM[1].magnitude, 'RM', weight='bold', ha='left', fontsize=8, color='black', clip_on=True)
            h.ax.plot(RM[0].magnitude, RM[1].magnitude, 'ko', markersize=4)
            h.ax.text(LM[0].magnitude, LM[1].magnitude, 'LM', weight='bold', ha='left', fontsize=8, color='black', clip_on=True)
            h.ax.plot(LM[0].magnitude, LM[1].magnitude, 'ko', markersize=4)
        except:
            pass

        # --- Statistics Panel ---
        ax_stats = fig.add_subplot(gs_right[1])
        ax_stats.axis('off') 
    
        rect = plt.Rectangle((0, 0), 1, 1, fill=False, color='black', lw=1, transform=ax_stats.transAxes)
        ax_stats.add_patch(rect)
    
        def fmt(val, precision=0):
            try:
                if hasattr(val, 'magnitude'): v = val.magnitude
                else: v = val
                if hasattr(v, 'item'): v = v.item()
                if pd.isna(v): return "-"
                return f"{v:.{precision}f}"
            except: return "-"

        c1_center, c2_center = 0.25, 0.75
        ax_stats.text(c1_center, 0.92, "THERMODYNAMIC", weight='bold', fontsize=9, ha='center', color='black', transform=ax_stats.transAxes)
        ax_stats.text(c2_center, 0.92, "KINEMATIC", weight='bold', fontsize=9, ha='center', color='black', transform=ax_stats.transAxes)
        ax_stats.plot([0, 1], [0.88, 0.88], color='black', lw=0.5, transform=ax_stats.transAxes)
        ax_stats.plot([0.5, 0.5], [0, 1], color='black', lw=0.5, transform=ax_stats.transAxes)

        y_curr, y_step = 0.80, 0.10
        x1_lbl, x1_val = 0.05, 0.45
        x2_lbl, x2_val = 0.55, 0.95

        # Row 1
        ax_stats.text(x1_lbl, y_curr, "SBCAPE", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x1_val, y_curr, fmt(sbcape), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)
        ax_stats.text(x2_lbl, y_curr, "Sfc-1km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x2_val, y_curr, fmt(shear_1km) + " kt", fontsize=9, weight='bold', color='blue', ha='right', transform=ax_stats.transAxes)
        y_curr -= y_step
    
        # Row 2
        ax_stats.text(x1_lbl, y_curr, "SBCIN", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x1_val, y_curr, fmt(sbcin), fontsize=9, weight='bold', color='cornflowerblue', ha='right', transform=ax_stats.transAxes)
        ax_stats.text(x2_lbl, y_curr, "Sfc-3km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x2_val, y_curr, fmt(shear_3km) + " kt", fontsize=9, weight='bold', color='blue', ha='right', transform=ax_stats.transAxes)
        y_curr -= y_step
    
        # Row 3
        ax_stats.text(x1_lbl, y_curr, "MLCAPE", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x1_val, y_curr, fmt(ml_cape), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)
        ax_stats.text(x2_lbl, y_curr, "Sfc-6km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x2_val, y_curr, fmt(shear_6km) + " kt", fontsize=9, weight='bold', color='blue', ha='right', transform=ax_stats.transAxes)
        y_curr -= y_step
    
        # Row 4
        ax_stats.text(x1_lbl, y_curr, "MLCIN", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x1_val, y_curr, fmt(ml_cin), fontsize=9, weight='bold', color='cornflowerblue', ha='right', transform=ax_stats.transAxes)
        ax_stats.text(x2_lbl, y_curr, "SRH 1km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x2_val, y_curr, fmt(srh_1km), fontsize=9, weight='bold', color='navy', ha='right', transform=ax_stats.transAxes)
        y_curr -= y_step
    
        # Row 5
        ax_stats.text(x1_lbl, y_curr, "MUCAPE", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x1_val, y_curr, fmt(mu_cape), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)
        ax_stats.text(x2_lbl, y_curr, "SRH 3km", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x2_val, y_curr, fmt(srh_3km), fontsize=9, weight='bold', color='navy', ha='right', transform=ax_stats.transAxes)
        y_curr -= y_step
    
        # Row 6
        ax_stats.text(x1_lbl, y_curr, "MUCIN", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x1_val, y_curr, fmt(mu_cin), fontsize=9, weight='bold', color='cornflowerblue', ha='right', transform=ax_stats.transAxes)
        y_curr -= 1.5*y_step
    
        # Row 7
        ax_stats.text(x1_lbl, y_curr, "TT Index", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x1_val, y_curr, fmt(tt_idx), fontsize=9, weight='bold', color='black', ha='right', transform=ax_stats.transAxes)
        ax_stats.text(x2_lbl, y_curr, "SIGTOR", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        stpv = sig_tor[0] if isinstance(sig_tor, list) else sig_tor
        ax_stats.text(x2_val, y_curr, fmt(stpv, 1), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)
        y_curr -= y_step
    
        # Row 8
        ax_stats.text(x1_lbl, y_curr, "K Index", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        ax_stats.text(x1_val, y_curr, fmt(k_idx), fontsize=9, weight='bold', color='black', ha='right', transform=ax_stats.transAxes)
        ax_stats.text(x2_lbl, y_curr, "SUPCELL", fontsize=9, weight='bold', transform=ax_stats.transAxes)
        scpv = sup_comp[0] if isinstance(sup_comp, list) else sup_comp
        ax_stats.text(x2_val, y_curr, fmt(scpv, 1), fontsize=9, weight='bold', color='orangered', ha='right', transform=ax_stats.transAxes)

    # --- Output ---
    script_dir = pathlib.Path(__file__).parent.absolute()
    output_path = script_dir.parent / "outputs" / "skewt_standalone.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=900, bbox_inches='tight', pad_inches=0.2, format='pdf')
    print(f"Plot saved at: {output_path}")

    # --- Export CSV ---
    csv_output_path = script_dir.parent / "outputs" / "skewt_standalone_metrics.csv"
    
    def fmt_val(val, precision=2):
        try:
            if hasattr(val, 'magnitude'): v = val.magnitude
            else: v = val
            if hasattr(v, 'item'): v = v.item()
            if pd.isna(v): return "N/A"
            return f"{v:.{precision}f}"
        except: return "N/A"

    stpv = sig_tor[0] if isinstance(sig_tor, list) else sig_tor
    scpv = sup_comp[0] if isinstance(sup_comp, list) else sup_comp

    metrics = {
        "Station": CodEst,
        "StationName": station_name,
        "Date": f"{yr}-{mn}-{dy} {hr}Z",
        "PlotMode": PLOT_MODE,
        "CAPE_Jkg": fmt_val(cape),
        "CIN_Jkg": fmt_val(cin),
        "LCL_hPa": fmt_val(lcl_p),
        "LFC_hPa": fmt_val(lfc_p),
        "CCL_hPa": fmt_val(ccl_p),
        "EL_hPa": fmt_val(el_p),
        "SBCAPE_Jkg": fmt_val(sbcape),
        "SBCIN_Jkg": fmt_val(sbcin),
        "MLCAPE_Jkg": fmt_val(ml_cape),
        "MLCIN_Jkg": fmt_val(ml_cin),
        "MUCAPE_Jkg": fmt_val(mu_cape),
        "MUCIN_Jkg": fmt_val(mu_cin),
        "TT_Index": fmt_val(tt_idx),
        "K_Index": fmt_val(k_idx),
        "Sfc_1km_Shear_kt": fmt_val(shear_1km),
        "Sfc_3km_Shear_kt": fmt_val(shear_3km),
        "Sfc_6km_Shear_kt": fmt_val(shear_6km),
        "SRH_1km_m2s2": fmt_val(srh_1km),
        "SRH_3km_m2s2": fmt_val(srh_3km),
        "SIGTOR": fmt_val(stpv, 1),
        "SUPCELL": fmt_val(scpv, 1)
    }

    df_metrics = pd.DataFrame([metrics])
    df_metrics.to_csv(csv_output_path, index=False)
        
    print(f"Metrics saved at: {csv_output_path}")
