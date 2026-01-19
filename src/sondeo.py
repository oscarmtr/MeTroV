# =========================
# sondeo.py
# =========================

import numpy as np
import matplotlib.pyplot as plt
import requests
import zipfile
import pandas as pd
from io import StringIO
import io
import pathlib

import metpy.calc as mpcalc
from metpy.plots import SkewT
from metpy.units import units

from stations import find_station  # tu CSV de estaciones
# =====================================
# LECTURA SONDEO IGRA
# =====================================

def lecturaSondeoIGRA(CodEst, yr, mn, dy, hr):
    """
    Descarga un sondeo IGRA y devuelve p, T, Td, u, v como arrays MetPy
    """

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
            # IGRA Format v2:
            # PRESS(9-15), TEMP(22-27), DEWPOINT DEP(34-39), WDIR(40-45), WSPD(46-51)
            pres = int(line[9:15])
            temp = int(line[22:27])
            dtd  = int(line[34:39])
            wdir = int(line[40:45])
            wspd = int(line[46:51])
        except ValueError:
            n_read += 1
            continue

        # BasicQC: Pressure valid, Temp valid
        if pres < 0 or temp < -900:
            n_read += 1
            continue

        # Process standard vars
        pres_val = pres / 100.0
        temp_val = temp / 10.0
        
        # Td
        if dtd < -900:
            td_val = np.nan
        else:
            td_val = (temp - dtd) / 10.0

        # Wind
        if wdir < -900 or wspd < -900:
            wdir_val = np.nan
            wspd_val = np.nan
        else:
            wdir_val = float(wdir)
            wspd_val = float(wspd) / 10.0
            # IGRA readme: WSPD is output in tenths of meters per second. 
            # Example: 123 = 12.3 m/s. 
            # Let's verify standard IGRA usage. 
            # "WSPD is the wind speed in meters per second" - in some versions.
            # "WSPD (46-51) ... in tenths of meters per second" (Readme v2)
            # Indeed, IGRA v2 is tenths.
            
        p_list.append(pres_val)
        T_list.append(temp_val)
        Td_list.append(td_val)
        wdir_list.append(wdir_val)
        wspd_list.append(wspd_val)

        n_read += 1

    if len(p_list) < 10:
        raise ValueError("IGRA sounding not available")

    # Create arrays
    p = np.array(p_list) * units.hPa
    T = np.array(T_list) * units.degC
    Td = np.array(Td_list) * units.degC
    
    # Calculate u, v
    wdir = np.array(wdir_list) * units.degrees
    wspd = np.array(wspd_list) * units('m/s') # IGRA is m/s
    
    u, v = mpcalc.wind_components(wspd, wdir)

    # Sort by pressure descending
    idx = np.argsort(p.magnitude)[::-1]
    
    return p[idx], T[idx], Td[idx], u[idx], v[idx]


