import pandas as pd
import pathlib
import requests
import time
import os
import os

# FIX: Usar ruta absoluta relativa al script y nombre de archivo actualizado
script_dir = pathlib.Path(__file__).parent.absolute()
STATION_FILE = script_dir.parent / "data" / "igra_stations_all.csv"
COUNTRY_FILE = script_dir.parent / "data" / "igra_countries.csv"

def get_country_map():
    """
    Returns a dictionary mapping 2-letter country code -> Country Name
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
    # Usually format is "CITY/AIRPORT_NAME" or just "CITY"
    parts = raw.split("/")
    city = parts[0].strip().title()
    
    extra = ""
    if len(parts) > 1:
        extra = parts[1].strip().title()

    # Keywords to detect if it's an airport/base
    keywords = [
        "airport", "air", "ap", "afb",
        "base", "naval", "intl", "international"
    ]

    is_airport = False
    if extra and any(k in extra.lower() for k in keywords):
        is_airport = True
    elif any(k in city.lower() for k in keywords):
        is_airport = True
        
    # Construct display name
    # Case 1: Airport (or base)
    if is_airport:
        # If extra info exists, use it as main name if it looks like an airport name
        # e.g. "MADRID/BARAJAS" -> "Barajas (Madrid, Spain)" ??
        # Or "ABU DHABI/INTL" -> "Abu Dhabi Intl (Abu Dhabi, UAE)"
        
        main_name = extra if extra else city
        
        # Avoid redundancy: if main name contains city, don't repeat city inside parens
        if city.lower() in main_name.lower():
            # e.g. "Abu Dhabi Intl" contains "Abu Dhabi"
            # Result: "Abu Dhabi Intl (Spain)"
             display = f"{main_name} ({country_name})"
        else:
            # e.g. "Barajas" (Madrid)
            display = f"{main_name} ({city}, {country_name})"
            
    else:
        # Case 2: Just a city/station
        # "HUELVA" -> "Huelva, Spain"
        if extra:
             # e.g. "XXX/YYY" where YYY is not clearly an airport
             display = f"{city}/{extra}, {country_name}"
        else:
             display = f"{city}, {country_name}"

    # Cleanup double spaces or trailing commas
    display = display.replace(", )", ")").replace("()", "").strip()
    if display.endswith(", "): display = display[:-2]
    
    return display, city

def update_station_list(force=False):
    """
    Checks if station list is older than 24h. If so, attempts to download and update it.
    Returns True if updated, False otherwise.
    """
    # Check if files exist and age
    if not force and STATION_FILE.exists() and COUNTRY_FILE.exists():
        file_age = time.time() - STATION_FILE.stat().st_mtime
        if file_age < 86400: # 24 hours
            return False # Fresh enough
    
    # Needs update
    print("Updating station and country lists...")
    try:
        # 1. Update Country List
        URL_CTRY = "https://www.ncei.noaa.gov/pub/data/igra/igra2-country-list.txt"
        resp_c = requests.get(URL_CTRY, timeout=30)
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

        # 2. Update Station List
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
