# api/pricing.py
from __future__ import annotations
from datetime import date

def dynamic_discount_pct(check_in: date, today: date | None = None) -> float:
    """
    Descuento por cercanía:
    - A >=10 días vista: 0%
    - A 0..9 días: sube linealmente hasta 30%
    Ajusta números a tu gusto.
    """
    today = today or date.today()
    days = (check_in - today).days
    if days >= 10:
        return 0.0
    if days < 0:
        return 0.0
    # 9 días -> ~3%, 0 días -> 30%
    max_disc = 0.30
    return round(max_disc * (10 - days) / 10, 4)

def apply_discount(price: float, pct: float) -> float:
    pct = max(0.0, min(pct, 0.90))
    return round(price * (1.0 - pct), 2)
