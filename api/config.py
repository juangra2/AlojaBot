# api/config.py
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# --- Paths de datos ---
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ALOJ_XLSX = DATA_DIR / "alojamientos.xlsx"
CAL_XLSX = DATA_DIR / "calendario.xlsx"
RES_XLSX = DATA_DIR / "reservas.xlsx"


def daterange(d0: date, d1: date):
    """Generador de fechas [d0, d1)."""
    cur = d0
    while cur < d1:
        yield cur
        cur += timedelta(days=1)


def load_alojamientos_calendario():
    aloj = pd.read_excel(ALOJ_XLSX)
    cal = pd.read_excel(CAL_XLSX, parse_dates=["fecha"])
    aloj.columns = [c.strip().lower() for c in aloj.columns]
    cal.columns = [c.strip().lower() for c in cal.columns]
    return aloj, cal


def load_reservas():
    if RES_XLSX.exists():
        df = pd.read_excel(RES_XLSX)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    return pd.DataFrame(
        columns=[
            "id",
            "id_alojamiento",
            "check_in",
            "check_out",
            "huespedes",
            "precio_total",
            "estado",
            "cliente_nombre",
            "cliente_email",
            "cliente_tel",
            "created_at",
        ]
    )


def next_reserva_id(df_res: pd.DataFrame) -> int:
    if df_res.empty or "id" not in df_res.columns:
        return 1
    try:
        return int(pd.to_numeric(df_res["id"], errors="coerce").fillna(0).max()) + 1
    except Exception:
        return 1
