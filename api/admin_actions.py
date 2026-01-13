# api/admin_actions.py
from __future__ import annotations

from datetime import date, timedelta
import re

from .admin_store import (
    load_reservas_df,
    save_reservas_df,
    load_calendario_df,
    save_calendario_df,
    precio_noche_by_aloj_id,
    aloj_id_by_name,
    aloj_name_by_id,
)

def daterange(d1: date, d2: date):
    cur = d1
    while cur < d2:
        yield cur
        cur += timedelta(days=1)

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def free_days(aloj_name: str, year: int, month: int) -> dict:
    """
    Devuelve días libres del mes para un alojamiento.
    Si una fecha no está en calendario.xlsx, se considera libre.
    """
    aid = aloj_id_by_name(aloj_name)
    if not aid:
        return {"ok": False, "message": f"No encuentro el alojamiento '{aloj_name}'."}

    cal = load_calendario_df()
    # ocupados del alojamiento (set)
    occ = set()
    if not cal.empty:
        sub = cal[(cal["id_alojamiento"] == aid) & (cal["estado"] == "ocupado")]
        for f in sub["fecha"].dropna().tolist():
            if isinstance(f, date):
                occ.add(f)

    # iterar días del mes
    start = date(year, month, 1)
    # fin de mes
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    free = [d for d in daterange(start, end) if d not in occ]

    return {
        "ok": True,
        "id_alojamiento": aid,
        "alojamiento": aloj_name_by_id(aid),
        "year": year,
        "month": month,
        "free_days": free,
    }

def list_reservas(start: date, end: date, estado: str | None = "creada") -> dict:
    """
    Lista reservas cuyo check_in cae en [start, end).
    """
    df = load_reservas_df()
    if df.empty:
        return {"ok": True, "reservas": []}

    out = df.copy()
    if estado and "estado" in out.columns:
        out = out[out["estado"].astype(str).str.lower().str.strip() == estado.lower().strip()]

    out = out[(out["check_in"] >= start) & (out["check_in"] < end)]
    out = out.sort_values(["check_in", "id"], ascending=[True, True])

    reservas = []
    for _, r in out.iterrows():
        reservas.append({
            "id": int(r["id"]) if str(r.get("id", "")).strip() != "" else None,
            "id_alojamiento": int(r["id_alojamiento"]) if str(r.get("id_alojamiento","")).strip() != "" else None,
            "alojamiento": aloj_name_by_id(int(r["id_alojamiento"])) if r.get("id_alojamiento") else None,
            "check_in": r.get("check_in"),
            "check_out": r.get("check_out"),
            "huespedes": int(r["huespedes"]) if r.get("huespedes") else None,
            "precio_total": float(r["precio_total"]) if r.get("precio_total") is not None else None,
            "estado": r.get("estado"),
            "cliente_nombre": r.get("cliente_nombre"),
            "cliente_email": r.get("cliente_email"),
            "cliente_tel": r.get("cliente_tel"),
            "cliente_dni": r.get("cliente_dni"),
        })

    return {"ok": True, "start": start, "end": end, "reservas": reservas}

