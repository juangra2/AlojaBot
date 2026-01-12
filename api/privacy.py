# api/privacy.py
from __future__ import annotations
import re
import math
from typing import Any

def mask_email(email: str | None) -> str:
    if not email:
        return ""
    email = email.strip()
    if "@" not in email:
        return "***"
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        user_mask = user[:1] + "***"
    else:
        user_mask = user[:2] + "***"
    # dominio: mostramos solo el TLD y parte mínima
    parts = domain.split(".")
    if len(parts) >= 2:
        dom_main = parts[0]
        tld = parts[-1]
        dom_mask = (dom_main[:1] + "***") if dom_main else "***"
        domain_mask = dom_mask + "." + tld
    else:
        domain_mask = "***"
    return f"{user_mask}@{domain_mask}"

def mask_phone(phone: Any) -> str | None:

    if phone is None:
        return None

    # pandas NaN -> float
    if isinstance(phone, float) and math.isnan(phone):
        return None

    s = str(phone).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None

    digits = re.sub(r"\D+", "", s)
    if len(digits) < 6:
        return digits or None

    return digits[:2] + ("*" * (len(digits) - 4)) + digits[-2:]

def mask_dni(dni: str | None) -> str:
    if not dni:
        return ""
    dni = re.sub(r"\s+", "", dni).upper()
    if len(dni) <= 3:
        return "***"
    # muestra 2 primeros + *** + último
    return f"{dni[:2]}***{dni[-1]}"
