# api/i18n.py
from __future__ import annotations

import re
from typing import Optional

from .llm_client import chat_llm


_LANG_ALIASES = {
    # English
    "english": "en", "inglés": "en", "ingles": "en", "en": "en",
    # Spanish
    "spanish": "es", "español": "es", "espanol": "es", "es": "es",
    # French
    "french": "fr", "français": "fr", "francais": "fr", "fr": "fr",
    # German
    "german": "de", "deutsch": "de", "alemán": "de", "aleman": "de", "de": "de",
    # Italian
    "italian": "it", "italiano": "it", "it": "it",
    # Portuguese
    "portuguese": "pt", "português": "pt", "portugues": "pt", "pt": "pt",
}

_EXPLICIT_LANG_RE = re.compile(
    r"""
    (?:
      \b(?:respond|answer|reply)\s+(?:in)\s+(?P<en_lang>english|spanish|french|german|italian|portuguese)\b
      |
      \b(?:resp[oó]ndeme|cont[eé]stame|habla)\s+(?:en)\s+(?P<es_lang>ingl[eé]s|espa[ñn]ol|franc[eé]s|alem[aá]n|italiano|portugu[eé]s)\b
      |
      \b(?:auf)\s+(?P<de_lang>deutsch)\b
      |
      \b(?:en)\s+(?P<fr_lang>fran[cç]ais)\b
      |
      \b(?:in)\s+(?P<it_lang>italiano)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalize_lang(lang: str | None) -> str:
    if not lang:
        return "es"
    l = (lang or "").strip().lower()
    # en-US, en_GB -> en
    if "-" in l:
        l = l.split("-", 1)[0]
    if "_" in l:
        l = l.split("_", 1)[0]
    # alias -> iso
    return _LANG_ALIASES.get(l, l if len(l) == 2 else "es")


def extract_explicit_lang(text: str) -> Optional[str]:
    if not text:
        return None
    m = _EXPLICIT_LANG_RE.search(text)
    if not m:
        return None
    for k, v in m.groupdict().items():
        if v:
            return normalize_lang(v)
    return None


def translate_answer_if_needed(text: str, target_lang: str, source_lang: str = "es") -> str:
    """
    Traduce texto (manteniendo números/€, ids/fechas/emails) si target_lang != source_lang.
    """
    if not text:
        return text

    tgt = normalize_lang(target_lang)
    src = normalize_lang(source_lang)

    if tgt == src:
        return text

    system = (
        "Eres un traductor profesional.\n"
        "Traduce el texto al idioma objetivo.\n"
        "REGLAS MUY IMPORTANTES:\n"
        "- NO cambies números, importes (€), IDs (reserva #), fechas, emails, teléfonos, DNI/NIE.\n"
        "- NO inventes información.\n"
        "- Mantén saltos de línea.\n"
        "- Devuelve SOLO la traducción (sin prefacios, sin comillas).\n"
    )
    user = f"Idioma objetivo: {tgt}\n\nTexto:\n{text}"

    out = chat_llm(system_prompt=system, user_prompt=user, model="gpt-4o-mini", temperature=0.0, max_tokens=600)
    return (out or text).strip() or text