# =====================================
# LECTURA SONDEO UWYO
# =====================================
def lecturaSondeoUWyo(CodEst_WMO, yr, mn, dy, hr):
    """
    Descarga un sondeo de la Universidad de Wyoming
    CodEst_WMO: últimos 5 dígitos del código WMO
    """

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

            # Leer CSV con pandas
            df = pd.read_csv(StringIO(csv_text))

            # Verificar si el dataframe está vacío o tiene error de "HTML" disfrazado
            if df.empty or "pressure" not in str(df.columns).lower():
                 # Sometimes returns html with error
                 raise ValueError(f"Invalid or empty response with src={src}")

            # Columnas típicas del CSV de UWyo
            # Columns: pressure, height, temperature, dew point, direction, speed
            # Map columns often found: 'pressure', 'temperature', 'dewpoint', 'drct', 'sknt'
            # UWyo CSV usually has headers: pressure, height, temp, dwpt, relh, mixr, drct, sknt, thta, thte, thtv
            
            # Let's map loosely
            # df columns in uwyo often: ['pressure', 'height', 'temperature', 'dew point', 'humidity', 'mixing ratio', 'direction', 'speed', ...]
            # Wait, 'drct' and 'sknt' are typical in fixed width, CSV has full names? 
            # Checking sondeo.py original code... it accessed 'pressure_hPa', 'temperature_C', 'dew point temperature_C' ??
            # Wait, the previous code was:
            # p  = pd.to_numeric(df['pressure_hPa'], errors='coerce')
            # The previous code implies the CSV has specific headers.
            # UWYO CSV output headers: "pressure_[hPa]", "height_[m]", "temperature_[C]", "dew_point_[C]", "relative_humidity_[%]", "mixing_ratio_[g/kg]", "wind_direction_[deg]", "wind_speed_[kn]"
            # Actually standard UWyo CSV often uses: 'pressure', 'temperature', 'dewpoint', 'drct', 'speed' or unit-based names.
            # Let's try to be robust.
            
            # Based on previous code: df['pressure_hPa']
            # I will assume standard UWyo CSV format.
            # Helper to find column from candidates
            def get_col(candidates):
                for c in candidates:
                    if c in df.columns:
                        return df[c], c
                raise KeyError(f"Ninguna de las columnas {candidates} encontrada")

            try:
                # Pressure
                p_col, _ = get_col(['pressure', 'pressure_hPa', 'pres'])
                p = pd.to_numeric(p_col, errors='coerce')
                
                # Temperature
                T_col, _ = get_col(['temperature', 'temperature_C', 'temp'])
                T = pd.to_numeric(T_col, errors='coerce')

                # Dew Point
                Td_col, _ = get_col(['dew point', 'dew point temperature_C', 'dwpt'])
                Td = pd.to_numeric(Td_col, errors='coerce')

                # Wind Direction
                wdir_col, _ = get_col(['direction', 'wind direction_degree', 'drct'])
                wdir = pd.to_numeric(wdir_col, errors='coerce')

                # Wind Speed
                # Need to know the unit based on column name
                wspd_raw_col, wspd_col_name = get_col(['speed', 'wind speed_m/s', 'sknt', 'wind speed_kn'])
                wspd = pd.to_numeric(wspd_raw_col, errors='coerce')
                
                # Determine wind units
                if 'm/s' in wspd_col_name:
                    wind_units = units('m/s')
                elif 'kn' in wspd_col_name or 'sknt' in wspd_col_name:
                    wind_units = units.knots
                else:
                    # Default assumption if unknown name (e.g. 'speed') - usually UWYO web is knots, but 'wind speed_m/s' is explicit.
                    # If just 'speed', older parsers assumed knots, but let's be careful.
                    # Looking at the user error, 'wind speed_m/s' is explicitly present.
                    wind_units = units.knots # Fallback

            except KeyError as e:
                 cols_found = df.columns.tolist()
                 snippet = csv_text[:200].replace('\n', ' ')
                 raise ValueError(f"Formato UWyo inesperado o columna faltante ({e}). Columnas encontradas: {cols_found}. Inicio contenido: {snippet}")

            # Filtrar valores inválidos
            mask = (~p.isna()) & (~T.isna()) # Keep basic valid
            
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
            # Si falla, probamos el siguiente source
            continue

    # If we exit the loop, all failed
    raise ValueError(f"Could not download UWyo sounding with any source. Last error: {last_exception}")

# =====================================
# GESTOR DE FUENTES
# =====================================
def get_sounding(CodEst, yr, mn, dy, hr, source_mode="IGRA"):
    """
    source_mode:
      - 'IGRA'  → solo IGRA
      - 'UWYO'  → solo UWyo
      - 'AUTO'  → intenta IGRA, si falla → UWyo
    """
    source_mode = source_mode.upper()
    if source_mode not in ("IGRA", "UWYO", "AUTO"):
        raise ValueError("source_mode debe ser IGRA, UWYO o AUTO")

    if source_mode == "IGRA":
        return lecturaSondeoIGRA(CodEst, yr, mn, dy, hr), "IGRA"

    if source_mode == "UWYO":
        wmo = CodEst[-5:]
        data_tuple = lecturaSondeoUWyo(wmo, yr, mn, dy, hr)
        # data_tuple es (p, T, Td, u, v, precise_source)
        return data_tuple[:5], data_tuple[5]

    # AUTO
    try:
        return lecturaSondeoIGRA(CodEst, yr, mn, dy, hr), "IGRA"
    except Exception:
        wmo = CodEst[-5:]
        data_tuple = lecturaSondeoUWyo(wmo, yr, mn, dy, hr)
        return data_tuple[:5], data_tuple[5]

