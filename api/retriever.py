# api/retriever.py
from __future__ import annotations

from typing import List
import unicodedata
import re

from .corpus_loader import get_corpus_chunks, CorpusChunk


# Stopwords muy sencillas para español (para que el score no se contamine)
SPANISH_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "y", "o", "u", "en", "por", "para", "con",
    "que", "qué", "como", "cómo", "es", "son", "ser",
    "a", "al", "lo", "su", "sus", "mi", "mis", "tu", "tus",
    "me", "te", "se", "le", "les", "nos", "os",
    "donde", "dónde", "cuando", "cuándo",
    "hay", "haber",
}


def _strip_accents(s: str) -> str:
    """Normaliza texto: sin acentos, en minúsculas."""
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn").lower()


def _tokenize(text: str) -> list[str]:
    norm = _strip_accents(text)
    # Dejamos solo letras/números y espacios
    norm = re.sub(r"[^a-z0-9áéíóúüñ\s]", " ", norm)
    tokens = [t for t in norm.split() if t and t not in SPANISH_STOPWORDS]
    return tokens


def _score_chunk(query_tokens: list[str], chunk: CorpusChunk) -> float:
    """
    Asigna un score muy simple a un chunk:
    - +1 por cada aparición de un token en el texto.
    - +2 extra si el token aparece en el título o en el nombre de sección.
    - Pequeño bonus si el chunk es de tipo 'alojamiento' cuando la query menciona 'apartamento'.
    """
    if not query_tokens:
        return 0.0

    text_norm = _strip_accents(chunk.text)
    title_norm = _strip_accents(chunk.title)
    section_norm = _strip_accents(chunk.section)

    score = 0.0

    for tok in query_tokens:
        if not tok:
            continue
        # En texto
        score += text_norm.count(tok)
        # En título / sección
        if tok in title_norm:
            score += 2.0
        if tok in section_norm:
            score += 1.5

    # Bonus si la query probablemente habla de un alojamiento
    if "apartamento" in query_tokens or "casa" in query_tokens:
        if chunk.tipo == "alojamiento":
            score += 2.0

    return score


def retrieve_chunks(query: str, k: int = 5) -> List[CorpusChunk]:
    """
    Devuelve los k chunks más relevantes para la query.

    Estrategia:
    - Tokenizamos la query.
    - Score muy simple por coincidencias.
    - Ordenamos chunks por score descendente.
    - Si todos los scores son 0, devolvemos una lista vacía.
    """
    all_chunks = get_corpus_chunks()
    if not all_chunks or not query.strip():
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored: list[tuple[float, CorpusChunk]] = []
    for ch in all_chunks:
        s = _score_chunk(query_tokens, ch)
        if s > 0:
            scored.append((s, ch))

    if not scored:
        # No hay ningún chunk con score > 0: devolvemos vacío
        return []

    # Ordenar por score descendente
    scored.sort(key=lambda x: x[0], reverse=True)

    # Nos quedamos con los k mejores
    top_chunks = [ch for _, ch in scored[:k]]
    return top_chunks
