import requests
import pandas as pd
import pathlib

URL = "https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt"
txt = requests.get(URL, timeout=30).text.splitlines()

records = []

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

for line in txt:
    # Aumentar el límite de longitud para asegurar que existe el año final
    if len(line) < 81:
        continue

    code = line[0:11].strip()
    raw_name = line[38:68].strip()
    
    # CORREGIDO: Índices ajustados a 77:81 para el año final
    try:
        last_year = int(line[77:81])
    except ValueError:
        continue

    # Eliminado filtro de años para incluir todas las estaciones
    # if last_year < 2020:
    #     continue
    
    # ... resto del código ...

    display, city = prettify_name(raw_name)

    records.append({
        "code": code,
        "display_name": display,
        "city": city,
        "raw_name": raw_name
    })

df = pd.DataFrame(records)

# Construir ruta absoluta relativa a la ubicación del script
script_dir = pathlib.Path(__file__).parent.absolute()
output_path = script_dir.parent / "data" / "igra_stations_all.csv"

# Asegurar que el directorio existe
output_path.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(output_path, index=False)

print(f"Estaciones guardadas: {len(df)}")

