# api/utils_nlu.py
from __future__ import annotations

from datetime import date
import re
import unicodedata

from .config import daterange  # (no se usa ahora, pero lo dejamos por compat)

def strip_accents(s: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

# =========================
# Intenciones (multi-idioma)
# =========================

WEATHER_RE = re.compile(
    r"("
    r"lluvia|llover\w*|tiempo|clima|grados|temperatura|meteo|viento|racha\w*"
    r"|weather|forecast|rain|wind|windy|temperature|meteo"
    r")",
    re.I,
)

TRANS_RE = re.compile(
    r"("
    r"reserv\w*|reserva\w*|book\w*|booking|reservation|"
    r"cancel\w*|anul\w*|"
    r"modifica\w*|cambia\w*|mueve\w*|reschedul\w*|change\w*|modify\w*|move\w*|"
    r"busc\w*|find\w*|search\w*|looking\s+for|"
    r"disponibl\w*|availability|available|free\s+(dates|days)|is\s+.*free|"
    r"est[aá]\s+libre|hay\s+alg[uú]n?\s+sitio|"
    r"quiero\s+(algo|un\s+alojamiento|una\s+casa)|"
    r"for\s+\d+\s*(guests?|people|persons?|pax)|"
    r"para\s+\d+\s*(personas|hu[eé]spedes|pax)|"
    r"check[-\s]?in|check[-\s]?out"
    r")",
    re.I,
)

# Reservar explícito (incluye inglés)
RESERVA_RE = re.compile(r"\b(reserv\w*|book\w*|booking|reservation)\b", re.I)

# Confirm / Cancel (multi-idioma)
CONFIRM_RE = re.compile(
    r"\b("
    r"s[ií]|vale|ok|okay|confirm\w*|adelante|hecho|"
    r"yes|yep|yeah|sure|go\s+ahead"
    r")\b",
    re.I,
)

CANCEL_RE = re.compile(
    r"\b("
    r"no|nope|cancel\w*|anula\w*|cancela\w*|stop|abort|never\s+mind|mejor\s+no"
    r")\b",
    re.I,
)

# =========================
# Intenciones post-reserva
# =========================

CONSULTA_RE = re.compile(
    r"("
    r"(consulta\w*|ver|ensena\w*|muestra\w*|que\s+tengo).*(reserv)"
    r"|"
    r"(show|see|list|check).*(reservation|booking)"
    r")",
    re.I,
)

MIS_RESERVAS_RE = re.compile(
    r"(\bmis\s+reservas\b|\bmy\s+reservations\b|\bmy\s+bookings\b)", re.I
)

CANCEL_RESERVA_RE = re.compile(
    r"("
    r"(cancela\w*|anula\w*).*(reserv)"
    r"|"
    r"(cancel\w*).*(reservation|booking)"
    r")",
    re.I,
)

MODIF_RESERVA_RE = re.compile(
    r"("
    r"(modifica\w*|cambia\w*|mueve\w*).*(reserv)"
    r"|"
    r"(modify|change|move|reschedule).*(reservation|booking)"
    r")",
    re.I,
)

# =========================
# DNI / NIE
# =========================
DNI_RE = re.compile(r"\b(\d{8}[A-Z])\b", re.I)
NIE_RE = re.compile(r"\b([XYZ]\d{7}[A-Z])\b", re.I)

# =========================
# Fechas
# =========================
DATE_RE = re.compile(r"\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?\b")

# ID reserva: "reserva 12", "reservation 12", "booking 12", "reserva nº 12"
RESERVA_ID_RE = re.compile(
    r"\b(?:reserva|reservation|booking)\s*(?:n[ºo.]*)?\s*(\d+)\b",
    re.I,
)

# =========================
# Precio
# =========================
PRICE_MAX_RE = re.compile(
    r"(?:menos de|hasta|m[aá]ximo|under|below|max)\s*(\d{2,4})\s*(?:€|euros)?",
    re.I,
)
PRICE_MIN_RE = re.compile(
    r"(?:m[aá]s de|al menos|m[ií]nimo|from|at least|min)\s*(\d{2,4})\s*(?:€|euros)?",
    re.I,
)
PRICE_RANGE_RE = re.compile(
    r"(?:entre|between)\s*(\d{2,4})\s*(?:€|euros)?\s*(?:y|and)\s*(\d{2,4})\s*(?:€|euros)?",
    re.I,
)

def parse_date_es(d: int, m: int, y: int | None) -> date | None:
    today = date.today()

    if y is not None:
        if y < 100:
            y = 2000 + y
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            return None

    year = today.year
    try:
        cand = date(year, int(m), int(d))
    except ValueError:
        return None

    if cand < today:
        try:
            cand = date(year + 1, int(m), int(d))
        except ValueError:
            return None

    return cand

def extract_slots(t: str) -> dict:
    """Extrae fechas, pax, precios, id de alojamiento y datos de cliente (ES/EN)."""
    text_raw = (t or "").strip()
    text = strip_accents(text_raw.lower())

    # -----------------
    # Huéspedes (multi-idioma: ES/EN/FR/DE/PT/IT)
    # -----------------
    guests = None

    # Keywords normalizados (strip_accents): "gäste" -> "gaste", "invités" -> "invites"
    GUEST_KEYWORDS = r"(?:huesped(?:es)?|invitad(?:o|os|a|as)?|persona(?:s)?|" \
                     r"guest(?:s)?|people|person(?:s)?|pax|" \
                     r"personne(?:s)?|invite(?:s)?|" \
                     r"ospit(?:e|i)|persone|" \
                     r"pessoa(?:s)?|" \
                     r"gast(?:e|en)?|gaste|gaeste|personen?)"

    patterns = [
        rf"\b(\d+)\s*{GUEST_KEYWORDS}\b",          # "4 personen", "4 invites", "4 pessoas"
        rf"\b{GUEST_KEYWORDS}\s*[:=]?\s*(\d+)\b",  # "personnes: 4"
        r"\bpara\s+(\d+)\b",
        r"\bsomos\s+(\d+)\b",
        r"\bfor\s+(\d+)\b",                        # "book ... for 4"
        r"\bwe\s+are\s+(\d+)\b",
        r"\bwir\s+sind\s+(\d+)\b",                 # DE
        r"\bnous\s+sommes\s+(\d+)\b",              # FR
        r"\bsomos\s+(\d+)\b",                      # PT/ES
        r"\bsiamo\s+(\d+)\b",                      # IT
    ]

    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            # Algunos patrones usan group(1) o group(2)
            val = None
            if m.lastindex:
                # si hay 2 grupos, usa el que no sea None
                if m.lastindex >= 2:
                    val = m.group(1) or m.group(2)
                else:
                    val = m.group(1)
            if val and str(val).isdigit():
                guests = int(val)
                break

    # Si el mensaje es SOLO un número (típico: "4")
    if guests is None:
        only = text.replace(" ", "")
        if only.isdigit():
            n = int(only)
            # limite razonable para no confundir con ID reserva
            if 1 <= n <= 12:
                guests = n


    # -----------------
    # Fechas (dd/mm[/aaaa] o dd-mm)
    # -----------------
    matches = DATE_RE.findall(t)
    parsed: list[date] = []
    for dd, mm, yy in matches:
        y = int(yy) if yy else None
        d = parse_date_es(int(dd), int(mm), y)
        if d:
            parsed.append(d)

    check_in, check_out = (parsed[0], parsed[1]) if len(parsed) >= 2 else (None, None)

    # -----------------
    # Precio
    # -----------------
    price_min = price_max = None
    r = PRICE_RANGE_RE.search(text)
    if r:
        lo, hi = int(r.group(1)), int(r.group(2))
        price_min, price_max = min(lo, hi), max(lo, hi)
    else:
        mmax = PRICE_MAX_RE.search(text)
        mmin = PRICE_MIN_RE.search(text)
        if mmax:
            price_max = int(mmax.group(1))
        if mmin:
            price_min = int(mmin.group(1))

    if ("barato" in text or "económ" in text) and price_max is None:
        price_max = 100

    # -----------------
    # Alojamiento id (opcional)
    # -----------------
    aloj_id = None
    m_id = re.search(r"(?:id\s*|alojamiento\s*#?\s*)(\d{1,4})", text)
    if m_id:
        aloj_id = int(m_id.group(1))

    # -----------------
    # Datos cliente: email / tel / dni-nie / nombre
    # -----------------
    m_email = re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", t, re.I)
    cliente_email = m_email.group(0) if m_email else None

    m_tel = re.search(r"(?<![\w+])(\+?\d[\d\s\-().]{7,}\d)\b", t)
    if m_tel:
        raw_tel = m_tel.group(1).strip()
        # conserva '+' si venía, elimina separadores
        has_plus = raw_tel.startswith("+")
        digits = re.sub(r"\D+", "", raw_tel)
        cliente_tel = ("+" + digits) if (has_plus and digits) else (digits if digits else None)
    else:
        cliente_tel = None

    cliente_dni = None
    # Probamos primero sobre el texto original (conserva los límites de palabra
    # de frases como "mi DNI es 20202020M"); si no hay match, probamos sin
    # espacios/guiones (para DNI escrito como "12345678 Z" o "X1234567-L").
    for raw in (t.upper(), t.upper().replace(" ", "").replace("-", "")):
        m_nie = NIE_RE.search(raw)
        m_dni = DNI_RE.search(raw)
        if m_nie:
            cliente_dni = m_nie.group(1).upper()
            break
        elif m_dni:
            cliente_dni = m_dni.group(1).upper()
            break

    cliente_nombre = None

    # 1) "a nombre de Juan", "soy Juan", "my name is Juan", "i'm Juan"
    m_nombre = re.search(
        r"(?:a nombre de|soy|somos|mi nombre es|my name is|i am|i'm|this is)\s+([a-záéíóúüñ][a-záéíóúüñ\s'.-]{2,})",
        t,
        re.I,
    )
    if m_nombre:
        cliente_nombre = m_nombre.group(1).strip()

    # 2) Nombre antes del email
    if not cliente_nombre and m_email:
        before_email = t[: m_email.start()]
        segments = [seg.strip(" ;:-") for seg in before_email.split(",")]
        last_segment = ""
        for seg in reversed(segments):
            if seg:
                last_segment = seg
                break
        if last_segment and re.fullmatch(
            r"[a-záéíóúüñ][a-záéíóúüñ\s'.-]{2,}",
            last_segment,
            re.I,
        ):
            cliente_nombre = last_segment

    # 3) "nombre: Juan"
    if not cliente_nombre:
        m_nom_tag = re.search(
            r"^nombre\s*:\s*([a-záéíóúüñ][a-záéíóúüñ\s'.-]{2,})$",
            t.strip(),
            re.I,
        )
        if m_nom_tag:
            cliente_nombre = m_nom_tag.group(1).strip()

    # 4) Mensaje corto que parece solo un nombre
    if not cliente_nombre:
        solo = t.strip()
        words = solo.split()
        if 1 <= len(words) <= 4:
            blocked_first = {
                "quiero","busco","hola","buenos","buenas","necesito","me","que","q",
                "reservar","reserva","book","booking","reservation","cancel","modify","change",
            }
            first_norm = strip_accents(words[0].lower())
            if first_norm not in blocked_first:
                if all(re.fullmatch(r"[a-záéíóúüñ'.-]+", w, re.I) for w in words):
                    cliente_nombre = solo

    return {
        "huespedes": guests,
        "check_in": check_in,
        "check_out": check_out,
        "price_min": price_min,
        "price_max": price_max,
        "aloj_id": aloj_id,
        "cliente_nombre": cliente_nombre,
        "cliente_email": cliente_email,
        "cliente_tel": cliente_tel,
        "cliente_dni": cliente_dni,
        "raw_text": text,
    }

# =========================
# Idioma (detección ligera + persistencia)
# =========================

LANG_FORCE_EN_RE = re.compile(r"\b(in\s+english|english\s+please|en\s+ingles)\b", re.I)
LANG_FORCE_ES_RE = re.compile(r"\b(en\s+espanol|en\s+español|castellano|in\s+spanish)\b", re.I)

_EN_HINTS = {
    "book", "booking", "reservation", "cancel", "change", "modify", "move", "reschedule",
    "from", "to", "for", "guests", "people", "please", "confirm", "yes", "no",
    "checkin", "checkout", "available", "availability", "weather", "forecast",
}

_ES_HINTS = {
    "reserva", "reservar", "cancelar", "cancela", "anular", "anula", "modificar", "modifica",
    "cambiar", "cambia", "mover", "mueve", "del", "al", "para", "huespedes", "huéspedes",
    "disponible", "disponibilidad", "tiempo", "clima", "lluvia", "pronostico", "pronóstico",
    "confirmar", "confirmo", "si", "sí", "no", "vale", "ok",
}

def detect_lang(user_text: str, prev_lang: str | None = None) -> str:
    """
    Detecta 'en' o 'es' con heurística simple.
    IMPORTANTÍSIMO: si el mensaje no tiene "señal lingüística" (solo email/teléfono/dni/números),
    mantiene el idioma anterior para evitar que el flujo cambie de idioma.
    """
    prev = prev_lang or "es"
    t = (user_text or "").strip()
    if not t:
        return prev

    norm = strip_accents(t.lower())

    # Forzado explícito
    if LANG_FORCE_EN_RE.search(norm):
        return "en"
    if LANG_FORCE_ES_RE.search(norm):
        return "es"

    # Si es un mensaje "de datos" (email/teléfono/dni/fechas/números), mantenemos el idioma anterior
    # Quitamos emails, teléfonos, DNI/NIE, fechas y números, y miramos si queda algo "de palabras"
    scrubbed = norm
    scrubbed = re.sub(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", " ", scrubbed, flags=re.I)
    scrubbed = re.sub(r"\b\+?\d[\d\s\-]{7,}\d\b", " ", scrubbed)       # teléfono
    scrubbed = re.sub(r"\b\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?\b", " ", scrubbed)  # fechas
    scrubbed = re.sub(r"\b(\d{8}[a-z])\b", " ", scrubbed, flags=re.I) # DNI
    scrubbed = re.sub(r"\b([xyz]\d{7}[a-z])\b", " ", scrubbed, flags=re.I) # NIE
    scrubbed = re.sub(r"[\d,;:+\-./()]+", " ", scrubbed)

    words = re.findall(r"[a-záéíóúüñ]+", scrubbed, flags=re.I)
    # Si apenas hay palabras reales -> no recalcular idioma
    if len(words) < 2:
        return prev

    en_score = sum(1 for w in words if w in _EN_HINTS)
    es_score = sum(1 for w in words if w in _ES_HINTS)

    if en_score > es_score:
        return "en"
    if es_score > en_score:
        return "es"

    # Empate / dudoso -> mantenemos el anterior
    return prev
