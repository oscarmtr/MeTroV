"""
sondehub_service.py - Módulo para la integración de datos en tiempo real de SondeHub v2.
Permite listar radiosondas activas en vuelo y reconstruir el perfil vertical
para análisis termodinámico y cinemático con MetPy.
"""

import math
import requests
import numpy as np
import pandas as pd
import metpy.calc as mpcalc
from metpy.units import units
from datetime import datetime, timezone, timedelta

SONDEHUB_API_BASE = "https://api.v2.sondehub.org"
SONDEHUB_HEADERS = {
    "User-Agent": "MeTroV/1.2.1 (+https://github.com/oscarmtr/MeTroV)"
}


def format_utc_24h(time_str, include_seconds=False):
    """Formatea una cadena ISO-8601 a formato 24h 'YYYY-MM-DD HH:MM UTC' (sin 'Z')."""
    if not time_str or not isinstance(time_str, str):
        return "N/A"
    try:
        clean_time = time_str.split(".")[0].rstrip("Z")
        dt = datetime.fromisoformat(clean_time).replace(tzinfo=timezone.utc)
        fmt = "%Y-%m-%d %H:%M:%S UTC" if include_seconds else "%Y-%m-%d %H:%M UTC"
        return dt.strftime(fmt)
    except Exception:
        return str(time_str).replace("T", " ").rstrip("Z") + " UTC"

# Cache en memoria de sitios de lanzamiento conocidos
_SITES_CACHE = None

def get_launch_sites():
    """Obtiene y almacena en caché la lista de sitios de lanzamiento mundiales."""
    global _SITES_CACHE
    if _SITES_CACHE is not None:
        return _SITES_CACHE
    try:
        r = requests.get(f"{SONDEHUB_API_BASE}/sites", headers=SONDEHUB_HEADERS, timeout=15)
        if r.status_code == 200:
            _SITES_CACHE = r.json()
            return _SITES_CACHE
    except Exception as e:
        print(f"Error cargando sitios de lanzamiento: {e}")
    return {}

def extract_country_city(station_name):
    """
    Extracts country and city/station name from SondeHub station name in English.
    Ensures Catalonia, Spain is normalized strictly to Spain.
    """
    if not station_name:
        return 'Other', 'Station'
    import re
    matches = re.findall(r'\(([^)]+)\)', station_name)
    if matches:
        raw_country = matches[-1].strip()
        city = re.sub(r'\s*\([^)]*\)\s*', ' ', station_name).strip()
    else:
        if ',' in station_name:
            parts = station_name.rsplit(',', 1)
            city = parts[0].strip()
            raw_country = parts[1].strip()
        else:
            city = station_name.strip()
            raw_country = 'Other'

    # Normalization (English country names)
    raw_lower = raw_country.lower()
    if 'catalonia' in raw_lower or raw_lower == 'spain' or 'catalonia' in city.lower():
        country = 'Spain'
    elif 'united states' in raw_lower:
        country = 'United States'
    elif raw_lower in ['korea, south', 'south korea']:
        country = 'South Korea'
    elif 'algeria' in raw_lower:
        country = 'Algeria'
    else:
        country = raw_country

    # Ensure Catalonia never lingers in the city label
    city = re.sub(r'(?i)\bCatalonia\b', '', city).strip(' ,')
    if not city:
        city = 'Station'

    return country, city

