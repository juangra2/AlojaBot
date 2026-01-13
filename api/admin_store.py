# api/admin_store.py
from __future__ import annotations

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]  # raíz del proyecto
DATA_DIR = BASE_DIR / "data"

RESERVAS_XLSX = DATA_DIR / "reservas.xlsx"
CALENDARIO_XLSX = DATA_DIR / "calendario.xlsx"
ALOJAMIENTOS_XLSX = DATA_DIR / "alojamientos.xlsx"


def _ensure_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")


def load_reservas_df() -> pd.DataFrame:
    _ensure_exists(RESERVAS_XLSX)
    df = pd.read_excel(RESERVAS_XLSX)
    return normalize_reservas(df)


def save_reservas_df(df: pd.DataFrame) -> None:
    df = df.copy()
    df.to_excel(RESERVAS_XLSX, index=False)


def load_calendario_df() -> pd.DataFrame:
    _ensure_exists(CALENDARIO_XLSX)
    df = pd.read_excel(CALENDARIO_XLSX)

    # normaliza columnas esperadas
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    if "id_alojamiento" in df.columns:
        df["id_alojamiento"] = pd.to_numeric(df["id_alojamiento"], errors="coerce").astype("Int64")
    if "estado" in df.columns:
        df["estado"] = df["estado"].astype(str).str.strip().str.lower()

    return df


def save_calendario_df(df: pd.DataFrame) -> None:
    df = df.copy()
    df.to_excel(CALENDARIO_XLSX, index=False)


def load_alojamientos_df() -> pd.DataFrame:
    _ensure_exists(ALOJAMIENTOS_XLSX)
    df = pd.read_excel(ALOJAMIENTOS_XLSX)

    if "id" in df.columns:
        df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    if "nombre" in df.columns:
        df["nombre"] = df["nombre"].astype(str).str.strip()

    return df


def normalize_reservas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "check_in" in df.columns:
        df["check_in"] = pd.to_datetime(df["check_in"], errors="coerce").dt.date
    if "check_out" in df.columns:
        df["check_out"] = pd.to_datetime(df["check_out"], errors="coerce").dt.date

    # normaliza textos típicos
    for col in ["estado", "cliente_nombre", "cliente_email"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    if "cliente_email" in df.columns:
        df["cliente_email"] = df["cliente_email"].str.lower()

    if "id" in df.columns:
        df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")

    if "id_alojamiento" in df.columns:
        df["id_alojamiento"] = pd.to_numeric(df["id_alojamiento"], errors="coerce").astype("Int64")

    if "huespedes" in df.columns:
        df["huespedes"] = pd.to_numeric(df["huespedes"], errors="coerce").astype("Int64")

    if "precio_total" in df.columns:
        df["precio_total"] = pd.to_numeric(df["precio_total"], errors="coerce")

    return df


def precio_noche_by_aloj_id(aloj_id: int) -> float | None:
    df = load_alojamientos_df()
    if "precio_noche" not in df.columns:
        return None
    row = df[df["id"] == aloj_id]
    if row.empty:
        return None
    val = row.iloc[0].get("precio_noche")
    try:
        return float(val)
    except Exception:
        return None


def aloj_id_by_name(name: str) -> int | None:
    name_norm = (name or "").strip().lower()
    if not name_norm:
        return None
    df = load_alojamientos_df()
    if "nombre" not in df.columns:
        return None
    # match suave
    for _, r in df.iterrows():
        n = str(r.get("nombre", "")).strip()
        if n.lower() == name_norm:
            return int(r["id"])
    # contains
    for _, r in df.iterrows():
        n = str(r.get("nombre", "")).strip()
        if name_norm in n.lower():
            return int(r["id"])
    return None


def aloj_name_by_id(aloj_id: int) -> str:
    df = load_alojamientos_df()
    row = df[df["id"] == aloj_id]
    if row.empty:
        return f"#{aloj_id}"
    return str(row.iloc[0].get("nombre", f"#{aloj_id}")).strip()
