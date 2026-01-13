# api/i18n.py
from __future__ import annotations

from typing import Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def translate_answer_if_needed(text: str, target_lang: str) -> str:
    if not text:
        return text
    if not target_lang or target_lang.lower().startswith("es"):
        return text
    if OpenAI is None:
        return text

    client = OpenAI()

    system = (
        "Eres un traductor profesional.\n"
        "Traduce el texto al idioma objetivo.\n"
        "REGLAS: NO cambies números, importes €, IDs de reserva, fechas, ni nombres propios.\n"
        "Mantén saltos de línea.\n"
    )
    user = f"Idioma objetivo: {target_lang}\n\nTexto:\n{text}"

    try:
        r = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        return (r.output_text or "").strip() or text
    except Exception:
        return text
