# api/bots_meteo.py
from __future__ import annotations

from typing import Dict

from .weather_client import get_forecast_summary_for_range
from .session_flows import SESS


def meteo_bot(slots: Dict, session_id: str | None = None) -> Dict:
    """
    Devuelve un dict con 'weather'.
    Si no se dan fechas explícitas, intenta usar el último rango de la sesión.
    """
    cin = slots.get("check_in")
    cout = slots.get("check_out")
    aloj_id = slots.get("aloj_id")

    # Si no hay fechas en este mensaje, intentar recuperar de la sesión
    if (cin is None or cout is None) and session_id:
        sess = SESS.get(session_id, {})
        last = sess.get("last_range") or {}
        cin = cin or last.get("check_in")
        cout = cout or last.get("check_out")
        aloj_id = aloj_id or last.get("aloj_id")

    if not (cin and cout):
        return {"weather": "🌤️ Dime las fechas de entrada y salida para mirar el pronóstico.", "needs_dates": True}

    summary = get_forecast_summary_for_range(cin, cout, aloj_id=aloj_id)
    return {"weather": summary, "needs_dates": False}
