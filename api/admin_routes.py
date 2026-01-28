# api/admin_routes.py
from __future__ import annotations

import hashlib
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from .admin_bot import admin_chat
from .admin_reports import (
    compute_metrics,
    compute_series,
    list_reservas_filtered,
    get_reserva_by_id,
    export_reservas_csv,
)
from .admin_actions import cancel_reserva, modify_reserva
from .admin_store import load_alojamientos_df, aloj_name_by_id


router = APIRouter(tags=["admin"])

# =========================
# LOGIN HARDCODED (DEMO)
# =========================
ADMIN_USERNAME = "admin"         # <-- CAMBIA AQUÍ
ADMIN_PASSWORD = "admin123"      # <-- CAMBIA AQUÍ

# Token estable (cambia si cambias user/pass)
_ADMIN_TOKEN = hashlib.sha256(
    f"{ADMIN_USERNAME}:{ADMIN_PASSWORD}:aloja-admin".encode("utf-8")
).hexdigest()[:32]


def require_admin(x_admin_token: str | None = Header(default=None)):
    if not x_admin_token or x_admin_token != _ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


class AdminLoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def admin_login(inp: AdminLoginIn):
    u = (inp.username or "").strip()
    p = (inp.password or "").strip()

    if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
        return {"ok": True, "token": _ADMIN_TOKEN}

    return {"ok": False, "message": "Usuario o contraseña incorrectos."}


@router.get("/me")
def admin_me(_: None = Depends(require_admin)):
    return {"ok": True}

@router.get("/alojamientos")
def admin_alojamientos(_: None = Depends(require_admin)):
    df = load_alojamientos_df()
    if df.empty or "id" not in df.columns:
        return {"ok": True, "items": []}

    ids = sorted({int(x) for x in df["id"].dropna().tolist()})
    items = [{"id": i, "nombre": (aloj_name_by_id(i) or f"Alojamiento {i}")} for i in ids]
    return {"ok": True, "items": items}



# =========================
# MÉTRICAS + SERIES (GRÁFICAS)
# =========================

@router.get("/metrics")
def admin_metrics(
    scope: str = Query("month", pattern="^(month|year|all)$"),
    year: int = Query(date.today().year, ge=2000, le=2100),
    month: int = Query(date.today().month, ge=1, le=12),
    aloj_id: Optional[int] = Query(default=None),
    _: None = Depends(require_admin),
):
    return compute_metrics(scope=scope, year=year, month=month, aloj_id=aloj_id)


@router.get("/series")
def admin_series(
    year: int = Query(date.today().year, ge=2000, le=2100),
    kind: str = Query("revenue", pattern="^(revenue|occupancy)$"),
    aloj_id: Optional[int] = Query(default=None),
    _: None = Depends(require_admin),
):
    return compute_series(year=year, kind=kind, aloj_id=aloj_id)



# =========================
# RESERVAS (tabla + acciones)
# =========================
@router.get("/reservas")
def admin_reservas(
    scope: str = Query("month", pattern="^(month|year|all|range)$"),
    estado: str = Query("all"),
    year: int = Query(date.today().year, ge=2000, le=2100),
    month: int = Query(date.today().month, ge=1, le=12),
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    aloj_id: Optional[int] = Query(default=None, ge=1),
    _: None = Depends(require_admin),
):
    items = list_reservas_filtered(
        scope=scope, estado=estado, year=year, month=month, date_from=from_, date_to=to, aloj_id=aloj_id
    )
    return {"ok": True, "items": items}


@router.get("/reserva/{reserva_id}")
def admin_reserva_get(reserva_id: int, _: None = Depends(require_admin)):
    item = get_reserva_by_id(reserva_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return {"ok": True, "item": item}


class ModifyIn(BaseModel):
    new_check_in: str
    new_check_out: str
    new_huespedes: int | None = None


@router.post("/reserva/{reserva_id}/cancel")
def admin_reserva_cancel(reserva_id: int, _: None = Depends(require_admin)):
    out = cancel_reserva(reserva_id)
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out.get("message", "No se pudo cancelar"))
    return {"ok": True, "message": f"✅ Reserva {reserva_id} cancelada."}


@router.post("/reserva/{reserva_id}/modify")
def admin_reserva_modify(reserva_id: int, inp: ModifyIn, _: None = Depends(require_admin)):
    try:
        ci = date.fromisoformat(inp.new_check_in)
        co = date.fromisoformat(inp.new_check_out)
    except Exception:
        raise HTTPException(status_code=400, detail="Fechas inválidas (usa YYYY-MM-DD).")

    out = modify_reserva(
        reserva_id=reserva_id,
        new_check_in=ci,
        new_check_out=co,
        new_huespedes=inp.new_huespedes,
    )
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out.get("message", "No se pudo modificar"))
    return {"ok": True, "message": f"✅ Reserva {reserva_id} modificada."}


@router.get("/export")
def admin_export(
    scope: str = Query("month", pattern="^(month|year|all|range)$"),
    estado: str = Query("all"),
    year: int = Query(date.today().year, ge=2000, le=2100),
    month: int = Query(date.today().month, ge=1, le=12),
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    _: None = Depends(require_admin),
):
    csv_bytes = export_reservas_csv(
        scope=scope, estado=estado, year=year, month=month, date_from=from_, date_to=to
    )
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="reservas_export.csv"'},
    )


# =========================
# CHAT ADMIN (LLM + chart opcional)
# =========================
class AdminChatIn(BaseModel):
    message: str
    context: dict | None = None


@router.post("/chat")
def admin_chat_endpoint(inp: AdminChatIn, _: None = Depends(require_admin)):
    return admin_chat(inp.message, context=inp.context or {})
