# api/main.py
from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .domain_reservas import encontrar_aloj_por_nombre, aloj_id_by_name, month_availability

from .utils_nlu import (
    strip_accents,
    extract_slots,
    WEATHER_RE,
    TRANS_RE,
    RESERVA_RE,
    CONSULTA_RE,
    MIS_RESERVAS_RE,
    CANCEL_RESERVA_RE,
    MODIF_RESERVA_RE,
)
from .session_flows import (
    SESS,
    handle_reserva_with_session,
    start_cancel_flow,
    handle_cancel_with_session,
    start_modificar_flow,
    handle_modificar_with_session,
    handle_consulta_reservas,
)

from .bots_info import info_bot_llm
from .bots_sql import sql_buscar_bot
from .bots_meteo import meteo_bot

app = FastAPI(
    title="AlojaBot API (Excel + Reservas + Cliente + Sesión + Meteo)"
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


class ChatOut(BaseModel):
    answer: str | None = None
    evidence: list | None = None
    candidatos: list | None = None
    weather: str | None = None


@app.post("/chat", response_model=ChatOut)
def chat(inp: ChatIn):
    text = inp.message.strip()
    norm_text = strip_accents(text.lower())
    session_id = inp.session_id or "default"
    slots = extract_slots(text)

    if not slots.get("aloj_id"):
        aid = encontrar_aloj_por_nombre(text)
        if aid:
            slots["aloj_id"] = aid

    wants_trans = bool(TRANS_RE.search(norm_text))
    wants_weather = bool(WEATHER_RE.search(norm_text))
    wants_reserva = bool(RESERVA_RE.search(norm_text))
    wants_consulta = bool(
        CONSULTA_RE.search(norm_text) or MIS_RESERVAS_RE.search(norm_text)
    )
    wants_cancel_reserva = bool(CANCEL_RESERVA_RE.search(norm_text))
    wants_modificar_reserva = bool(MODIF_RESERVA_RE.search(norm_text))

    sess = SESS.get(session_id, {})
    mode = sess.get("mode")

    # 1) Flujos multivuelta activos
    if mode == "reservar":
        base = handle_reserva_with_session(session_id, text, slots)
        if wants_weather:
            base.update(meteo_bot(slots, session_id))
        return base

    if mode == "cancelar":
        base = handle_cancel_with_session(session_id, text, slots)
        if wants_weather:
            base.update(meteo_bot(slots, session_id))
        return base

    if mode == "modificar":
        base = handle_modificar_with_session(session_id, text, slots)
        if wants_weather:
            base.update(meteo_bot(slots, session_id))
        return base

    # 2) Intenciones post-reserva
    if wants_cancel_reserva:
        base = start_cancel_flow(session_id, text, slots)
        if wants_weather:
            base.update(meteo_bot(slots, session_id))
        return base

    if wants_modificar_reserva:
        base = start_modificar_flow(session_id, text, slots)
        if wants_weather:
            base.update(meteo_bot(slots, session_id))
        return base

    if wants_consulta:
        base = handle_consulta_reservas(slots, text)
        if wants_weather:
            base.update(meteo_bot(slots, session_id))
        return base

    # 3) Flujo de creación de reserva
    if wants_reserva:
        base = handle_reserva_with_session(session_id, text, slots)
        if wants_weather:
            base.update(meteo_bot(slots, session_id))
        return base

    # 4) Búsqueda transaccional + meteo
    if wants_trans and wants_weather:
        base = sql_buscar_bot(slots)
        base.update(meteo_bot(slots, session_id))
        return base

    if wants_trans:
        return sql_buscar_bot(slots)

    # 5) Solo meteo
    if wants_weather:
        r = meteo_bot(slots, session_id)
        # El propio texto del pronóstico va como answer
        return {
            "answer": r.get("weather")
            or "⚠️ No he podido obtener el pronóstico.",
            **r,
        }

    # 6) Por defecto, bot informativo (RAG + LLM sobre el corpus)
    return info_bot_llm(text)

@app.get("/aloj_id")
def get_aloj_id(name: str = Query(..., min_length=1)):
    aid = aloj_id_by_name(name)
    return {"ok": bool(aid), "id": aid}

@app.get("/availability")
def get_availability(
    id_aloj: int,
    year: int,
    month: int,
):
    return month_availability(id_aloj, year, month)

