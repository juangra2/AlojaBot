# api/utils_nlu.py
from __future__ import annotations

from datetime import date
import re
import unicodedata

from .config import daterange  # por si se quiere usar aquí en el futuro


def strip_accents(s: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


# --- Patrones de intención (sobre texto sin acentos) ---
WEATHER_RE = re.compile(
    r"(lluvia|llover\w*|tiempo|clima|grados|temperatura|meteo)", re.I
)
TRANS_RE = re.compile(
    r"("
    r"reserv\w*"                       # reservar, reserva...
    r"|confirm\w*"                     # confirmar...
    r"|cancel\w*"                      # cancelar...
    r"|busc\w*"                        # busca, buscando...
    r"|disponibl\w*"                   # disponibilidad, disponible...
    r"|est[aá]\s+libre"                # está libre
    r"|hay\s+alg[uú]n?\s+sitio"        # hay algún sitio
    r"|quiero\s+(algo|un\s+alojamiento|una\s+casa)"  # quiero algo / un alojamiento...
    r"|para\s+\d+\s*(personas|hu[eé]spedes|pax)"     # para 4 personas...
    r")",
    re.I,
)
RESERVA_RE = re.compile(r"\breserv\w*|\bbook\w*", re.I)
CONFIRM_RE = re.compile(r"\b(s[ií]|ok|vale|confirm\w*|adelante|hecho)\b", re.I)
CANCEL_RE = re.compile(r"\b(no|cancela\w*|anula\w*|mejor no)\b", re.I)

# Intenciones post-reserva
CONSULTA_RE = re.compile(r"(consulta\w*|ver|ensena\w*|muestra\w*|que tengo).*(reserv)", re.I)
MIS_RESERVAS_RE = re.compile(r"\bmis\s+reservas\b", re.I)
CANCEL_RESERVA_RE = re.compile(r"(cancela\w*|anula\w*).*(reserv)", re.I)
MODIF_RESERVA_RE = re.compile(r"(modifica\w*|cambia\w*|mueve\w*).*(reserv)", re.I)

# Extraer ID de reserva tipo "reserva 12", "reserva nº 12"
RESERVA_ID_RE = re.compile(r"reserva\s*(?:n[ºo.]*)?\s*(\d+)", re.I)


# --- Slots numéricos (precio) ---
PRICE_MAX_RE = re.compile(
    r"(?:menos de|hasta|m[aá]ximo)\s*(\d{2,4})\s*(?:€|euros)?", re.I
)
PRICE_MIN_RE = re.compile(
    r"(?:m[aá]s de|al menos|m[ií]nimo)\s*(\d{2,4})\s*(?:€|euros)?", re.I
)
PRICE_RANGE_RE = re.compile(
    r"(?:entre)\s*(\d{2,4})\s*(?:€|euros)?\s*y\s*(\d{2,4})\s*(?:€|euros)?", re.I
)


def extract_slots(t: str) -> dict:
    """Extrae fechas, pax, precios, id de alojamiento y datos de cliente."""
    text = t.lower()

    # --- Huéspedes ---
    guests = None
    g1 = re.search(r"\b(\d+)\s*(personas|hu[eé]spedes|pax)\b", text)
    g2 = re.search(r"\bpara\s+(\d+)\b", text)
    g3 = re.search(r"\bsomos\s+(\d+)\b", text)
    for g in (g1, g2, g3):
        if g:
            guests = int(g.group(1))
            break

    # --- Fechas (dd/mm[/aaaa] o dd-mm) ---
    f = re.findall(r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)", t)

    def parse(d):
        try:
            p = d.replace("-", "/").split("/")
            dd, mm = int(p[0]), int(p[1])
            yy = date.today().year
            if len(p) == 3:
                yy = int(p[2]) if int(p[2]) > 31 else 2000 + int(p[2])
            return date(yy, mm, dd)
        except Exception:
            return None

    parsed = list(filter(None, map(parse, f)))
    check_in, check_out = (
        (parsed[0], parsed[1]) if len(parsed) >= 2 else (None, None)
    )

    # --- Precio ---
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

    # --- Alojamiento id (opcional) ---
    aloj_id = None
    m_id = re.search(r"(?:id\s*|alojamiento\s*#?\s*)(\d{1,4})", text)
    if m_id:
        aloj_id = int(m_id.group(1))

    # --- Datos de cliente (email, teléfono, nombre) ---
    m_email = re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", t, re.I)
    cliente_email = m_email.group(0) if m_email else None

    m_tel = re.search(r"\b(\+?\d[\d\s\-]{7,}\d)\b", t)
    cliente_tel = re.sub(r"\s+", "", m_tel.group(1)) if m_tel else None

    cliente_nombre = None

    # 1) "a nombre de Juan", "soy Juan"
    m_nombre = re.search(
        r"(?:a nombre de|soy|somos)\s+([a-záéíóúüñ][a-záéíóúüñ\s'.-]{2,})",
        t,
        re.I,
    )
    if m_nombre:
        cliente_nombre = m_nombre.group(1).strip()

    # 2) Nombre antes del email: "... , Juan Grau, juan@mail.com"
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

    # 4) Mensaje que es solo un nombre corto: "Juan", "Juan Grau"
    if not cliente_nombre:
        solo = t.strip()
        words = solo.split()
        if 1 <= len(words) <= 4:
            blocked_first = {
                "quiero",
                "busco",
                "hola",
                "buenos",
                "buenas",
                "necesito",
                "me",
                "que",
                "q",
                "reservar",
                "reserva",
            }
            first_norm = strip_accents(words[0].lower())
            if first_norm not in blocked_first:
                if all(
                    re.fullmatch(r"[a-záéíóúüñ'.-]+", w, re.I) for w in words
                ):
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
        "raw_text": text,
    }
