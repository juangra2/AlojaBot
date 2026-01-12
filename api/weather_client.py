# api/weather_client.py
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import logging

import pandas as pd
import requests

from .config import DATA_DIR
from .config import ALOJ_XLSX  # type: ignore[attr-defined]

# Coordenadas por defecto (Cobisa)
DEFAULT_LAT = 39.805084
DEFAULT_LON = -4.024354
DEFAULT_TZ = "Europe/Madrid"

# Horizonte máximo razonable de predicción (días)
FORECAST_MAX_DAYS = 16

logger = logging.getLogger(__name__)


def _load_alojamientos() -> pd.DataFrame | None:
    try:
        df = pd.read_excel(ALOJ_XLSX)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except Exception as e:
        logger.warning(
            "No se ha podido leer alojamientos.xlsx para meteo: %s", e
        )
        return None


def get_coords_for_aloj(id_aloj: int | None) -> tuple[float, float]:
    df = _load_alojamientos()
    if df is None:
        return DEFAULT_LAT, DEFAULT_LON

    if (
        id_aloj is not None
        and "id" in df.columns
        and "lat" in df.columns
        and "lon" in df.columns
    ):
        row = df.loc[df["id"] == id_aloj]
        if not row.empty:
            try:
                lat = float(row.iloc[0]["lat"])
                lon = float(row.iloc[0]["lon"])
                return lat, lon
            except Exception:
                pass

    if "lat" in df.columns and "lon" in df.columns and not df.empty:
        row0 = df.iloc[0]
        try:
            lat = float(row0["lat"])
            lon = float(row0["lon"])
            return lat, lon
        except Exception:
            pass

    return DEFAULT_LAT, DEFAULT_LON

def get_place_label(aloj_id: int | None) -> str:
    df = _load_alojamientos()
    if df is None or df.empty:
        return "Cobisa (Toledo)"

    if aloj_id is not None and "id" in df.columns and "nombre" in df.columns:
        row = df.loc[df["id"] == aloj_id]
        if not row.empty:
            nombre = str(row.iloc[0]["nombre"])
            loc = str(row.iloc[0].get("localidad") or "Cobisa")
            return f"{nombre} — {loc} (Toledo)"

    # fallback
    loc = str(df.iloc[0].get("localidad") or "Cobisa")
    return f"{loc} (Toledo)"



def get_forecast_summary_for_range(
    check_in: date,
    check_out: date,
    aloj_id: int | None = None,
) -> str:
    """
    Llama a Open-Meteo para el rango [check_in, check_out) y devuelve
    un resumen textual en castellano.

    - Si todo el rango está en el pasado -> mensaje de solo futuro.
    - Si el inicio está demasiado lejos -> mensaje de que aún no hay datos.
    """
    if not (check_in and check_out) or check_out <= check_in:
        return "⛔ No puedo mirar el tiempo porque las fechas no son válidas."

    today = date.today()

    # 1) Todo el rango en el pasado
    if check_out <= today:
        return (
            "📅 Solo puedo darte un pronóstico para fechas futuras; "
            "para fechas pasadas no tengo datos históricos detallados."
        )

    # 2) Rango mixto pasado/futuro -> recortamos inicio a hoy
    if check_in < today:
        check_in = today

    # 3) Demasiado lejos en el futuro
    end = check_out - timedelta(days=1)
    max_ahead = (end - today).days
    if max_ahead > FORECAST_MAX_DAYS:
        return (
            "🌤️ Los modelos de predicción solo llegan aproximadamente a "
            f"{FORECAST_MAX_DAYS} días vista. Para esas fechas aún no hay "
            "datos de pronóstico disponibles."
        )


    start = check_in

    lat, lon = get_coords_for_aloj(aloj_id)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
            ]
        ),
        "timezone": DEFAULT_TZ,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }

    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Fallo al llamar a Open-Meteo: %s", e)
        return (
            "⚠️ Ahora mismo no he podido consultar el tiempo; "
            "parece haber un problema al acceder al servicio meteorológico."
        )

    daily = data.get("daily")
    if not daily:
        return (
            "🌥️ No hay datos de pronóstico disponibles para esas fechas.\n"
            "Prueba con un rango más cercano en el tiempo."
        )

    times = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    precip = daily.get("precipitation_sum") or []
    prob = daily.get("precipitation_probability_max") or []
    wind = daily.get("wind_speed_10m_max") or []
    gust = daily.get("wind_gusts_10m_max") or []


    if not times or not tmax or not tmin:
        return (
            "🌥️ No hay datos de pronóstico disponibles para esas fechas.\n"
            "Prueba con un rango más cercano en el tiempo."
        )

    n = min(len(times), len(tmax), len(tmin), len(wind) or 10**9, len(gust) or 10**9)
    tmax = tmax[:n]
    tmin = tmin[:n]
    precip = precip[:n] if precip else [0.0] * n
    prob = prob[:n] if prob else [None] * n
    wind = wind[:n] if wind else [None] * n
    gust = gust[:n] if gust else [None] * n

    wind_vals = [w for w in wind if w is not None]
    gust_vals = [g for g in gust if g is not None]
    max_max = round(max(tmax), 1)
    min_min = round(min(tmin), 1)
    avg_max = round(sum(tmax) / n, 1)
    avg_min = round(sum(tmin) / n, 1)

    total_precip = round(sum(precip), 1) if precip else None

    max_prob = None
    vals_prob = [p for p in prob if p is not None]
    if vals_prob:
        max_prob = max(vals_prob)

    if max_prob is None:
        lluvia_txt = "sin datos claros de lluvia"
    elif max_prob <= 20:
        lluvia_txt = "con baja probabilidad de lluvia"
    elif max_prob <= 60:
        lluvia_txt = "con alguna probabilidad de lluvia"
    else:
        lluvia_txt = "con alta probabilidad de lluvia"

    if total_precip is not None and total_precip > 0:
        lluvia_txt += f" (precipitación acumulada ~ {total_precip} mm)"
    
    wind_txt = ""
    if wind_vals:
        wind_txt = f"\n- 💨 Viento máx aprox.: {round(max(wind_vals),1)} km/h"
        if gust_vals:
            wind_txt += f" (rachas hasta {round(max(gust_vals),1)} km/h)"

    rango_fechas = f"{start} → {end}"

    place = get_place_label(aloj_id)

    return (
        f"📍 Lugar: {place}\n"
        f"🌤️ Pronóstico aproximado para esas fechas ({rango_fechas}):\n"
        f"- Temperaturas máximas ~ {avg_max} °C (entre {min(tmax)} y {max_max} °C)\n"
        f"- Temperaturas mínimas ~ {avg_min} °C (entre {min_min} y {max(tmin)} °C)\n"
        f"- Tiempo {lluvia_txt}."
        f"{wind_txt}"
    )