# =====================================
# CONFIGURACIÓN DE USUARIO
# =====================================
if __name__ == "__main__":
    city = "Huelva"
    source_mode = "AUTO"   # "IGRA" | "UWYO" | "AUTO"
    yr, mn, dy, hr = "2026", "01", "14", "00"

    CodEst, station_name = find_station(city)

# Descargar sondeo según fuente elegida
    # Download sounding based on chosen source
    (p, T, Td, u, v), source_used = get_sounding(CodEst, yr, mn, dy, hr, source_mode)
    print(f"Sounding retrieved from: {source_used}")

# =====================================
# METPY
# =====================================
    # =====================================
    # METPY
    # =====================================
    lcl_p, lcl_T = mpcalc.lcl(p[0], T[0], Td[0])
    parcel_prof = mpcalc.parcel_profile(p, T[0], Td[0])
    lfc_p, _ = mpcalc.lfc(p, T, Td, parcel_prof, which='bottom')
    el_p,  _ = mpcalc.el (p, T, Td, parcel_prof, which='bottom')
    cape, cin = mpcalc.cape_cin(p, T, Td, parcel_prof)

    # =====================================
    # PRINT RESULTS
    # =====================================
    print("\n" + "="*40)
    print(f"THERMODYNAMIC INDICES ({station_name})")
    print("="*40)
    print(f"CAPE: {cape.magnitude:.2f} J/kg")
    print(f"CIN:  {cin.magnitude:.2f} J/kg")
    
    print("\n" + "="*40)
    print("CHARACTERISTIC LEVELS")
    print("="*40)
    print(f"LCL: {lcl_p.magnitude:.1f} hPa")
    print(f"LFC: {lfc_p.magnitude:.1f} hPa")
    print(f"EL:  {el_p.magnitude:.1f}  hPa")
    print("="*40 + "\n")

    # =====================================
    # SKEW-T
    # =====================================
    fig = plt.figure(figsize=(9, 15))
    skew = SkewT(fig, rotation=45)
    
    # Plot wind barbs
    # Skip every n points to de-clutter
    interval = np.arange(0, len(p), 5) 
    skew.plot_barbs(p[interval], u[interval], v[interval])

    skew.plot(p, T, 'r', label='T')
    skew.plot(p, Td, 'g', label='Td')
    skew.plot(p, parcel_prof, 'k--', label='Parcel')

    if cape > 0:
        skew.shade_cape(p, T, parcel_prof)
    
    # Restrict CIN to area below LFC (avoid painting stability aloft)
    if not np.isnan(lfc_p):
        mask_cin = p >= lfc_p
        skew.shade_cin(p[mask_cin], T[mask_cin], parcel_prof[mask_cin])

    skew.ax.set_ylim(1050, 75)
    skew.ax.set_xlim(-40, 40)

    skew.plot_dry_adiabats()
    skew.plot_moist_adiabats()
    skew.plot_mixing_lines()

    # Líneas de referencia
    skew.ax.axhline(lcl_p.magnitude, linestyle='--', color='black')
    skew.ax.axhline(lfc_p.magnitude, linestyle='--', color='black')
    skew.ax.axhline(el_p.magnitude,  linestyle='--', color='black')
    skew.ax.text(-38, lcl_p.magnitude, 'LCL')
    skew.ax.text(-38, lfc_p.magnitude, 'LFC')
    skew.ax.text(-38, el_p.magnitude,  'EL')

    # Calcular ruta de salida absoluta
    script_dir = pathlib.Path(__file__).parent.absolute()
    output_path = script_dir.parent / "outputs" / "skewt_web.png"
    
    # Asegurar que el directorio existe
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.title(f"{station_name}  {yr}-{mn}-{dy} {hr}Z")
    plt.savefig(output_path, dpi=1200)
    plt.show()
