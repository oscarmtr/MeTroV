from sondeo import lecturaSondeoIGRA, lecturaSondeoUWyo

def get_sounding(CodEst, yr, mn, dy, hr, source_mode="IGRA"):
    """
    source_mode:
      - 'IGRA'  → solo IGRA
      - 'UWYO'  → solo UWyo
      - 'AUTO'  → IGRA → UWyo
    """

    source_mode = source_mode.upper()

    if source_mode not in ("IGRA", "UWYO", "AUTO"):
        raise ValueError("source_mode debe ser IGRA, UWYO o AUTO")

    # --- SOLO IGRA ---
    if source_mode == "IGRA":
        return lecturaSondeoIGRA(CodEst, yr, mn, dy, hr), "IGRA"

    # --- SOLO UWYO ---
    if source_mode == "UWYO":
        wmo = CodEst[-5:]          # UWyo usa WMO de 5 cifras
        return lecturaSondeoUWyo(wmo, yr, mn, dy, hr), "UWYO"

    # --- AUTOMÁTICO ---
    try:
        return lecturaSondeoIGRA(CodEst, yr, mn, dy, hr), "IGRA"
    except Exception:
        wmo = CodEst[-5:]
        return lecturaSondeoUWyo(wmo, yr, mn, dy, hr), "UWYO"

