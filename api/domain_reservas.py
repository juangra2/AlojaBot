# api/domain_reservas.py
from __future__ import annotations

from datetime import date, datetime
from typing import List, Dict, Any
from datetime import date, timedelta

import pandas as pd

from .config import (
    load_alojamientos_calendario,
    load_reservas,
    daterange,
    RES_XLSX,
    CAL_XLSX,
    next_reserva_id,
)


# ---------- Búsqueda básica ----------


def buscar_opciones(capacidad=None, price_min=None, price_max=None, top=5) -> List[Dict]:
    aloj, _ = load_alojamientos_calendario()
    df = aloj.copy()
    if capacidad:
        df = df[df["capacidad"] >= int(capacidad)]
    if price_min is not None:
        df = df[df["precio_noche"] >= float(price_min)]
    if price_max is not None:
        df = df[df["precio_noche"] <= float(price_max)]
    cols = ["id", "nombre", "capacidad", "precio_noche"]
    if not set(cols).issubset(df.columns):
        raise RuntimeError("Faltan columnas esperadas en alojamientos.xlsx")
    return (
        df[cols]
        .sort_values("precio_noche")
        .head(top)
        .to_dict(orient="records")
    )


def hay_disponibilidad(id_aloj: int, check_in: date, check_out: date) -> bool:
    _, cal = load_alojamientos_calendario()
    mask = (cal["id_alojamiento"] == id_aloj) & (
        cal["fecha"] >= pd.Timestamp(check_in)
    ) & (cal["fecha"] < pd.Timestamp(check_out))
    sub = cal.loc[mask]
    if sub.empty:
        return True
    return (sub["estado"].str.lower() == "libre").all()


def encontrar_aloj_por_nombre(texto: str) -> int | None:
    from .utils_nlu import strip_accents

    aloj, _ = load_alojamientos_calendario()
    t = strip_accents(texto.lower())
    for _, row in aloj.iterrows():
        nombre = strip_accents(str(row["nombre"]).lower())
        if nombre and nombre in t:
            return int(row["id"])
    return None


def precio_noche_de(id_aloj: int) -> float:
    aloj, _ = load_alojamientos_calendario()
    r = aloj.loc[aloj["id"] == id_aloj]
    if r.empty:
        raise ValueError("Alojamiento no encontrado")
    return float(r.iloc[0]["precio_noche"])


def capacidad_de(id_aloj: int) -> int:
    aloj, _ = load_alojamientos_calendario()
    r = aloj.loc[aloj["id"] == id_aloj]
    if r.empty:
        return 0
    return int(r.iloc[0]["capacidad"])


def nombre_de(id_aloj: int) -> str:
    aloj, _ = load_alojamientos_calendario()
    r = aloj.loc[aloj["id"] == id_aloj]
    if r.empty:
        return f"Alojamiento {id_aloj}"
    return str(r.iloc[0]["nombre"])


# ---------- Crear reserva + idempotencia ----------


