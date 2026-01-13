# api/orchestrator_llm.py
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  

# Rutas que ya tienes en tu backend
Route = Literal["reservar", "buscar", "consultar", "cancelar", "modificar", "meteo", "info"]


class Orchestration(BaseModel):
    lang: str = Field(description="ISO 639-1 (es, en, fr, it, de, pt, ...)")
    route: Route
    confidence: float = Field(ge=0.0, le=1.0)


def orchestrate_route_and_lang(
    user_text: str,
    session_mode: Optional[str] = None,
    session_has_pending: bool = False,
) -> Orchestration:
    """
    Devuelve ruta e idioma. Si hay modo de sesión activo, NO llamamos al LLM.
    """
    # 1) Prioridad total: si estás en un flujo multivuelta, no rutees con LLM.
    if session_mode in {"reservar", "cancelar", "modificar"} and session_has_pending:
        # idioma: si estás en flujo, no cambies idioma “por sorpresa”
        return Orchestration(lang="es", route=session_mode, confidence=1.0)

    # 2) Si no hay OpenAI client, fallback
    if OpenAI is None:
        return Orchestration(lang="es", route="info", confidence=0.0)

    client = OpenAI()

    today = date.today().isoformat()
    system = (
        "Eres un ORQUESTADOR (router) para un asistente de reservas.\n"
        "Tu tarea: decidir (1) el idioma de respuesta (lang) y (2) la ruta (route).\n\n"
        "RUTAS POSIBLES:\n"
        "- reservar: crear una reserva / confirmar una reserva\n"
        "- buscar: disponibilidad, opciones, precios, 'esta libre', 'hay sitio'\n"
        "- consultar: ver una reserva por id, o 'mis reservas', o por email\n"
        "- cancelar: cancelar/anular una reserva\n"
        "- modificar: mover/cambiar fechas o huéspedes de una reserva\n"
        "- meteo: tiempo, temperatura, lluvia, viento, forecast\n"
        "- info: preguntas generales, descripción, entorno, normas, RAG\n\n"
        "REGLAS IMPORTANTES:\n"
        "- Si el usuario pide explícitamente 'respóndeme en X', usa ese idioma.\n"
        "- Si mezcla idiomas, elige el dominante.\n"
        "- Devuelve SIEMPRE un JSON que cumpla el esquema.\n"
        f"- Hoy es {today}.\n"
    )

    user = f"Mensaje del usuario:\n{user_text}"

    # Structured Outputs: recomendado frente a JSON mode cuando sea posible. :contentReference[oaicite:1]{index=1}
    # gpt-4o-mini soporta Structured Outputs y el endpoint Responses. :contentReference[oaicite:2]{index=2}
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
        # pequeño saneado
        if not out.lang:
            out.lang = "es"
        return out
    except Exception:
        return Orchestration(lang="es", route="info", confidence=0.0)
