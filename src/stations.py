import pandas as pd
import pathlib
import requests
import time
import os
import os

# FIX: Utilizar ruta absoluta relativa al script y nombre de archivo actualizado
script_dir = pathlib.Path(__file__).parent.absolute()
STATION_FILE = script_dir.parent / "data" / "igra_stations_all.csv"
COUNTRY_FILE = script_dir.parent / "data" / "igra_countries.csv"

def get_country_map():
    """
    Devuelve un diccionario que mapea el código de país de 2 letras -> Nombre del País
    """
    if COUNTRY_FILE.exists():
        try:
            df = pd.read_csv(COUNTRY_FILE)
            return dict(zip(df['code'], df['name']))
        except:
            return {}
    return {}

def prettify_name(raw, country_name=""):
    raw = raw.strip()
    # Petición del usuario: "estación, país de la estación" independientemente del tipo.
    # Se utiliza el nombre original en formato título.
    
    name_display = raw.title()
    
    # Construir nombre para mostrar
    # "HUELVA" -> "Huelva, Spain"
    # "MADRID/BARAJAS" -> "Madrid/Barajas, Spain"
    
    if country_name:
        display = f"{name_display}, {country_name}"
    else:
        display = name_display

    return display, name_display.split("/")[0]

def update_station_list(force=False):
    """
    Comprueba si la lista de estaciones tiene más de 24h. Si es así, intenta descargarla y actualizarla.
    Devuelve True si se ha actualizado, False en caso contrario.
    """
    # Comprobar si los archivos existen y su antigüedad
    if not force and STATION_FILE.exists() and COUNTRY_FILE.exists():
        file_age = time.time() - STATION_FILE.stat().st_mtime
        if file_age < 86400: # 24 horas
            return False # Suficientemente reciente
    
    # Requiere actualización
    print("Actualizando listas de estaciones y países...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        URL_CTRY = "https://www.ncei.noaa.gov/pub/data/igra/igra2-country-list.txt"
        resp_c = requests.get(URL_CTRY, headers=headers, timeout=3)
        resp_c.raise_for_status()
        
        c_records = []
        for line in resp_c.text.splitlines():
            if len(line) < 3: continue
            code = line[0:2].strip()
            name = line[3:].strip()
            c_records.append({"code": code, "name": name})
            
        df_c = pd.DataFrame(c_records)
        COUNTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        df_c.to_csv(COUNTRY_FILE, index=False)
        
        country_map = dict(zip(df_c['code'], df_c['name']))

        URL = "https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt"
        response = requests.get(URL, headers=headers, timeout=3)
        response.raise_for_status()
        txt = response.text.splitlines()

        records = []
        for line in txt:
             # Incrementar el límite de longitud para asegurar que el año final existe
            if len(line) < 81:
                continue

            code = line[0:11].strip()
            country_code = code[0:2]
            country_name = country_map.get(country_code, country_code)
            
            raw_name = line[38:68].strip()
            
            try:
                last_year = int(line[77:81])
            except ValueError:
                continue

            display, city = prettify_name(raw_name, country_name)

            records.append({
                "code": code,
                "display_name": display,
                "city": city,
                "raw_name": raw_name
            })
        
        if records:
            df = pd.DataFrame(records)
            # Asegurar que el directorio existe
            STATION_FILE.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(STATION_FILE, index=False)
            
            # Actualizar la variable global si existe/recargarla
            global stations
            stations = df
            return True
            
    except Exception as e:
        print(f"Error al actualizar la lista de estaciones: {e}")
        return False
    
    return False

# Carga inicial (puede estar obsoleta si la actualización no se ha ejecutado, pero es suficiente para importaciones)
if STATION_FILE.exists():
    stations = pd.read_csv(STATION_FILE)
else:
    # Crear un DataFrame vacío o manejar el error, aunque la actualización debería solucionar esto
    stations = pd.DataFrame(columns=["code", "display_name", "city", "raw_name"])

def find_station(city_query):
    """
    Devuelve (code, display_name)
    """
    mask = stations["city"].str.contains(city_query, case=False, na=False)
    matches = stations[mask]

    if len(matches) == 0:
        raise ValueError("No se encontró ninguna estación")

    if len(matches) > 1:
        print("Múltiples estaciones encontradas:")
        print(matches[["display_name", "code"]])
        raise ValueError("Búsqueda ambigua")

    row = matches.iloc[0]
    return row["code"], row["display_name"]
