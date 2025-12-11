# api/bots_info.py
from __future__ import annotations

from typing import Dict, Any, List

from .llm_client import chat_llm
from .retriever import retrieve_chunks
from .corpus_loader import CorpusChunk


def _build_context_from_chunks(chunks: List[CorpusChunk]) -> str:
    """
    Construye un bloque de contexto legible para el LLM
    a partir de los chunks seleccionados.
    """
    if not chunks:
        return "No hay contexto relevante disponible."

    partes: list[str] = []
    for idx, ch in enumerate(chunks, start=1):
        header = f"[{idx}] {ch.title} — {ch.section}"
        body = ch.text.strip()
        partes.append(f"{header}\n{body}")
    return "\n\n---\n\n".join(partes)


def info_bot_llm(user_message: str) -> Dict[str, Any]:
    """
    Info-bot real usando:
    - RAG sencillo sobre el corpus (.md)
    - GPT-4o mini para redactar la respuesta

    Devuelve un dict compatible con ChatOut:
      - answer: texto respuesta
      - evidence: lista de trozos utilizados
    """
    # 1) Recuperar trozos relevantes del corpus
    chunks = retrieve_chunks(user_message, k=6)

    # 2) Construir contexto para el LLM
    contexto = _build_context_from_chunks(chunks)

    system_prompt = (
        "Eres AlojaBot, un asistente para alojamientos turísticos en Cobisa (Toledo) "
        "y su entorno.\n\n"
        "TU COMPORTAMIENTO:\n"
        "- Respondes SIEMPRE en español, de forma clara, cercana y educada.\n"
        "- Hablas de tú al usuario, como un anfitrión/recepcionista amable.\n"
        "- NO empieces siempre con 'Hola'. Usa un saludo solo si parece el primer "
        "mensaje de la conversación o si el usuario te saluda explícitamente.\n"
        "- Puedes usar EMOJIS, pero con moderación: entre 1 y 3 por respuesta, "
        "colocados en frases clave (inicio o final). No abuses ni pongas uno en cada palabra.\n"
        "- SOLO puedes usar la información que aparece en el contexto que te doy.\n"
        "- Si el usuario pregunta algo que NO aparece en el contexto, debes decirlo "
        "explícitamente (por ejemplo: 'esa información no la tengo en mi ficha') y, si encaja, "
        "ofrecer que la persona pregunte algo más concreto.\n"
        "- No inventes precios, disponibilidad, ni crees reservas. Eso lo gestiona "
        "otro módulo del sistema.\n"
        "- Puedes mencionar los nombres de los apartamentos (Mercedes, Arcos, Bruna, "
        "Calera) y hablar de sus características, normas, equipamiento, etc., "
        "siempre basándote en el contexto.\n"
        "- Si te preguntan por qué hacer en Cobisa/Toledo o por Puy du Fou, usa "
        "la información del contexto sobre entorno, restaurantes y planes.\n"
        "- Organiza la respuesta en 1–3 párrafos cortos o una lista de puntos clara. "
        "Evita respuestas muy largas."
    )


    user_prompt = (
        f"Pregunta del usuario:\n"
        f"{user_message}\n\n"
        f"Contexto relevante (no inventes nada que no aparezca aquí):\n"
        f"---\n"
        f"{contexto}\n"
        f"---\n\n"
        f"Instrucciones específicas para esta respuesta:\n"
        f"- Responde con un tono cercano y amable, como si atendieras en recepción.\n"
        f"- Usa entre 1 y 3 emojis que encajen con el contenido (por ejemplo, 🏡, 🌿, 🚗, 🍽️, 😊). "
        f"No uses más de 3.\n"
        f"- Si el contexto habla de un apartamento concreto, puedes recomendarlo "
        f"explicando por qué encaja.\n"
        f"- Si el usuario mezcla varias cosas (por ejemplo, alojamiento + planes "
        f"en la zona), responde en un solo mensaje organizado.\n"
        f"- No des información meteorológica aquí; solo describe alojamientos "
        f"y entorno. El tiempo lo gestiona otro módulo."
    )

    # 3) Llamar al LLM
    answer_text = chat_llm(system_prompt=system_prompt, user_prompt=user_prompt)

    # 4) Preparar evidencia para el panel derecho
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

    return {
        "answer": answer_text,
        "evidence": evidence,
    }
