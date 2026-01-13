# api/admin_nlu.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

MONTHS = {
    # ES
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    # EN
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

DATE_DDMM_RE = re.compile(r"\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?\b")
RANGE_MONTHNAME_RE = re.compile(
    r"\b(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*(?:de\s+)?([a-záéíóúñ]+)\s*(?:de\s+(\d{4}))?\b",
    re.I,
)
MONTHNAME_RE = re.compile(r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|"
                          r"january|february|march|april|may|june|july|august|september|october|november|december)\b", re.I)

THIS_WEEK_RE = re.compile(r"\b(esta semana|this week)\b", re.I)


@dataclass
class DateRange:
    start: date
    end: date  # end EXCLUSIVE (tipo check_out)


def _infer_year(month: int, day: int, preferred_year: int | None = None) -> int:
    today = date.today()
    y = preferred_year or today.year
    try:
        cand = date(y, month, day)
    except Exception:
        return y
    # si ya pasó, usa siguiente año
    if cand < today:
        return y + 1
    return y


def parse_week_range(today: date | None = None) -> DateRange:
    today = today or date.today()
    # lunes->domingo
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=7)
    return DateRange(start=start, end=end)


def parse_month_from_text(text: str) -> tuple[int | None, int | None]:
    """
    Devuelve (year, month) si detecta "marzo" / "march" opcionalmente con año.
    """
    t = (text or "").lower()
    m = MONTHNAME_RE.search(t)
    if not m:
        return None, None
    name = m.group(1).lower()
    month = MONTHS.get(name)
    if not month:
        return None, None

    y = None
    # intenta pillar "2026" cerca
    ymatch = re.search(r"\b(20\d{2})\b", t)
    if ymatch:
        y = int(ymatch.group(1))
    return y, month


def parse_date_range_from_text(text: str) -> DateRange | None:
    """
    Soporta:
    - 10/04 al 12/04
    - 10-12 de abril
    - from 10/04 to 12/04
    """
    t = (text or "").strip()

    # 1) rango dd/mm dd/mm (tomamos 2 fechas)
    dates = []
    for dd, mm, yy in DATE_DDMM_RE.findall(t):
        d = int(dd); m = int(mm); y = int(yy) if yy else None
        if y is not None and y < 100:
            y = 2000 + y
        if y is None:
            y = _infer_year(m, d)
        try:
            dates.append(date(y, m, d))
        except Exception:
            pass
    if len(dates) >= 2:
        start, end = dates[0], dates[1]
        if end <= start:
            return None
        return DateRange(start=start, end=end)

    # 2) "10–12 de abril"
    m = RANGE_MONTHNAME_RE.search(t)
    if m:
        d1 = int(m.group(1))
        d2 = int(m.group(2))
        mon_name = m.group(3).lower()
        mon = MONTHS.get(mon_name)
        if not mon:
            return None
        y = int(m.group(4)) if m.group(4) else _infer_year(mon, d1)
        try:
            start = date(y, mon, d1)
            end = date(y, mon, d2)
        except Exception:
            return None
        if end <= start:
            return None
        return DateRange(start=start, end=end)

    return None
