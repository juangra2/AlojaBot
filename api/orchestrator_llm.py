# api/orchestrator_llm.py
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .i18n import normalize_lang

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

Route = Literal["reservar", "buscar", "consultar", "cancelar", "modificar", "meteo", "info"]


class Orchestration(BaseModel):
    lang: str = Field(description="ISO 639-1 (es, en, fr, it, de, pt, ...)")
    route: Route
    confidence: float = Field(ge=0.0, le=1.0)


def orchestrate_route_and_lang(
    user_text: str,
    session_mode: Optional[str] = None,
    session_has_pending: bool = False,
    session_lang: Optional[str] = None,
) -> Orchestration:
    # Si hay flujo activo, NO rutees con LLM y NO cambies idioma
    if session_mode in {"reservar", "cancelar", "modificar"} and session_has_pending:
        lang = normalize_lang(session_lang or "es")
        return Orchestration(lang=lang, route=session_mode, confidence=1.0)

    if OpenAI is None:
        return Orchestration(lang=normalize_lang(session_lang or "es"), route="info", confidence=0.0)

    client = OpenAI()
    today = date.today().isoformat()
    system = (
        "Eres un ORQUESTADOR (router) para un asistente de reservas.\n"
        "Decide (1) idioma (lang) y (2) ruta (route).\n\n"
        "RUTAS: reservar, buscar, consultar, cancelar, modificar, meteo, info.\n\n"
        "REGLAS:\n"
        "- Si el usuario pide explícitamente 'respóndeme en X', usa ese idioma.\n"
        "- Si mezcla idiomas, elige el dominante.\n"
        "- Devuelve SIEMPRE un JSON válido con el esquema.\n"
        f"- Hoy es {today}.\n"
    )
    user = f"Mensaje del usuario:\n{user_text}"

    try:
        resp = client.responses.parse(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=Orchestration,
        )
        out: Orchestration = resp.output_parsed
        out.lang = normalize_lang(out.lang)
        return out
    except Exception:
        return Orchestration(lang=normalize_lang(session_lang or "es"), route="info", confidence=0.0)
