# api/bots_info.py
from __future__ import annotations

from typing import Dict, Any, List

from .llm_client import chat_llm
from .retriever import retrieve_chunks
from .corpus_loader import CorpusChunk
from .i18n import normalize_lang, translate_answer_if_needed


def _build_context_from_chunks(chunks: List[CorpusChunk]) -> str:
    if not chunks:
        return "No hay contexto relevante disponible."

    partes: list[str] = []
    for idx, ch in enumerate(chunks, start=1):
        header = f"[{idx}] {ch.title} — {ch.section}"
        body = ch.text.strip()
        partes.append(f"{header}\n{body}")
    return "\n\n---\n\n".join(partes)


def _translate_query_to_spanish_for_retrieval(user_message: str, lang: str) -> str:
    """
    Para que el retriever funcione bien con corpus en ES:
    - si el usuario pregunta en otro idioma, traducimos la QUERY a ES (solo para recuperar chunks).
    """
    lang = normalize_lang(lang)
    if lang == "es":
        return user_message

    system = (
        "Eres un traductor. Traduce el mensaje a español SOLO para búsqueda interna.\n"
        "REGLAS:\n"
        "- Conserva nombres propios (Apartamento Mercedes, Casa Bruna, etc.).\n"
        "- Conserva términos clave (Puy du Fou, Toledo).\n"
        "- Devuelve SOLO la traducción, sin comentarios.\n"
    )
    out = chat_llm(system_prompt=system, user_prompt=user_message, model="gpt-4o-mini", temperature=0.0, max_tokens=120)
    return (out or user_message).strip() or user_message


def info_bot_llm(user_message: str, lang: str = "es") -> Dict[str, Any]:
    """
    Info-bot (RAG + LLM).
    - Recuperación en ES (traduciendo query si hace falta)
    - Redacción en ES (backend interno)
    - La traducción al idioma final se hace en main.py (o aquí si quieres).
    """
    lang = normalize_lang(lang)

    # 1) Query para retrieval (siempre ES)
    query_es = _translate_query_to_spanish_for_retrieval(user_message, lang)

    # 2) Recuperar chunks (sube k un poco para preguntas tipo "historia")
    chunks = retrieve_chunks(query_es, k=8)

    # 3) Contexto
    contexto = _build_context_from_chunks(chunks)

    # 4) Prompt (más corto y SIN inventar)
    system_prompt = (
        "Eres AlojaBot (modo INFO), un asistente para alojamientos turísticos en Cobisa (Toledo).\n"
        "IMPORTANTE:\n"
        "- Respondes usando SOLO el contexto proporcionado.\n"
        "- Si algo no está en el contexto, dilo claramente: 'Esa información no aparece en mi ficha'.\n"
        "- NO inventes reformas, anécdotas, distancias ni normas si no están en el contexto.\n"
        "- Responde en ESPAÑOL (luego el sistema puede traducir la respuesta).\n"
        "- Sé breve: máximo 6 viñetas o 4 párrafos (ideal 120-150 palabras).\n"
        "- 1-3 emojis como mucho.\n"
    )

    user_prompt = (
        f"Pregunta del usuario:\n{user_message}\n\n"
        f"(Nota: para buscar en la base interna, la consulta equivalente en ES es: {query_es})\n\n"
        f"Contexto relevante:\n---\n{contexto}\n---\n\n"
        "Responde ahora."
    )

    answer_text = chat_llm(system_prompt=system_prompt, user_prompt=user_prompt, model="gpt-4o-mini", temperature=0.2, max_tokens=350)

    evidence: List[Dict[str, Any]] = []
    for ch in chunks:
        evidence.append(
            {
                "text": ch.text,
                "meta": {
                    "titulo": ch.title,
                    "seccion": ch.section,
                    "doc_id": ch.doc_id,
                    "tipo": ch.tipo,
                    "id_alojamiento": ch.id_alojamiento,
                },
            }
        )

    return {"answer": (answer_text or "").strip(), "evidence": evidence}
