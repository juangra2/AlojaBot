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
from .admin_routes import router as admin_router

from .i18n import (
    normalize_lang,
    extract_explicit_lang,
    translate_answer_if_needed,
)

from .orchestrator_llm import orchestrate_route_and_lang


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


def localize_payload(payload: dict, lang: str) -> dict:
    """
    Backend interno ES -> traducimos aquí al idioma de sesión.
    """
    lang = normalize_lang(lang)
    if lang == "es":
        return payload

    if payload.get("answer"):
        payload["answer"] = translate_answer_if_needed(payload["answer"], lang, source_lang="es")
    if payload.get("weather"):
        payload["weather"] = translate_answer_if_needed(payload["weather"], lang, source_lang="es")
    return payload


def _append_to_answer(base: dict, extra: str) -> dict:
    extra = (extra or "").strip()
    if not extra:
        return base
    a = (base.get("answer") or "").rstrip()
    base["answer"] = (a + ("\n\n" if a else "") + extra).strip()
    return base


def _get_session_lang(session_id: str, user_text: str) -> str:
    """
    Idioma estable por sesión:
    - Si el usuario pide explícitamente un idioma -> se cambia y se bloquea.
    - Si ya hay idioma guardado y está bloqueado -> NO cambiamos aunque el texto tenga números/palabras raras.
    - Si no hay idioma aún -> lo inferimos (LLM orquestador si está disponible; si no, heuristic).
    """
    sess = SESS.get(session_id, {})
    prev = normalize_lang(sess.get("lang") or "es")
    locked = bool(sess.get("lang_locked", False))

    explicit = extract_explicit_lang(user_text)
    if explicit:
        sess["lang"] = normalize_lang(explicit)
        sess["lang_locked"] = True
        SESS[session_id] = sess
        return sess["lang"]

    # Si ya estaba bloqueado, mantenlo siempre (esto evita saltos ES<->DE por mensajes con fechas)
    if locked and sess.get("lang"):
        return prev

    # Si ya hay idioma (aunque no esté bloqueado), mantenlo salvo señal fuerte
    if sess.get("lang"):
        # señal fuerte: texto largo y con muchas letras (no solo números/fechas)
        letters = sum(ch.isalpha() for ch in user_text)
        total = max(1, len(user_text))
        alpha_ratio = letters / total
        if len(user_text) >= 35 and alpha_ratio >= 0.55:
            guess = normalize_lang(detect_lang_nlu(user_text, prev))
            # si cambia, aceptamos y bloqueamos desde aquí
            if guess != prev:
                sess["lang"] = guess
                sess["lang_locked"] = True
                SESS[session_id] = sess
                return guess

        # por defecto, mantenemos prev
        return prev

    # Primera vez: usa orquestador para detectar idioma (más fiable que heurísticas)
    try:
        orch = orchestrate_route_and_lang(user_text=user_text, session_mode=None, session_has_pending=False, session_lang=None)
        lang = normalize_lang(orch.lang)
    except Exception:
        lang = normalize_lang(detect_lang_nlu(user_text, "es"))

    sess["lang"] = lang
    sess["lang_locked"] = True
    SESS[session_id] = sess
    return lang


@app.post("/chat", response_model=ChatOut)
def chat(inp: ChatIn):
    text = inp.message.strip()
    norm_text = strip_accents(text.lower())
    session_id = inp.session_id or "default"

    sess = SESS.get(session_id, {})
    lang = _get_session_lang(session_id, text)
    sess = SESS.get(session_id, {})  # refresca por si _get_session_lang escribió
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

    # 0) Continuación meteo (si antes pedimos fechas)
    if sess.get("awaiting_weather_dates") and mode not in ("reservar", "cancelar", "modificar"):
        met = meteo_bot(slots, session_id)
        if not met.get("needs_dates"):
            sess.pop("awaiting_weather_dates", None)
            SESS[session_id] = sess
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
                SESS[session_id] = sess
        return localize_payload(base, lang)

    if mode == "cancelar":
        base = handle_cancel_with_session(session_id, text, slots)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
                SESS[session_id] = sess
        return localize_payload(base, lang)

    if mode == "modificar":
        base = handle_modificar_with_session(session_id, text, slots)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
                SESS[session_id] = sess
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
                SESS[session_id] = sess
        return localize_payload(base, lang)

    if wants_modificar_reserva:
        base = start_modificar_flow(session_id, text, slots)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
                SESS[session_id] = sess
        return localize_payload(base, lang)

    if wants_consulta:
        base = handle_consulta_reservas(slots, text)
        if wants_weather:
            met = meteo_bot(slots, session_id)
            _append_to_answer(base, met.get("weather", ""))
            base.update(met)
            if met.get("needs_dates"):
                sess["awaiting_weather_dates"] = True
                SESS[session_id] = sess
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
                SESS[session_id] = sess
        return localize_payload(base, lang)

    # 4) Búsqueda + meteo
    if wants_trans and wants_weather:
        base = sql_buscar_bot(slots)
        met = meteo_bot(slots, session_id)
        _append_to_answer(base, met.get("weather", ""))
        base.update(met)
        if met.get("needs_dates"):
            sess["awaiting_weather_dates"] = True
            SESS[session_id] = sess
        return localize_payload(base, lang)

    if wants_trans:
        return localize_payload(sql_buscar_bot(slots), lang)

    # 5) Solo meteo
    if wants_weather:
        met = meteo_bot(slots, session_id)
        out = {"answer": met.get("weather") or "⚠️ No he podido obtener el pronóstico.", **met}
        if met.get("needs_dates"):
            sess["awaiting_weather_dates"] = True
            SESS[session_id] = sess
        return localize_payload(out, lang)

    # 6) Default: info-bot (RAG+LLM) + retrieval multidioma
    out = info_bot_llm(text, lang=lang)
    return localize_payload(out, lang)


@app.get("/aloj_id")
def get_aloj_id(name: str = Query(..., min_length=1)):
    aid = aloj_id_by_name(name)
    return {"ok": bool(aid), "id": aid}


@app.get("/availability")
def get_availability(id_aloj: int, year: int, month: int):
    return month_availability(id_aloj, year, month)
