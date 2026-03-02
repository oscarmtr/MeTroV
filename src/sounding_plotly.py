
import numpy as np
import plotly.graph_objects as go
import pathlib
import sys
import os
from metpy.units import units

# Add current directory to path to allow imports if running from src or root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sounding import get_sounding
from stations import find_station

def create_skewt_plotly(p, T, Td, station_name, date_str):
    """
    Crea un diagrama de Skew-T simple usando Plotly.
    Los datos de temperatura se sesgan manualmente para que encajen en el área de trazado rectangular de Plotly.
    
    Transformation:
    x = T + skew_factor * ln(P_ref / P)
    y = P (log axis)
    """
    
    # Ensure magnitudes
    p_vals = p.m_as(units.hPa)
    T_vals = T.m_as(units.degC)
    Td_vals = Td.m_as(units.degC)
    
    # Skew factor (tune for appearance, usually around 30-45 deg equivalent)
    # x = T + skew * log(1000/P)
    skew = 30  
    
    # Helper to skew X coordinates
    def skew_x(temp, pres):
        return temp + skew * np.log(1000.0 / pres)

    T_skewed = skew_x(T_vals, p_vals)
    Td_skewed = skew_x(Td_vals, p_vals)
    
    # Create traces
    trace_T = go.Scatter(
        x=T_skewed,
        y=p_vals,
        mode='lines+markers',
        name='Temperature',
        line=dict(color='red', width=2),
        hovertemplate='P: %{y:.1f} hPa<br>T_skewed: %{x:.1f}<br>T_actual: %{text:.1f} °C',
        text=T_vals # Pass actual T for hover
    )
    
    trace_Td = go.Scatter(
        x=Td_skewed,
        y=p_vals,
        mode='lines',
        name='Dew Point',
        line=dict(color='green', width=2),
        hovertemplate='P: %{y:.1f} hPa<br>Td_actual: %{text:.1f} °C',
        text=Td_vals
    )
    
    # Isobaras (líneas horizontales) - La escala logarítmica lo maneja naturalmente en Y, 
    # pero se pueden añadir líneas de cuadrícula
    
    # Isotermas (líneas diagonales en este sistema sesgado)
    # T = constante -> x = C + skew * log(1000/P)
    # Se pueden trazar algunas isotermas de referencia
    isotherm_traces = []
    ref_temps = range(-100, 50, 10)
    ref_pressures = np.linspace(1050, 1, 100)
    
    for temp in ref_temps:
        x_iso = skew_x(np.full_like(ref_pressures, temp), ref_pressures)
        isotherm_traces.append(go.Scatter(
            x=x_iso,
            y=ref_pressures,
            mode='lines',
            line=dict(color='lightgrey', width=0.5, dash='dot'),
            showlegend=False,
            hoverinfo='skip'
        ))

    layout = go.Layout(
        title=f"Skew-T (Plotly) - {station_name} - {date_str}",
        xaxis=dict(
            title="Temperature (ºC)",
            showgrid=True,
            zeroline=False
        ),
        yaxis=dict(
            title="Pressure (hPa)",
            type="log",
            range=[np.log10(1050), np.log10(1)], # ¿Rango logarítmico invertido visualmente? No, dirección del eje logarítmico de Plotly.
            # Normalmente el Skew-T tiene la presión alta en la parte inferior.
            # Eje logarítmico de Plotly: el estándar es creciente hacia arriba. Se requiere decreciente hacia arriba (1000 -> 100).
            # Se puede utilizar 'autorange="reversed"' o un rango explícito
            autorange="reversed"
        ),
        height=800,
        width=600,
        template="plotly_white"
    )
    
    fig = go.Figure(data=isotherm_traces + [trace_T, trace_Td], layout=layout)
    return fig

if __name__ == "__main__":
    # Settings similar to main script, or simplified for test
    city = "Huelva"
    # Probando con una fecha conocida o la intentada (si es válida)
    # Intentada 2026-01-14 -> LFC=NaN (Estable). Buena para un gráfico simple.
    yr, mn, dy, hr = "2026", "01", "14", "00"
    
    # Se utiliza una estación/fecha conocida que funciona si Huelva falla, pero primero se prueba Huelva
    # ya que funciona en el paso anterior (ignorando el sombreado LFC faltante).
    
    try:
        CodEst, station_name = find_station(city)
        print(f"Station: {station_name} ({CodEst})")
        
        # Download
        (p, T, Td), source = get_sounding(CodEst, yr, mn, dy, hr, "AUTO")
        print(f"Data retrieved from {source}. Levels: {len(p)}")
        
        # Plot
        fig = create_skewt_plotly(p, T, Td, station_name, f"{yr}-{mn}-{dy} {hr}Z")
        
        # Save
        script_dir = pathlib.Path(__file__).parent.absolute()
        output_path = script_dir.parent / "outputs" / "skewt_plotly.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fig.write_html(str(output_path))
        print(f"Plot saved to: {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")