def haversine_km(lat1, lon1, lat2, lon2):
    """Calcula distancia en km entre dos coordenadas geográficas."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def find_nearest_site(lat, lon, sites_dict, max_dist_km=500):
    """Encuentra el sitio de lanzamiento oficial más cercano a una posición."""
    if not sites_dict or lat is None or lon is None:
        return None, None
    nearest_site = None
    min_dist = float('inf')
    for site_id, site in sites_dict.items():
        pos = site.get('position')
        if pos and len(pos) == 2:
            s_lon, s_lat = pos[0], pos[1]
            dist = haversine_km(lat, lon, s_lat, s_lon)
            if dist < min_dist:
                min_dist = dist
                nearest_site = site
    if min_dist <= max_dist_km:
        return nearest_site, min_dist
    return None, min_dist

def get_active_sondes(duration="12h", only_ascending=False):
    """
    Obtiene las radiosondas activas de SondeHub (por defecto hasta 12 horas, todos los globos).
    Garantiza el cálculo de presión en hPa para cada sonda y ordena alfabéticamente por país de origen.
    """
    try:
        url = f"{SONDEHUB_API_BASE}/sondes?duration={duration}"
        r = requests.get(url, headers=SONDEHUB_HEADERS, timeout=25)
        r.raise_for_status()
        sondes_dict = r.json()
    except Exception as e:
        raise RuntimeError(f"Error consultando SondeHub API: {e}")

    sites = get_launch_sites()
    active_list = []
    now = datetime.now(timezone.utc)

    try:
        max_age_seconds = float(str(duration).lower().rstrip("h").strip()) * 3600.0
    except ValueError:
        max_age_seconds = 12.0 * 3600.0

    for serial, s in sondes_dict.items():
        vel_v = s.get("vel_v")
        temp = s.get("temp")
        pressure = s.get("pressure")
        alt = s.get("alt")
        lat = s.get("lat")
        lon = s.get("lon")
        time_str = s.get("datetime")

        # Requerir coordenadas válidas para representación geográfica
        if lat is None or lon is None:
            continue

        # Filtro opcional de ascenso (por defecto desactivado para ver todos los globos)
        if only_ascending and (vel_v is None or vel_v < 0.5):
            continue

        # Obtener o derivar presión en hPa
        pressure_val = None
        if pressure is not None:
            try:
                pressure_val = float(pressure)
            except (ValueError, TypeError):
                pressure_val = None

        if (pressure_val is None or pressure_val <= 0) and alt is not None:
            try:
                pressure_val = float(mpcalc.height_to_pressure_std(float(alt) * units.m).to(units.hPa).magnitude)
            except Exception:
                pressure_val = None

        if pressure_val is None or pressure_val <= 0:
            pressure_val = 1013.25

        # Calcular antigüedad del paquete y fecha/hora de lanzamiento estimada (formato 24h UTC)
        age_seconds = None
        dt = None
        if time_str:
            try:
                clean_time = time_str.split(".")[0].rstrip("Z")
                dt = datetime.fromisoformat(clean_time).replace(tzinfo=timezone.utc)
                age_seconds = (now - dt).total_seconds()
            except Exception:
                pass

        if age_seconds is not None and age_seconds > max_age_seconds:
            continue

        telemetry_time_utc = dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "N/A"
        frame_val = s.get("frame")
        launch_dt = dt
        if dt is not None:
            est_flight_sec = None
            if vel_v is not None and vel_v > 0.5 and alt is not None and alt > 0:
                est_flight_sec = float(alt) / 5.0
                if frame_val is not None:
                    try:
                        f_sec = float(frame_val)
                        if 0 < f_sec <= 21600:
                            est_flight_sec = min(est_flight_sec, f_sec)
                    except (ValueError, TypeError):
                        pass
            elif frame_val is not None:
                try:
                    f_sec = float(frame_val)
                    if 0 < f_sec <= 21600:
                        est_flight_sec = f_sec
                except (ValueError, TypeError):
                    pass
            if est_flight_sec is not None and est_flight_sec > 0:
                launch_dt = dt - timedelta(seconds=est_flight_sec)
        launch_time_utc = launch_dt.strftime("%Y-%m-%d %H:%M UTC") if launch_dt else "N/A"

        # Identify country and nearest official launch site
        site_info, dist_km = find_nearest_site(lat, lon, sites, max_dist_km=500)
        if site_info:
            raw_station_name = site_info.get('station_name', 'Station')
            country, city = extract_country_city(raw_station_name)
            location_label = f"{city}, {country}"
        else:
            country = "Other"
            city = f"Coord: {lat:.2f}°, {lon:.2f}°"
            location_label = f"{city}, {country}"

        model = s.get("subtype") or s.get("type") or "Radiosonde"
        v_str = f"+{vel_v:.1f}" if (vel_v and vel_v > 0) else f"{vel_v:.1f}" if vel_v is not None else "0.0"

        display_name = f"{location_label} — {serial} ({model}) | {pressure_val:.1f} hPa ({v_str} m/s)"

        active_list.append({
            "serial": serial,
            "display_name": display_name,
            "country": country,
            "city": city,
            "model": model,
            "manufacturer": s.get("manufacturer", "Unknown"),
            "lat": lat,
            "lon": lon,
            "alt_m": alt,
            "pressure_hpa": pressure_val,
            "temp_c": temp,
            "humidity": s.get("humidity"),
            "vel_v_ms": vel_v,
            "vel_h_ms": s.get("vel_h"),
            "heading": s.get("heading"),
            "location_label": location_label,
            "site_distance_km": dist_km,
            "datetime": time_str,
            "telemetry_time_utc": telemetry_time_utc,
            "launch_time_utc": launch_time_utc,
            "age_seconds": age_seconds,
        })

    # Sort alphabetically by country of origin, city, and serial number
    active_list.sort(key=lambda x: (
        "zzz" if x["country"] == "Other" else x["country"].lower(),
        x["city"].lower(),
        x["serial"]
    ))
    return pd.DataFrame(active_list)

def _hampel_filter_td(td_vals, p_vals=None, t_vals=None, half_window=5, n_sigma=3.0, min_diff=2.0, max_dp=20.0):
    """
    Aplica un filtro Hampel (mediana móvil + MAD) al perfil vertical de Td (°C)
    para eliminar picos aislados sin deformar inversiones térmicas ni capas secas reales.
    Mantiene la coherencia física Td <= T cuando se proporciona t_vals.
    """
    arr = np.asarray(td_vals, dtype=float).copy()
    n = len(arr)
    if n < 5:
        return arr

    k = min(half_window, max(2, n // 10))
    p = np.asarray(p_vals, dtype=float) if p_vals is not None else None
    out = arr.copy()

    for i in range(n):
        if np.isnan(arr[i]):
            continue
        lo = max(0, i - k)
        hi = min(n, i + k + 1)
        win = arr[lo:hi]

        # Limitar la ventana a niveles cercanos en presión para no cruzar grandes huecos de telemetría
        if p is not None and not np.isnan(p[i]):
            dp_mask = (~np.isnan(p[lo:hi])) & (np.abs(p[lo:hi] - p[i]) <= max_dp)
            if np.sum(dp_mask) >= 5:
                win = win[dp_mask]

        win = win[~np.isnan(win)]
        if len(win) < 5:
            continue

        med = float(np.median(win))
        mad = float(np.median(np.abs(win - med)))
        # Piso mínimo para evitar falsos positivos en capas con MAD ≈ 0 (p. ej. dentro de nubes)
        threshold = max(min_diff, n_sigma * 1.4826 * mad)
        if abs(arr[i] - med) > threshold:
            out[i] = med

    if t_vals is not None:
        t_arr = np.asarray(t_vals, dtype=float)
        valid_t = ~np.isnan(t_arr)
        out[valid_t] = np.minimum(out[valid_t], t_arr[valid_t])

    return out


def get_live_sounding(serial):
    """
    Descarga la telemetría histórica completa del vuelo actual de una radiosonda de SondeHub.
    Transforma y limpia los datos para ser compatibles con MetPy (p, T, Td, u, v).
    
    Devuelve:
        (p, T, Td, u, v), metadata_dict
    """
    url = f"{SONDEHUB_API_BASE}/sonde/{serial}"
    r = requests.get(url, headers=SONDEHUB_HEADERS, timeout=30)
    r.raise_for_status()
    telemetry = r.json()

    if not telemetry or len(telemetry) == 0:
        raise ValueError(f"No hay telemetría disponible en SondeHub para la sonda {serial}")

    df = pd.DataFrame(telemetry)

    # Verificar presencia de temperatura
    if "temp" not in df.columns or df["temp"].notnull().sum() < 5:
        raise ValueError("La radiosonda no transmite datos válidos de temperatura.")

    # Ordenar por fecha cronológica
    if "datetime" in df.columns:
        df = df.sort_values("datetime").reset_index(drop=True)

    # Identificar si la sonda subió y luego bajó (estallido de globo).
    # Tomamos el segmento de ascenso (hasta la altitud máxima alcanzada),
    # o el perfil completo si la telemetría disponible corresponde a la fase de descenso.
    if "alt" in df.columns and df["alt"].notnull().any():
        max_alt_idx = df["alt"].idxmax()
        if max_alt_idx >= 10:
            df_ascent = df.iloc[:max_alt_idx + 1].copy()
        else:
            df_ascent = df.copy()
    else:
        df_ascent = df.copy()

    # Si la presión no viene directamente de sensor, estimarla mediante la atmósfera estándar
    if "pressure" not in df_ascent.columns or df_ascent["pressure"].notnull().sum() < 5:
        if "alt" in df_ascent.columns:
            alt_m = df_ascent["alt"].fillna(0).to_numpy() * units.m
            calc_p = mpcalc.height_to_pressure_std(alt_m).to(units.hPa).magnitude
            df_ascent["pressure"] = calc_p
        else:
            raise ValueError("La telemetría no contiene ni presión ni altitud suficiente.")

    # Si algunos puntos tienen altitud pero presión nula, interpolar o estimar presión
    missing_p = df_ascent["pressure"].isnull() & df_ascent["alt"].notnull()
    if missing_p.any():
        alt_m = df_ascent.loc[missing_p, "alt"].to_numpy() * units.m
        df_ascent.loc[missing_p, "pressure"] = mpcalc.height_to_pressure_std(alt_m).to(units.hPa).magnitude

    # Filtrar puntos donde tengamos presión y temperatura válidas
    mask = df_ascent["pressure"].notnull() & df_ascent["temp"].notnull()
    valid_df = df_ascent[mask].copy()

    # Eliminar posibles lecturas anómalas
    valid_df = valid_df[(valid_df["temp"] >= -105) & (valid_df["temp"] <= 55)]
    valid_df = valid_df[(valid_df["pressure"] >= 1) & (valid_df["pressure"] <= 1100)]
    valid_df = valid_df.reset_index(drop=True)

    # Descartar en orden cronológico (antes de ordenar por presión) las mediciones iniciales
    # sin calibrar (ej. sonda encendida dentro de la estación en la Antártida antes del lanzamiento)
    # donde se produce un salto térmico > 7.5 °C entre puntos o durante el choque térmico de salida.
    if len(valid_df) > 10:
        t_chrono = valid_df["temp"].to_numpy(dtype=float)
        p_chrono = valid_df["pressure"].to_numpy(dtype=float)
        max_p_init = np.nanmax(p_chrono[:min(len(p_chrono), 500)])
        near_surface_idx = np.where(p_chrono >= (max_p_init - 60.0))[0]
        chrono_start = 0
        if len(near_surface_idx) > 5:
            last_surf_i = int(near_surface_idx[-1])
            for i in range(1, last_surf_i + 1):
                w_start = max(0, i - 15)
                if abs(t_chrono[i] - t_chrono[i - 1]) > 7.5 or abs(t_chrono[i] - t_chrono[w_start]) > 7.5:
                    chrono_start = i + 1
            if chrono_start > 0:
                while chrono_start < len(t_chrono) - 1 and abs(t_chrono[chrono_start] - t_chrono[chrono_start - 1]) > 0.3:
                    chrono_start += 1
                if chrono_start < len(valid_df) - 10:
                    valid_df = valid_df.iloc[chrono_start:].reset_index(drop=True)

    if len(valid_df) < 5:
        raise ValueError(f"Datos meteorológicos insuficientes tras filtrar anomalías ({len(valid_df)} niveles)")

    # Calcular punto de rocío (Td) asegurando unidades degree_Celsius (no delta_degree_Celsius)
    temp_c_arr = valid_df["temp"].to_numpy(dtype=float)
    temp_vals = temp_c_arr * units.degC
    rh_series = (
        pd.to_numeric(valid_df["humidity"], errors="coerce")
        if "humidity" in valid_df.columns
        else pd.Series(dtype=float)
    )
    rh_series = rh_series.where((rh_series >= 0.0) & (rh_series <= 105.0))
    if not rh_series.empty and rh_series.notnull().any():
        rh_interp = rh_series.interpolate(method="linear", limit_direction="both")
        rh_arr = np.clip(rh_interp.to_numpy(dtype=float), 1.0, 100.0)
        rh_vals = rh_arr * units.percent
        try:
            td_calc = mpcalc.dewpoint_from_relative_humidity(temp_vals, rh_vals).to(units.degC).magnitude
            fallback_td = temp_c_arr - (100.0 - rh_arr) / 5.0
            td_c_arr = np.where(np.isnan(td_calc), fallback_td, td_calc)
            td_vals = td_c_arr * units.degC
        except Exception:
            td_vals = (temp_c_arr - (100.0 - rh_arr) / 5.0) * units.degC
    else:
        td_vals = (temp_c_arr - 10.0) * units.degC

    # Viento:
    # vel_h en m/s, heading en grados de avance del globo.
    # En meteorología, dirección del viento = de dónde viene -> (heading + 180) % 360
    if "vel_h" in valid_df.columns and "heading" in valid_df.columns:
        wspd_vals = valid_df["vel_h"].fillna(0).to_numpy() * units('m/s')
        wdir_vals = ((valid_df["heading"].fillna(0).to_numpy() + 180.0) % 360.0) * units.degrees
        u_vals, v_vals = mpcalc.wind_components(wspd_vals, wdir_vals)
    else:
        u_vals = np.zeros(len(valid_df)) * units('m/s')
        v_vals = np.zeros(len(valid_df)) * units('m/s')

    p_vals = valid_df["pressure"].to_numpy() * units.hPa

    # Ordenar por presión decreciente (de superficie a tropopausa/estratosfera)
    idx = np.argsort(p_vals.magnitude)[::-1]
    p_clean = p_vals[idx]
    T_clean = temp_vals[idx]
    Td_clean = td_vals[idx]
    u_clean = u_vals[idx]
    v_clean = v_vals[idx]

    # Eliminar presiones duplicadas idénticas para garantizar monotonicidad
    _, unique_indices = np.unique(p_clean.magnitude, return_index=True)
    unique_indices = np.sort(unique_indices)

    p_uniq = p_clean[unique_indices]
    T_uniq = T_clean[unique_indices]
    Td_uniq = Td_clean[unique_indices]
    u_uniq = u_clean[unique_indices]
    v_uniq = v_clean[unique_indices]

    # Filtrar saltos térmicos > 7.5 °C entre un punto y el anterior:
    # 1) Descartar tramo inicial sin calibrar (ej. interior de estación en Antártida antes de soltar el globo)
    #    donde se producen saltos > 7.5 °C en los primeros 100 hPa desde superficie.
    if len(T_uniq) > 2:
        p_m = p_uniq.magnitude
        t_m = T_uniq.magnitude
        t_diffs = np.abs(np.diff(t_m))
        p_diffs = np.abs(np.diff(p_m))
        in_surface_layer = p_m[:-1] >= (p_m[0] - 100.0)
        init_jumps = np.where((t_diffs > 7.5) & (p_diffs < 30.0) & in_surface_layer)[0]
        if len(init_jumps) > 0:
            start_idx = int(init_jumps[-1]) + 1
            if start_idx < len(p_uniq) - 5:
                p_uniq = p_uniq[start_idx:]
                T_uniq = T_uniq[start_idx:]
                Td_uniq = Td_uniq[start_idx:]
                u_uniq = u_uniq[start_idx:]
                v_uniq = v_uniq[start_idx:]

    # 2) Filtro secuencial punto a punto: no permitir saltos > 7.5 °C respecto al punto válido anterior
    if len(T_uniq) > 2:
        p_m = p_uniq.magnitude
        t_m = T_uniq.magnitude
        keep_idx = [0]
        for i in range(1, len(t_m)):
            dt_jump = abs(t_m[i] - t_m[keep_idx[-1]])
            dp_step = abs(p_m[i] - p_m[keep_idx[-1]])
            if dt_jump <= 7.5 or dp_step > 30.0:
                keep_idx.append(i)
        if len(keep_idx) >= 5:
            p_uniq = p_uniq[keep_idx]
            T_uniq = T_uniq[keep_idx]
            Td_uniq = Td_uniq[keep_idx]
            u_uniq = u_uniq[keep_idx]
            v_uniq = v_uniq[keep_idx]

    # 3) Filtro Hampel sobre Td (°C) para eliminar picos aislados y oscilaciones puntuales de humedad
    td_filtered = _hampel_filter_td(
        Td_uniq.to(units.degC).magnitude,
        p_vals=p_uniq.to(units.hPa).magnitude,
        t_vals=T_uniq.to(units.degC).magnitude,
    )
    Td_uniq = td_filtered * units.degC

    # Metadatos actuales del vuelo
    latest = df.iloc[-1]
    first = df.iloc[0]
    sites = get_launch_sites()
    nearest_site, site_dist = find_nearest_site(first.get("lat"), first.get("lon"), sites)

    # Fecha/hora de lanzamiento y del último paquete en formato 24h UTC (sin Z)
    dt_latest = latest.get("datetime", "")
    dt_first = first.get("datetime", "")
    try:
        dt_obj = datetime.fromisoformat(dt_latest.split(".")[0].rstrip("Z"))
        yr, mn, dy = str(dt_obj.year), f"{dt_obj.month:02}", f"{dt_obj.day:02}"
        hr = f"{dt_obj.hour:02}:{dt_obj.minute:02} UTC"
    except Exception:
        now_dt = datetime.now(timezone.utc)
        yr, mn, dy = str(now_dt.year), f"{now_dt.month:02}", f"{now_dt.day:02}"
        hr = f"{now_dt.hour:02}:{now_dt.minute:02} UTC"

    metadata = {
        "serial": serial,
        "type": latest.get("subtype") or latest.get("type") or "Radiosonde",
        "manufacturer": latest.get("manufacturer", ""),
        "launch_time": format_utc_24h(dt_first, include_seconds=False),
        "latest_time": format_utc_24h(dt_latest, include_seconds=True),
        "yr": yr, "mn": mn, "dy": dy, "hr": hr,
        "current_alt_m": latest.get("alt"),
        "max_alt_m": df["alt"].max() if "alt" in df.columns else None,
        "current_pressure_hpa": latest.get("pressure"),
        "current_temp_c": latest.get("temp"),
        "current_vel_v_ms": latest.get("vel_v"),
        "current_vel_h_ms": latest.get("vel_h"),
        "current_lat": latest.get("lat"),
        "current_lon": latest.get("lon"),
        "launch_lat": first.get("lat"),
        "launch_lon": first.get("lon"),
        "nearest_site": nearest_site,
        "site_distance_km": site_dist,
        "num_points": len(p_uniq),
        "is_burst": (df["alt"].idxmax() < len(df) - 1) if "alt" in df.columns else False,
        "source_url": f"https://sondehub.org/#!mt=Mapnik&mz=9&qm=3h&q={serial}"
    }

    return (p_uniq, T_uniq, Td_uniq, u_uniq, v_uniq), metadata

def get_sonde_trajectory(serial):
    """
    Obtiene la serie de coordenadas (lat, lon, alt, pressure_hpa, datetime) para dibujar la trayectoria
    completa del vuelo de la radiosonda sobre el mapa con escala de presión.
    """
    try:
        url = f"{SONDEHUB_API_BASE}/sonde/{serial}"
        r = requests.get(url, headers=SONDEHUB_HEADERS, timeout=30)
        if r.status_code == 200:
            tel = r.json()
            if tel:
                df = pd.DataFrame(tel)
                if "lat" in df.columns and "lon" in df.columns:
                    mask = df["lat"].notnull() & df["lon"].notnull()
                    df_clean = df[mask].copy()
                    if "datetime" in df_clean.columns:
                        df_clean = df_clean.sort_values("datetime").reset_index(drop=True)
                    
                    # Calcular presión en hPa para cada punto
                    if "pressure" in df_clean.columns:
                        df_clean["pressure_hpa"] = pd.to_numeric(df_clean["pressure"], errors="coerce")
                    else:
                        df_clean["pressure_hpa"] = np.nan

                    if "alt" in df_clean.columns:
                        alt_num = pd.to_numeric(df_clean["alt"], errors="coerce")
                        null_p = df_clean["pressure_hpa"].isnull() & alt_num.notnull()
                        if null_p.any():
                            alts = alt_num[null_p].values
                            # Fórmula barométrica estándar internacional
                            p_calc = 1013.25 * np.maximum(0.0001, (1.0 - 0.0065 * alts / 288.15)) ** 5.255
                            df_clean.loc[null_p, "pressure_hpa"] = p_calc

                    df_clean["pressure_hpa"] = df_clean["pressure_hpa"].fillna(1013.25)

                    if "temp" not in df_clean.columns:
                        df_clean["temp"] = np.nan
                    if "alt" not in df_clean.columns:
                        df_clean["alt"] = 0.0
                    if "datetime" not in df_clean.columns:
                        df_clean["datetime"] = ""
                    else:
                        df_clean["datetime"] = df_clean["datetime"].apply(lambda x: format_utc_24h(x, include_seconds=True))

                    cols = ["lat", "lon", "alt", "pressure_hpa", "datetime", "temp", "vel_v", "vel_h"]
                    available_cols = [c for c in cols if c in df_clean.columns]
                    return df_clean[available_cols]
    except Exception as e:
        print(f"Error obteniendo trayectoria de {serial}: {e}")
    return pd.DataFrame()