def find_reserva(query: str) -> dict:
    """
    Busca por:
    - ID si hay número claro
    - email si aparece
    - nombre (contains) si no
    """
    q = (query or "").strip()
    if not q:
        return {"ok": False, "message": "Necesito un nombre, email o ID."}

    df = load_reservas_df()
    if df.empty:
        return {"ok": True, "reservas": []}

    # ID
    m_id = re.search(r"\b(\d{1,6})\b", q)
    if m_id and ("reserva" in q.lower() or "reservation" in q.lower() or len(q.split()) == 1):
        rid = int(m_id.group(1))
        sub = df[df["id"] == rid]
        return {"ok": True, "reservas": sub.to_dict(orient="records")}

    # email
    m_email = re.search(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", q, re.I)
    if m_email and "cliente_email" in df.columns:
        email = m_email.group(0).lower()
        sub = df[df["cliente_email"].str.lower() == email]
        return {"ok": True, "reservas": sub.to_dict(orient="records")}

    # nombre
    name = q.lower()
    if "cliente_nombre" in df.columns:
        sub = df[df["cliente_nombre"].str.lower().str.contains(name, na=False)]
    else:
        sub = df.iloc[0:0]
    return {"ok": True, "reservas": sub.to_dict(orient="records")}

def cancel_reserva(reserva_id: int) -> dict:
    df = load_reservas_df()
    if df.empty:
        return {"ok": False, "message": f"No existe la reserva {reserva_id}."}

    row_idx = df.index[df["id"] == reserva_id].tolist()
    if not row_idx:
        return {"ok": False, "message": f"No existe la reserva {reserva_id}."}
    i = row_idx[0]
    row = df.loc[i]

    estado = str(row.get("estado", "")).strip().lower()
    if estado == "cancelada":
        return {"ok": False, "message": f"La reserva {reserva_id} ya está cancelada."}

    # liberar calendario
    aid = int(row["id_alojamiento"])
    ci = row["check_in"]; co = row["check_out"]
    cal = load_calendario_df()

    # si existen filas -> ponemos libre
    if not cal.empty:
        mask = (cal["id_alojamiento"] == aid) & (cal["fecha"].isin(list(daterange(ci, co))))
        cal.loc[mask, "estado"] = "libre"

    # guardar
    df.loc[i, "estado"] = "cancelada"
    save_reservas_df(df)
    save_calendario_df(cal)

    return {
        "ok": True,
        "id": reserva_id,
        "id_alojamiento": aid,
        "alojamiento": aloj_name_by_id(aid),
        "check_in": ci,
        "check_out": co,
    }

def modify_reserva(reserva_id: int, new_check_in: date, new_check_out: date, new_huespedes: int | None = None) -> dict:
    if new_check_out <= new_check_in:
        return {"ok": False, "message": "Las fechas no son válidas (check-out debe ser posterior a check-in)."}

    df = load_reservas_df()
    if df.empty:
        return {"ok": False, "message": f"No existe la reserva {reserva_id}."}

    row_idx = df.index[df["id"] == reserva_id].tolist()
    if not row_idx:
        return {"ok": False, "message": f"No existe la reserva {reserva_id}."}

    i = row_idx[0]
    row = df.loc[i]
    estado = str(row.get("estado", "")).strip().lower()
    if estado != "creada":
        return {"ok": False, "message": f"La reserva {reserva_id} no está en estado 'creada'."}

    aid = int(row["id_alojamiento"])
    old_ci = row["check_in"]; old_co = row["check_out"]
    old_h = int(row["huespedes"]) if row.get("huespedes") else None

    # disponibilidad (permitimos reutilizar días del tramo antiguo)
    cal = load_calendario_df()
    occupied = set()
    if not cal.empty:
        sub = cal[(cal["id_alojamiento"] == aid) & (cal["estado"] == "ocupado")]
        for f in sub["fecha"].dropna().tolist():
            if isinstance(f, date):
                occupied.add(f)

    old_set = set(daterange(old_ci, old_co))
    new_set = set(daterange(new_check_in, new_check_out))

    conflicts = sorted([d for d in new_set if (d in occupied and d not in old_set)])
    if conflicts:
        return {"ok": False, "message": f"Conflicto de disponibilidad. Ocupado: {conflicts[0]} (y más)."}

    # reescritura calendario:
    # 1) liberar tramo antiguo
    if not cal.empty:
        mask_old = (cal["id_alojamiento"] == aid) & (cal["fecha"].isin(list(old_set)))
        cal.loc[mask_old, "estado"] = "libre"

    # 2) ocupar tramo nuevo (crear filas si no existen)
    for d in sorted(new_set):
        if cal.empty:
            cal = cal.copy()
        mask_day = (cal["id_alojamiento"] == aid) & (cal["fecha"] == d)
        if mask_day.any():
            cal.loc[mask_day, "estado"] = "ocupado"
        else:
            cal = cal._append({"id_alojamiento": aid, "fecha": d, "estado": "ocupado"}, ignore_index=True)

    # actualizar reserva
    df.loc[i, "check_in"] = new_check_in
    df.loc[i, "check_out"] = new_check_out
    if new_huespedes is not None:
        df.loc[i, "huespedes"] = int(new_huespedes)

    # recalcular precio_total si podemos
    precio_noche = precio_noche_by_aloj_id(aid)
    noches = (new_check_out - new_check_in).days
    if precio_noche is not None and noches > 0:
        df.loc[i, "precio_total"] = float(precio_noche) * float(noches)

    save_reservas_df(df)
    save_calendario_df(cal)

    return {
        "ok": True,
        "id": reserva_id,
        "id_alojamiento": aid,
        "alojamiento": aloj_name_by_id(aid),
        "old_check_in": old_ci,
        "old_check_out": old_co,
        "check_in": new_check_in,
        "check_out": new_check_out,
        "old_huespedes": old_h,
        "huespedes": int(new_huespedes) if new_huespedes is not None else old_h,
        "noches": noches,
    }