def crear_reserva_excel(
    id_aloj: int,
    check_in: date,
    check_out: date,
    huespedes: int,
    precio_noche: float,
    cliente_nombre: str | None = None,
    cliente_email: str | None = None,
    cliente_tel: str | None = None,
) -> int:
    df_res = load_reservas().copy()
    expected_cols = {
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
    }
    for c in expected_cols - set(df_res.columns):
        df_res[c] = pd.NA
    df_res["check_in"] = pd.to_datetime(df_res["check_in"], errors="coerce")
    df_res["check_out"] = pd.to_datetime(df_res["check_out"], errors="coerce")
    df_res["created_at"] = pd.to_datetime(df_res["created_at"], errors="coerce")

    cin_ts, cout_ts = pd.Timestamp(check_in), pd.Timestamp(check_out)
    now = datetime.now()
    ventana = pd.Timedelta(minutes=2)

    # Idempotencia
    mask_igual = (
        (df_res["id_alojamiento"] == id_aloj)
        & (df_res["check_in"] == cin_ts)
        & (df_res["check_out"] == cout_ts)
        & (df_res["huespedes"] == huespedes)
        & (df_res["estado"].fillna("").str.lower() == "creada")
    )
    mask_reciente = (now - df_res["created_at"]) <= ventana
    if (mask_igual & mask_reciente).any():
        rid = int(df_res.loc[(mask_igual & mask_reciente), "id"].iloc[0])
        # Refuerza calendario
        _, cal = load_alojamientos_calendario()
        cal_cp = cal.copy()
        cal_cp["fecha"] = pd.to_datetime(cal_cp["fecha"], errors="coerce")
        for f in daterange(check_in, check_out):
            f_ts = pd.Timestamp(f)
            mcal = (cal_cp["id_alojamiento"] == id_aloj) & (
                cal_cp["fecha"] == f_ts
            )
            if mcal.any():
                cal_cp.loc[mcal, "estado"] = "ocupado"
            else:
                cal_cp = pd.concat(
                    [
                        cal_cp,
                        pd.DataFrame(
                            [
                                {
                                    "id_alojamiento": id_aloj,
                                    "fecha": f_ts,
                                    "estado": "ocupado",
                                }
                            ]
                        ),
                    ],
                    ignore_index=True,
                )
        cal_cp.sort_values(["id_alojamiento", "fecha"], inplace=True)
        cal_cp.to_excel(CAL_XLSX, index=False)
        return rid

    # Nueva reserva
    rid = next_reserva_id(df_res)
    noches = max(1, (check_out - check_in).days)
    total = round(noches * float(precio_noche), 2)
    nueva = pd.DataFrame(
        [
            {
                "id": rid,
                "id_alojamiento": id_aloj,
                "check_in": cin_ts,
                "check_out": cout_ts,
                "huespedes": huespedes,
                "precio_total": total,
                "estado": "creada",
                "cliente_nombre": cliente_nombre or "",
                "cliente_email": cliente_email or "",
                "cliente_tel": cliente_tel or "",
                "created_at": now,
            }
        ]
    )
    df_res = pd.concat([df_res, nueva], ignore_index=True)
    df_res.to_excel(RES_XLSX, index=False)

    # Calendario
    _, cal = load_alojamientos_calendario()
    cal_cp = cal.copy()
    cal_cp["fecha"] = pd.to_datetime(cal_cp["fecha"], errors="coerce")
    for f in daterange(check_in, check_out):
        f_ts = pd.Timestamp(f)
        mcal = (cal_cp["id_alojamiento"] == id_aloj) & (
            cal_cp["fecha"] == f_ts
        )
        if mcal.any():
            cal_cp.loc[mcal, "estado"] = "ocupado"
        else:
            cal_cp = pd.concat(
                [
                    cal_cp,
                    pd.DataFrame(
                        [
                            {
                                "id_alojamiento": id_aloj,
                                "fecha": f_ts,
                                "estado": "ocupado",
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )
    cal_cp.sort_values(["id_alojamiento", "fecha"], inplace=True)
    cal_cp.to_excel(CAL_XLSX, index=False)
    return rid


# ---------- Helpers dominio reservas (consulta / cancelar / modificar) ----------


def load_reservas_normalized() -> pd.DataFrame:
    df = load_reservas().copy()
    if df.empty:
        return df
    df["check_in"] = pd.to_datetime(df["check_in"], errors="coerce")
    df["check_out"] = pd.to_datetime(df["check_out"], errors="coerce")
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    if "estado" in df.columns:
        df["estado"] = df["estado"].fillna("").str.lower()
    if "cliente_email" in df.columns:
        df["cliente_email"] = (
            df["cliente_email"].fillna("").str.strip().str.lower()
        )
    return df


def get_reserva_by_id(reserva_id: int):
    df = load_reservas_normalized()
    if df.empty or "id" not in df.columns:
        return None
    rid = int(reserva_id)
    mask = pd.to_numeric(df["id"], errors="coerce") == rid
    if not mask.any():
        return None
    return df.loc[mask].iloc[0]


def list_reservas_by_email(
    email: str,
    check_in: date | None = None,
    check_out: date | None = None,
    solo_activas: bool = True,
    max_items: int = 20,
) -> list[dict]:
    df = load_reservas_normalized()
    if df.empty:
        return []
    email_norm = email.strip().lower()
    df = df[df["cliente_email"] == email_norm]
    if solo_activas and "estado" in df.columns:
        df = df[df["estado"] == "creada"]
    if check_in:
        df = df[df["check_in"] >= pd.Timestamp(check_in)]
    if check_out:
        df = df[df["check_out"] <= pd.Timestamp(check_out)]
    df = df.sort_values("check_in").head(max_items)
    return df.to_dict(orient="records")


def format_reserva_row(row: dict) -> str:
    rid = int(row.get("id"))
    id_aloj = int(row.get("id_alojamiento"))
    nombre = nombre_de(id_aloj)

    cin = (
        pd.to_datetime(row.get("check_in")).date()
        if row.get("check_in")
        else None
    )
    cout = (
        pd.to_datetime(row.get("check_out")).date()
        if row.get("check_out")
        else None
    )
    noches = (cout - cin).days if (cin and cout) else 0

    hues = int(row.get("huespedes") or 0)
    estado = str(row.get("estado") or "").lower() or "desconocido"
    estado_pretty = estado.capitalize()
    total = float(row.get("precio_total") or 0.0)

    return (
        f"ID {rid} · {nombre}\n"
        f"📅 Fechas: {cin} → {cout} ({noches} noche(s))\n"
        f"👥 Huéspedes: {hues}\n"
        f"🔖 Estado: {estado_pretty}\n"
        f"💶 Total: {total} €"
    )


def cancelar_reserva_excel(reserva_id: int) -> dict:
    df = load_reservas_normalized()
    if df.empty or "id" not in df.columns:
        return {"ok": False, "message": "No hay reservas registradas. 😕"}

    rid = int(reserva_id)
    mask = pd.to_numeric(df["id"], errors="coerce") == rid
    if not mask.any():
        return {
            "ok": False,
            "message": f"No encuentro la reserva {rid}. ❓",
        }

    row = df.loc[mask].iloc[0]
    estado = str(row.get("estado") or "").lower()
    if estado != "creada":
        return {
            "ok": False,
            "message": f"La reserva {rid} está en estado '{estado}' y no puede cancelarse. ⚠️",
        }

    id_aloj = int(row["id_alojamiento"])
    cin = pd.to_datetime(row["check_in"]).date()
    cout = pd.to_datetime(row["check_out"]).date()

    # Actualiza reservas.xlsx
    df.loc[mask, "estado"] = "cancelada"
    df.to_excel(RES_XLSX, index=False)

    # Libera calendario
    _, cal = load_alojamientos_calendario()
    cal_cp = cal.copy()
    cal_cp["fecha"] = pd.to_datetime(cal_cp["fecha"], errors="coerce")
    for f in daterange(cin, cout):
        f_ts = pd.Timestamp(f)
        mcal = (cal_cp["id_alojamiento"] == id_aloj) & (
            cal_cp["fecha"] == f_ts
        )
        if mcal.any():
            cal_cp.loc[mcal, "estado"] = "libre"
    cal_cp.sort_values(["id_alojamiento", "fecha"], inplace=True)
    cal_cp.to_excel(CAL_XLSX, index=False)

    return {
        "ok": True,
        "id": rid,
        "id_alojamiento": id_aloj,
        "check_in": cin,
        "check_out": cout,
    }


def modificar_reserva_excel(
    reserva_id: int,
    new_check_in: date | None = None,
    new_check_out: date | None = None,
    new_huespedes: int | None = None,
) -> dict:
    df = load_reservas_normalized()
    if df.empty or "id" not in df.columns:
        return {"ok": False, "message": "No hay reservas registradas. 😕"}

    rid = int(reserva_id)
    mask = pd.to_numeric(df["id"], errors="coerce") == rid
    if not mask.any():
        return {
            "ok": False,
            "message": f"No encuentro la reserva {rid}. ❓",
        }

    row = df.loc[mask].iloc[0]
    estado = str(row.get("estado") or "").lower()
    if estado != "creada":
        return {
            "ok": False,
            "message": f"La reserva {rid} está en estado '{estado}' y no puede modificarse. ⚠️",
        }

    id_aloj = int(row["id_alojamiento"])
    old_ci = pd.to_datetime(row["check_in"]).date()
    old_co = pd.to_datetime(row["check_out"]).date()
    old_hues = int(row.get("huespedes") or 0)

    cin = new_check_in or old_ci
    cout = new_check_out or old_co
    hues = int(new_huespedes or old_hues)

        # Regla: no mover reservas a fechas pasadas ni a hoy
    today = date.today()
    if cin <= today:
        if cin == today:
            return {
                "ok": False,
                "message": (
                    "Solo puedo mover reservas con **al menos un día de antelación**. "
                    "El nuevo check-in no puede ser hoy. 📅"
                ),
            }
        else:
            return {
                "ok": False,
                "message": (
                    "No puedo mover una reserva a **fechas que ya han pasado**. "
                    "Elige un check-in futuro. ⏭️"
                ),
            }

    if cout <= cin:
        return {
            "ok": False,
            "message": "La fecha de salida debe ser posterior a la de entrada. 📅",
        }

    # Capacidad
    cap = capacidad_de(id_aloj)
    if hues > cap:
        return {
            "ok": False,
            "message": f"El alojamiento admite hasta {cap} huéspedes. No puedo subir a {hues}. 👥",
        }

    # Disponibilidad (permitiendo días ya ocupados por esta misma reserva)
    _, cal = load_alojamientos_calendario()
    cal_cp = cal.copy()
    cal_cp["fecha"] = pd.to_datetime(cal_cp["fecha"], errors="coerce")

    for f in daterange(cin, cout):
        if old_ci <= f < old_co:
            continue
        f_ts = pd.Timestamp(f)
        mcal = (cal_cp["id_alojamiento"] == id_aloj) & (
            cal_cp["fecha"] == f_ts
        )
        sub = cal_cp.loc[mcal]
        if not sub.empty and not (sub["estado"].str.lower() == "libre").all():
            return {
                "ok": False,
                "message": f"El rango {cin} → {cout} está ocupado en {nombre_de(id_aloj)}. 🟥",
            }

    # Actualiza reservas.xlsx
    noches = max(1, (cout - cin).days)
    pn = precio_noche_de(id_aloj)
    total = round(noches * pn, 2)

    df.loc[mask, "check_in"] = pd.Timestamp(cin)
    df.loc[mask, "check_out"] = pd.Timestamp(cout)
    df.loc[mask, "huespedes"] = hues
    df.loc[mask, "precio_total"] = total
    df.to_excel(RES_XLSX, index=False)

    # Actualiza calendario: liberar antiguo rango + bloquear nuevo
    for f in daterange(old_ci, old_co):
        f_ts = pd.Timestamp(f)
        mcal = (cal_cp["id_alojamiento"] == id_aloj) & (
            cal_cp["fecha"] == f_ts
        )
        if mcal.any():
            cal_cp.loc[mcal, "estado"] = "libre"

    for f in daterange(cin, cout):
        f_ts = pd.Timestamp(f)
        mcal = (cal_cp["id_alojamiento"] == id_aloj) & (
            cal_cp["fecha"] == f_ts
        )
        if mcal.any():
            cal_cp.loc[mcal, "estado"] = "ocupado"
        else:
            cal_cp = pd.concat(
                [
                    cal_cp,
                    pd.DataFrame(
                        [
                            {
                                "id_alojamiento": id_aloj,
                                "fecha": f_ts,
                                "estado": "ocupado",
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

    cal_cp.sort_values(["id_alojamiento", "fecha"], inplace=True)
    cal_cp.to_excel(CAL_XLSX, index=False)

    return {
        "ok": True,
        "id": rid,
        "id_alojamiento": id_aloj,
        "old_check_in": old_ci,
        "old_check_out": old_co,
        "old_huespedes": old_hues,
        "check_in": cin,
        "check_out": cout,
        "huespedes": hues,
        "precio_total": total,
    }
