import pandas as pd
import pathlib
import requests
import time
import os
import os

# FIX: Usar ruta absoluta relativa al script y nombre de archivo actualizado
script_dir = pathlib.Path(__file__).parent.absolute()
STATION_FILE = script_dir.parent / "data" / "igra_stations_all.csv"

def prettify_name(raw):
    raw = raw.strip()
    city = raw.split("/")[0].title()

    keywords = [
        "airport", "air", "ap", "afb",
        "base", "naval", "intl", "international"
    ]

    if any(k in raw.lower() for k in keywords):
        display = f"{city} ({raw.title()})"
    else:
        display = city

    return display, city

def update_station_list():
    """
    Checks if station list is older than 24h. If so, attempts to download and update it.
    Returns True if updated, False otherwise.
    """
    # Check if file exists and age
    if STATION_FILE.exists():
        file_age = time.time() - STATION_FILE.stat().st_mtime
        if file_age < 86400: # 24 hours
            return False # Fresh enough
    
    # Needs update
    print("Updating station list...")
    try:
        URL = "https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt"
        response = requests.get(URL, timeout=30)
        response.raise_for_status()
        txt = response.text.splitlines()

        records = []
        for line in txt:
             # Aumentar el límite de longitud para asegurar que existe el año final
            if len(line) < 81:
                continue

            code = line[0:11].strip()
            raw_name = line[38:68].strip()
            
            try:
                last_year = int(line[77:81])
            except ValueError:
                continue

            display, city = prettify_name(raw_name)

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
            
            # Update global variable if it exists/reload it
            global stations
            stations = df
            return True
            
    except Exception as e:
        print(f"Failed to update station list: {e}")
        return False
    
    return False

# Load initially (might be stale if update hasn't run yet, but fine for imports)
if STATION_FILE.exists():
    stations = pd.read_csv(STATION_FILE)
else:
    # Create empty DF or handle error, though update sshould fix this
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
        print("Varias estaciones encontradas:")
        print(matches[["display_name", "code"]])
        raise ValueError("Búsqueda ambigua")

    row = matches.iloc[0]
    return row["code"], row["display_name"]
