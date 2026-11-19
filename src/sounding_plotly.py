
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

def create_skewt_plotly(p, T, Td, station_name, date_str, is_dark=False):
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

    hover_style = dict(
        bgcolor="#1e222b" if is_dark else "#ffffff",
        bordercolor="rgba(250, 250, 250, 0.35)" if is_dark else "rgba(31, 41, 55, 0.35)",
        font=dict(color="#fafafa" if is_dark else "#1f2937", size=12)
    )
    
    # Create traces
    trace_T = go.Scatter(
        x=T_skewed,
        y=p_vals,
        mode='lines+markers',
        name='Temperature',
        line=dict(color='#ff4b4b' if is_dark else 'red', width=2),
        hoverlabel=hover_style,
        hovertemplate='P: %{y:.1f} hPa<br>T: %{text:.1f} °C',
        text=T_vals # Pass actual T for hover
    )
    
    trace_Td = go.Scatter(
        x=Td_skewed,
        y=p_vals,
        mode='lines',
        name='Dew point',
        line=dict(color='#00e676' if is_dark else 'green', width=2),
        hoverlabel=hover_style,
        hovertemplate='P: %{y:.1f} hPa<br>Td: %{text:.1f} °C',
        text=Td_vals
    )
    
    # Isotermas (líneas diagonales en este sistema sesgado)
    isotherm_traces = []
    ref_temps = range(-100, 50, 10)
    ref_pressures = np.linspace(1050, 1, 100)
    iso_color = 'rgba(200, 210, 225, 0.22)' if is_dark else 'lightgrey'
    
    for temp in ref_temps:
        x_iso = skew_x(np.full_like(ref_pressures, temp), ref_pressures)
        isotherm_traces.append(go.Scatter(
            x=x_iso,
            y=ref_pressures,
            mode='lines',
            line=dict(color=iso_color, width=0.6, dash='dot'),
            showlegend=False,
            hoverinfo='skip'
        ))

    text_color = "#fafafa" if is_dark else "#1f2937"
    grid_color = "rgba(255, 255, 255, 0.12)" if is_dark else "rgba(0, 0, 0, 0.1)"
    paper_bg = "#0e1117" if is_dark else "#ffffff"
    plot_bg = "#141821" if is_dark else "#ffffff"

    layout = go.Layout(
        title=dict(
            text=f"Skew-T (Plotly) - {station_name} - {date_str}",
            font=dict(color=text_color)
        ),
        xaxis=dict(
            title=dict(text="Temperature (ºC)", font=dict(color=text_color)),
            tickfont=dict(color=text_color),
            gridcolor=grid_color,
            showgrid=True,
            zeroline=False
        ),
        yaxis=dict(
            title=dict(text="Pressure (hPa)", font=dict(color=text_color)),
            tickfont=dict(color=text_color),
            gridcolor=grid_color,
            type="log",
            range=[np.log10(1050), np.log10(1)],
            autorange="reversed"
        ),
        height=800,
        width=600,
        template="plotly_dark" if is_dark else "plotly_white",
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        font=dict(color=text_color),
        legend=dict(
            font=dict(color=text_color),
            bgcolor="rgba(20, 24, 33, 0.75)" if is_dark else "rgba(255, 255, 255, 0.75)"
        ),
        hoverlabel=hover_style
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
        (p, T, Td, u, v), source = get_sounding(CodEst, yr, mn, dy, hr, "AUTO")
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
