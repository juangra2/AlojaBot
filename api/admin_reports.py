# api/admin_reports.py
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from .admin_store import load_reservas_df, load_calendario_df, load_alojamientos_df, aloj_name_by_id


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def _year_range(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year + 1, 1, 1)


def _safe_days(start: date, end: date) -> int:
    return max(0, (end - start).days)


def _date_from_iso(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _filter_df(
    scope: str,
    estado: str,
    year: int,
    month: int,
    date_from: Optional[str],
    date_to: Optional[str],
) -> tuple[pd.DataFrame, Optional[date], Optional[date]]:
    df = load_reservas_df()
    if df.empty:
        return df, None, None

    # Estado
    est = (estado or "all").strip().lower()
    if est != "all" and "estado" in df.columns:
        df = df[df["estado"].astype(str).str.strip().str.lower() == est]

    start = end = None

    if scope == "month":
        start, end = _month_range(year, month)
        df = df[(df["check_in"] >= start) & (df["check_in"] < end)]
    elif scope == "year":
        start, end = _year_range(year)
        df = df[(df["check_in"] >= start) & (df["check_in"] < end)]
    elif scope == "range":
        s = _date_from_iso(date_from)
        e = _date_from_iso(date_to)
        if s and e and e > s:
            start, end = s, e
            df = df[(df["check_in"] >= start) & (df["check_in"] < end)]
    elif scope == "all":
        # sin filtro de fechas
        start = end = None

    return df, start, end


def list_reservas_filtered(
    scope: str,
    estado: str,
    year: int,
    month: int,
    date_from: Optional[str],
    date_to: Optional[str],
) -> list[dict]:
    df, _, _ = _filter_df(scope, estado, year, month, date_from, date_to)
    if df.empty:
        return []

    # Orden por ID (TOC-friendly 😄)
    if "id" in df.columns:
        df = df.sort_values(["id"], ascending=[True])

    items: list[dict] = []
    for _, r in df.iterrows():
        rid = int(r["id"]) if pd.notna(r.get("id")) else None
        aid = int(r["id_alojamiento"]) if pd.notna(r.get("id_alojamiento")) else None

        ci = r.get("check_in")
        co = r.get("check_out")
        ci_s = ci.isoformat() if isinstance(ci, date) else (str(ci) if ci is not None else "")
        co_s = co.isoformat() if isinstance(co, date) else (str(co) if co is not None else "")

        items.append(
            {
                "id": rid,
                "id_alojamiento": aid,
                "alojamiento_nombre": aloj_name_by_id(aid) if aid else None,
                "check_in": ci_s,
                "check_out": co_s,
                "huespedes": int(r["huespedes"]) if pd.notna(r.get("huespedes")) else None,
                "precio_total": float(r["precio_total"]) if pd.notna(r.get("precio_total")) else None,
                "estado": (str(r.get("estado", "")) or "").strip(),
                "cliente_nombre": (str(r.get("cliente_nombre", "")) or "").strip(),
                "cliente_email": (str(r.get("cliente_email", "")) or "").strip(),
                "cliente_tel": (str(r.get("cliente_tel", "")) or "").strip(),
                "cliente_dni": (str(r.get("cliente_dni", "")) or "").strip(),  # <-- DNI/NIE
                "created_at": (str(r.get("created_at", "")) or "").strip(),
            }
        )

    return items


def get_reserva_by_id(reserva_id: int) -> Optional[dict]:
    df = load_reservas_df()
    if df.empty or "id" not in df.columns:
        return None
    sub = df[df["id"] == reserva_id]
    if sub.empty:
        return None
    r = sub.iloc[0]
    aid = int(r["id_alojamiento"]) if pd.notna(r.get("id_alojamiento")) else None

    ci = r.get("check_in")
    co = r.get("check_out")
    ci_s = ci.isoformat() if isinstance(ci, date) else (str(ci) if ci is not None else "")
    co_s = co.isoformat() if isinstance(co, date) else (str(co) if co is not None else "")

    return {
        "id": int(r["id"]) if pd.notna(r.get("id")) else None,
        "id_alojamiento": aid,
        "alojamiento_nombre": aloj_name_by_id(aid) if aid else None,
        "check_in": ci_s,
        "check_out": co_s,
        "huespedes": int(r["huespedes"]) if pd.notna(r.get("huespedes")) else None,
        "precio_total": float(r["precio_total"]) if pd.notna(r.get("precio_total")) else None,
        "estado": (str(r.get("estado", "")) or "").strip(),
        "cliente_nombre": (str(r.get("cliente_nombre", "")) or "").strip(),
        "cliente_email": (str(r.get("cliente_email", "")) or "").strip(),
        "cliente_tel": (str(r.get("cliente_tel", "")) or "").strip(),
        "cliente_dni": (str(r.get("cliente_dni", "")) or "").strip(),
        "created_at": (str(r.get("created_at", "")) or "").strip(),
    }


def compute_metrics(scope: str, year: int, month: int) -> dict:
    # Para métricas usamos solo reservas "creada" (si quieres incluir canceladas, cambia aquí)
    df, start, end = _filter_df(scope, "creada", year, month, None, None)

    revenue = float(df["precio_total"].sum()) if (not df.empty and "precio_total" in df.columns) else 0.0

    # noches ocupadas desde reservas
    occ_nights = 0
    if not df.empty and "check_in" in df.columns and "check_out" in df.columns:
        for _, r in df.iterrows():
            ci = r.get("check_in")
            co = r.get("check_out")
            if isinstance(ci, date) and isinstance(co, date) and co > ci:
                occ_nights += (co - ci).days

    adr = (revenue / occ_nights) if occ_nights > 0 else 0.0

    # ocupación global con calendario si hay rango; si no, aproximamos con reservas
    aloj = load_alojamientos_df()
    n_aloj = int(aloj["id"].dropna().nunique()) if (not aloj.empty and "id" in aloj.columns) else 1
    if n_aloj <= 0:
        n_aloj = 1

    occupancy = 0.0
    revpar = 0.0

    if scope in ("month", "year") and start and end:
        days = _safe_days(start, end)
        total_available = days * n_aloj

        cal = load_calendario_df()
        occ_days = 0
        if not cal.empty and {"fecha", "estado"}.issubset(set(cal.columns)):
            sub = cal[(cal["fecha"] >= start) & (cal["fecha"] < end) & (cal["estado"] == "ocupado")]
            occ_days = int(len(sub))

        # fallback: si calendario está vacío, usa noches de reservas
        if occ_days == 0 and occ_nights > 0:
            occ_days = occ_nights

        occupancy = (occ_days / total_available) if total_available > 0 else 0.0
        revpar = (revenue / total_available) if total_available > 0 else 0.0
    else:
        # scope "all": sin rango, devolvemos ocupación/revpar como 0 (o podrías estimarlo)
        occupancy = 0.0
        revpar = 0.0

    reservas_checkin = int(len(df)) if not df.empty else 0

    # top alojamiento
    top_name = None
    top_rev = 0.0
    if not df.empty and {"id_alojamiento", "precio_total"}.issubset(df.columns):
        grp = df.groupby("id_alojamiento")["precio_total"].sum().sort_values(ascending=False)
        if len(grp) > 0:
            top_id = int(grp.index[0])
            top_rev = float(grp.iloc[0])
            top_name = aloj_name_by_id(top_id)

    return {
        "revenue": round(revenue, 2),
        "occupancy": float(occupancy),
        "reservas_checkin": reservas_checkin,
        "adr": round(adr, 2),
        "revpar": round(revpar, 2),
        "top_alojamiento": top_name,
        "top_revenue": round(top_rev, 2),
    }


def compute_series(year: int, kind: str) -> dict:
    labels = [f"{m:02d}" for m in range(1, 13)]
    values: list[float] = []

    for m in range(1, 13):
        met = compute_metrics(scope="month", year=year, month=m)
        if kind == "occupancy":
            values.append(float(met.get("occupancy") or 0.0))
        else:
            values.append(float(met.get("revenue") or 0.0))

    title = ("Ocupación " if kind == "occupancy" else "Facturación ") + str(year)
    return {"labels": labels, "values": values, "title": title}


def export_reservas_csv(
    scope: str,
    estado: str,
    year: int,
    month: int,
    date_from: Optional[str],
    date_to: Optional[str],
) -> bytes:
    items = list_reservas_filtered(scope, estado, year, month, date_from, date_to)
    df = pd.DataFrame(items)
    csv_text = df.to_csv(index=False)
    return csv_text.encode("utf-8")
