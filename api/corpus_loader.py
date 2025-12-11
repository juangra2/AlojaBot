# api/corpus_loader.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import re

# Carpeta donde has puesto los .md
BASE_DIR = Path(__file__).resolve().parent.parent
CORPUS_DIR = BASE_DIR / "data" / "corpus"


@dataclass
class CorpusDoc:
    doc_id: str
    path: Path
    title: str
    id_alojamiento: Optional[int]
    tipo: str  
    text: str


@dataclass
class CorpusChunk:
    doc_id: str
    title: str
    section: str
    text: str
    id_alojamiento: Optional[int]
    tipo: str


_DOCS_CACHE: Optional[List[CorpusDoc]] = None
_CHUNKS_CACHE: Optional[List[CorpusChunk]] = None


def _infer_tipo_from_filename(path: Path) -> str:
    """
    Heurística simple: si el fichero empieza por 'apto_' -> alojamiento,
    si no -> entorno/otro.
    """
    name = path.name.lower()
    if name.startswith("apto_"):
        return "alojamiento"
    return "entorno"


def load_raw_docs() -> List[CorpusDoc]:
    """
    Lee todos los .md de CORPUS_DIR y devuelve una lista de CorpusDoc.

    Esta función solo se llama internamente; usa get_corpus_docs() para
    obtener los documentos cacheados.
    """
    docs: List[CorpusDoc] = []

    if not CORPUS_DIR.exists():
        # No levantamos excepción para no romper el backend si aún no hay corpus.
        return []

    for path in sorted(CORPUS_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Intento de fallback
            text = path.read_text(errors="ignore")

        lines = text.splitlines()

        # Título: primera línea que empiece por '#'
        title = path.stem
        for line in lines:
            if line.strip().startswith("#"):
                title = line.lstrip("#").strip()
                break

        # id_alojamiento: buscar línea tipo 'id_alojamiento: 1'
        id_aloj = None
        for line in lines:
            m = re.search(r"id_alojamiento\s*:\s*(\d+)", line, re.IGNORECASE)
            if m:
                id_aloj = int(m.group(1))
                break

        tipo = _infer_tipo_from_filename(path)

        doc = CorpusDoc(
            doc_id=path.stem,
            path=path,
            title=title,
            id_alojamiento=id_aloj,
            tipo=tipo,
            text=text,
        )
        docs.append(doc)

    return docs


def get_corpus_docs() -> List[CorpusDoc]:
    """
    Devuelve la lista de documentos del corpus, cacheada en memoria.
    """
    global _DOCS_CACHE
    if _DOCS_CACHE is None:
        _DOCS_CACHE = load_raw_docs()
    return _DOCS_CACHE


def _split_doc_into_chunks(doc: CorpusDoc) -> List[CorpusChunk]:
    """
    Divide un documento en trozos por secciones Markdown (## Título de sección).

    - Si no hay secciones '##', se devuelve un solo chunk con todo el texto.
    - Cada chunk incluye:
      - doc_id, título global, nombre de sección, texto,
        id_alojamiento y tipo.
    """
    text = doc.text
    lines = text.splitlines()

    chunks: List[CorpusChunk] = []

    current_section_title = "General"
    current_lines: List[str] = []

    def flush_section():
        if not current_lines:
            return
        section_text = "\n".join(current_lines).strip()
        if not section_text:
            return
        chunks.append(
            CorpusChunk(
                doc_id=doc.doc_id,
                title=doc.title,
                section=current_section_title,
                text=section_text,
                id_alojamiento=doc.id_alojamiento,
                tipo=doc.tipo,
            )
        )

    for line in lines:
        # Detecta encabezados de segundo nivel: '## ...'
        if line.strip().startswith("## "):
            # Cerramos sección anterior
            flush_section()
            # Empezamos sección nueva
            current_section_title = line.strip().lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Última sección
    flush_section()

    # Si por lo que sea no salió ningún chunk, creamos uno con todo el texto
    if not chunks:
        chunks.append(
            CorpusChunk(
                doc_id=doc.doc_id,
                title=doc.title,
                section="General",
                text=text.strip(),
                id_alojamiento=doc.id_alojamiento,
                tipo=doc.tipo,
            )
        )

    return chunks


def build_corpus_chunks() -> List[CorpusChunk]:
    """
    Construye la lista completa de chunks a partir de todos los documentos.
    """
    docs = get_corpus_docs()
    chunks: List[CorpusChunk] = []
    for doc in docs:
        chunks.extend(_split_doc_into_chunks(doc))
    return chunks


def get_corpus_chunks() -> List[CorpusChunk]:
    """
    Devuelve los chunks cacheados (cada uno es un trozo de un .md con sección).
    """
    global _CHUNKS_CACHE
    if _CHUNKS_CACHE is None:
        _CHUNKS_CACHE = build_corpus_chunks()
    return _CHUNKS_CACHE
