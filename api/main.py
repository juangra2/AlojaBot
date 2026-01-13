# api/main.py
from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import re

from .domain_reservas import (
    encontrar_aloj_por_nombre,
    aloj_id_by_name,
    month_availability,
)

from .utils_nlu import (
    strip_accents,
    extract_slots,
    detect_lang as detect_lang_nlu,  
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
from .llm_client import chat_llm
from .admin_routes import router as admin_router

app = FastAPI(title="AlojaBot API (Excel + Reservas + Meteo + LLM Orquestador)")

app.include_router(admin_router, prefix="/admin", tags=["admin"])


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


# -------------------------
# Idioma: detectar + traducir
# -------------------------

def translate_text(text: str, target_lang: str) -> str:
    if not text or target_lang == "es":
        return text

    sys = (
        "You are a professional translator.\n"
        f"Translate the text to {target_lang}.\n"
        "IMPORTANT:\n"
        "- Output ONLY the translation.\n"
        "- Keep emojis, dates, numbers, prices, IDs, emails exactly.\n"
        "- Keep line breaks.\n"
        "- Do not add introductions or comments."
        "- Return ONLY the translated text, with no preface, no explanations, no quotes."
    )
    out = chat_llm(sys, text, model="gpt-4o-mini")
    return (out or text).strip()

def localize_payload(payload: dict, lang: str) -> dict:
    if lang == "es":
        return payload
    if payload.get("answer"):
        payload["answer"] = translate_text(payload["answer"], lang)
    if payload.get("weather"):
        payload["weather"] = translate_text(payload["weather"], lang)
    return payload


# -------------------------
# Helpers: meter meteo dentro de answer
# -------------------------

def _append_to_answer(base: dict, extra: str) -> dict:
    extra = (extra or "").strip()
    if not extra:
        return base
    a = (base.get("answer") or "").rstrip()
    base["answer"] = (a + ("\n\n" if a else "") + extra).strip()
    return base


@app.post("/chat", response_model=ChatOut)
def chat(inp: ChatIn):
    text = inp.message.strip()
    norm_text = strip_accents(text.lower())
    session_id = inp.session_id or "default"

    sess = SESS.get(session_id, {})
    lang = detect_lang_nlu(text, sess.get("lang"))
    sess["lang"] = lang
    SESS[session_id] = sess

    slots = extract_slots(text)

    # completar aloj_id por nombre
    if not slots.get("aloj_id"):
        aid = encontrar_aloj_por_nombre(text)
        if aid:
            slots["aloj_id"] = aid

    wants_trans = bool(TRANS_RE.search(norm_text))
    wants_weather = bool(WEATHER_RE.search(norm_text))
    wants_reserva = bool(RESERVA_RE.search(norm_text))
    wants_consulta = bool(CONSULTA_RE.search(norm_text) or MIS_RESERVAS_RE.search(norm_text))
    wants_cancel_reserva = bool(CANCEL_RESERVA_RE.search(norm_text))
    wants_modificar_reserva = bool(MODIF_RESERVA_RE.search(norm_text))

    mode = sess.get("mode")

    # 0) Continuación del meteo (cuando antes pedimos fechas)
    if sess.get("awaiting_weather_dates") and mode not in ("reservar", "cancelar", "modificar"):
        met = meteo_bot(slots, session_id)
        # si ya hemos podido dar pronóstico, limpiamos flag
        if not met.get("needs_dates"):
            sess.pop("awaiting_weather_dates", None)
        # en UI solo se ve answer, así que lo metemos ahí
        out = {"answer": met.get("weather") or "⚠️ No he podido obtener el pronóstico.", **met}
        return localize_payload(out, lang)

    # 1) Flujos multivuelta activos
    if mode == "reservar":
        base = handle_reserva_with_session(session_id, text, slots)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
        return localize_payload(base, lang)

    if mode == "cancelar":
        base = handle_cancel_with_session(session_id, text, slots)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
        return localize_payload(base, lang)

    if mode == "modificar":
        base = handle_modificar_with_session(session_id, text, slots)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
        return localize_payload(base, lang)

    # 2) Intenciones post-reserva
    if wants_cancel_reserva:
        base = start_cancel_flow(session_id, text, slots)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
        return localize_payload(base, lang)

    if wants_modificar_reserva:
        base = start_modificar_flow(session_id, text, slots)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
        return localize_payload(base, lang)

    if wants_consulta:
        base = handle_consulta_reservas(slots, text)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
        return localize_payload(base, lang)

    # 3) Crear reserva
    if wants_reserva:
        base = handle_reserva_with_session(session_id, text, slots)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
        return localize_payload(base, lang)

    # 4) Búsqueda + meteo (IMPORTANTE: unir en answer)
    if wants_trans and wants_weather:
        base = sql_buscar_bot(slots)
        met = meteo_bot(slots, session_id)
        _append_to_answer(base, met.get("weather", ""))
        base.update(met)
        if met.get("needs_dates"):
            sess["awaiting_weather_dates"] = True
        return localize_payload(base, lang)

    if wants_trans:
        return localize_payload(sql_buscar_bot(slots), lang)

    # 5) Solo meteo
    if wants_weather:
        met = meteo_bot(slots, session_id)
        out = {"answer": met.get("weather") or "⚠️ No he podido obtener el pronóstico.", **met}
        if met.get("needs_dates"):
            sess["awaiting_weather_dates"] = True
        return localize_payload(out, lang)

    # 6) Default: info-bot (RAG+LLM)
    out = info_bot_llm(text)
    return localize_payload(out, lang)


@app.get("/aloj_id")
def get_aloj_id(name: str = Query(..., min_length=1)):
    aid = aloj_id_by_name(name)
    return {"ok": bool(aid), "id": aid}


@app.get("/availability")
def get_availability(id_aloj: int, year: int, month: int):
    return month_availability(id_aloj, year, month)
