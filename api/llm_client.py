# api/llm_client.py
from __future__ import annotations

from typing import Optional

from openai import OpenAI
from .config_llm import OPENAI_API_KEY, LLM_MODEL

# Cliente global reutilizable
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY no está definida. "
                "Configúrala antes de usar el LLM."
            )
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def chat_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 600,
) -> str:
    """
    Envía un mensaje al modelo configurado y devuelve SOLO el texto de respuesta.

    - system_prompt: instrucciones de rol (quién eres, qué puedes hacer).
    - user_prompt: mensaje del usuario + contexto (por ejemplo, trozos del corpus).
    """
    client = _get_client()

    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        # Aquí NO reventamos la API; devolvemos un texto que el usuario pueda entender.
        return (
            "⚠️ Ahora mismo no puedo consultar la información con el modelo de lenguaje.\n"
            "Inténtalo de nuevo en unos minutos.\n"
            f"(Detalle técnico interno: {type(e).__name__})"
        )

    # Extraemos el texto de la primera respuesta
    if not resp.choices:
        return "⚠️ No he recibido respuesta del modelo en esta ocasión."

    content = resp.choices[0].message.content
    return content or "⚠️ La respuesta del modelo ha llegado vacía."
