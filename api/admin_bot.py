# api/admin_bot.py
from __future__ import annotations

import json
import re
from datetime import date

from .llm_client import chat_llm
from .admin_nlu import parse_week_range, parse_date_range_from_text, parse_month_from_text
from .admin_actions import free_days, list_reservas, find_reserva, cancel_reserva, modify_reserva
from .admin_store import load_alojamientos_df, aloj_name_by_id
from .admin_reports import compute_metrics, compute_series

CANCEL_ID_RE = re.compile(r"\b(?:cancela|cancel|anula)\b.*\b(\d{1,6})\b", re.I)
MODIFY_ID_RE = re.compile(r"\b(?:mueve|modifica|cambia|move|change|modify|reschedule)\b.*\b(\d{1,6})\b", re.I)
FREE_RE = re.compile(r"\b(dias libres|días libres|free days|available days)\b", re.I)
LIST_WEEK_RE = re.compile(r"\b(esta semana|this week)\b", re.I)
FIND_RE = re.compile(r"\b(busca|buscar|find|search)\b.*\b(reserva|reservation|booking)\b", re.I)

CHART_RE = re.compile(r"\b(grafica|gráfica|chart|plot|graph)\b", re.I)
REVENUE_RE = re.compile(r"\b(factur\w*|revenue|ingres\w*)\b", re.I)
OCC_RE = re.compile(r"\b(ocup\w*|occup\w*)\b", re.I)
YEAR_RE = re.compile(r"\b(20\d{2})\b")

def _fmt_date(d: date) -> str:
    return d.isoformat()

def _list_accommodations() -> list[str]:
    df = load_alojamientos_df()
    if df.empty or "nombre" not in df.columns:
        return []
    return [str(x).strip() for x in df["nombre"].dropna().tolist()]

def _detect_aloj_name(text: str) -> str | None:
    t = (text or "").lower()
    for n in _list_accommodations():
        if n.lower() in t:
            return n
    return None

def _safe_json(out: str) -> dict:
    out = (out or "").strip()
    if not out:
        return {"action": "unknown", "params": {}}
    # intenta encontrar el primer JSON {...}
    m = re.search(r"\{.*\}", out, re.S)
    if m:
        out = m.group(0)
    try:
        return json.loads(out)
    except Exception:
        return {"action": "unknown", "params": {}}

def _llm_plan(text: str) -> dict:
    names = _list_accommodations()
    sys = (
        "You are an admin assistant for a rentals business.\n"
        "Return ONLY valid JSON (no markdown).\n"
        "Choose ONE action from:\n"
        "free_days, list_reservas, find_reserva, cancel, modify, metrics, series, top, unknown.\n"
        "Schema: {\"action\":\"...\",\"params\":{...}}\n"
        "Rules:\n"
        "- If user asks to plot/chart -> series {year, kind:'revenue'|'occupancy'}\n"
        "- If user asks how much revenue/facturacion for a year -> metrics {scope:'year', year}\n"
        "- If asks 'this month/este mes' -> metrics {scope:'month', year, month}\n"
        "- If asks for free days in a month -> free_days {alojamiento, month, year}\n"
        "- If asks reservations this week -> list_reservas {range:'week'}\n"
        "- If asks find reservation -> find_reserva {query:'...'}\n"
        "- If asks cancel reservation N -> cancel {id:N}\n"
        "- If asks move/modify reservation N -> modify {id:N, new_range_text:'...'}\n"
        f"- Accommodation names: {names}\n"
    )
    out = chat_llm(sys, text, temperature=0.0, max_tokens=240) or ""
    return _safe_json(out)

def admin_chat(text: str, context: dict | None = None) -> dict:
    q = (text or "").strip()
    if not q:
        return {"ok": False, "answer": "Escribe una pregunta."}

    ctx = context or {}

    # =========================
    # 1) Determinista (cero fallos)
    # =========================

    # cancel
    m = CANCEL_ID_RE.search(q)
    if m:
        rid = int(m.group(1))
        res = cancel_reserva(rid)
        if not res.get("ok"):
            return {"ok": False, "answer": f"⚠️ {res.get('message','No he podido cancelar.')}"}
        return {"ok": True, "answer": f"✅ Reserva {rid} cancelada."}

    # modify
    m = MODIFY_ID_RE.search(q)
    if m:
        rid = int(m.group(1))
        rng = parse_date_range_from_text(q)
        if not rng:
            return {"ok": False, "answer": "⚠️ No detecto el nuevo rango (ej: “10–12 de abril” o “10/04 al 12/04”)."}
        res = modify_reserva(rid, rng.start, rng.end)
        if not res.get("ok"):
            return {"ok": False, "answer": f"⚠️ {res.get('message','No he podido modificar.')}"}
        return {"ok": True, "answer": f"✅ Reserva {rid} modificada a {rng.start} → {rng.end}."}

    # reservas esta semana
    if LIST_WEEK_RE.search(q):
        rng = parse_week_range()
        res = list_reservas(rng.start, rng.end, estado=None)
        items = res.get("reservas", [])
        if not items:
            return {"ok": True, "answer": f"📭 No hay reservas esta semana ({rng.start} → {rng.end})."}
        lines = [f"📋 Reservas esta semana ({rng.start} → {rng.end}):"]
        for r in items[:30]:
            lines.append(f"- #{r['id']} · {r.get('alojamiento')} · {r.get('check_in')}→{r.get('check_out')} · {r.get('estado')}")
        return {"ok": True, "answer": "\n".join(lines)}

    # buscar reserva
    if FIND_RE.search(q):
        query = q
        m2 = re.search(r"\b(?:de|for)\b\s+(.+)$", q, re.I)
        if m2:
            query = m2.group(1).strip()
        res = find_reserva(query)
        items = res.get("reservas", [])
        if not items:
            return {"ok": True, "answer": f"🔎 No encuentro reservas para: {query}"}
        lines = [f"🔎 Reservas para: {query}"]
        for r in items[:20]:
            aid = int(r["id_alojamiento"]) if r.get("id_alojamiento") else None
            aloj = aloj_name_by_id(aid) if aid else "—"
            lines.append(f"- #{r.get('id')} · {aloj} · {r.get('check_in')}→{r.get('check_out')} · {r.get('estado')}")
        return {"ok": True, "answer": "\n".join(lines)}

    # días libres
    if FREE_RE.search(q):
        aloj = _detect_aloj_name(q)
        if not aloj:
            return {"ok": False, "answer": "⚠️ Dime el alojamiento (ej: “días libres en Casa Bruna en marzo”)."}
        y, mth = parse_month_from_text(q)
        if not mth:
            return {"ok": False, "answer": "⚠️ Dime el mes (ej: “en marzo”)."}
        year = y or date.today().year
        res = free_days(aloj, year, mth)
        if not res.get("ok"):
            return {"ok": False, "answer": f"⚠️ {res.get('message','No puedo calcular días libres.')}"}
        days = res["free_days"]
        s = ", ".join(d.strftime("%d/%m") for d in days[:60]) + (f" … (+{len(days)-60})" if len(days) > 60 else "")
        return {"ok": True, "answer": f"🗓️ Días libres en {res['alojamiento']} ({mth:02d}/{year}):\n{s}"}

    # gráfica rápida (sin LLM)
    if CHART_RE.search(q):
        y = None
        my = YEAR_RE.search(q)
        if my:
            y = int(my.group(1))
        y = y or int(ctx.get("year") or date.today().year)

        kind = "revenue"
        if OCC_RE.search(q) and not REVENUE_RE.search(q):
            kind = "occupancy"
        if REVENUE_RE.search(q):
            kind = "revenue"

        series = compute_series(year=y, kind=kind)
        return {
            "ok": True,
            "answer": f"📈 Aquí tienes la {'ocupación' if kind=='occupancy' else 'facturación'} por meses de {y}.",
            "chart": series,
        }

    # pregunta de facturación/metrics rápida (sin LLM)
    if REVENUE_RE.search(q) and ("?" in q or "cuanto" in q.lower() or "how much" in q.lower()):
        y = None
        my = YEAR_RE.search(q)
        if my:
            y = int(my.group(1))
        y = y or int(ctx.get("year") or date.today().year)

        met = compute_metrics(scope="year", year=y, month=1)
        return {
            "ok": True,
            "answer": (
                f"💶 Facturación {y}: {met['revenue']:.2f} €\n"
                f"- Reservas (check-in): {met['reservas_checkin']}\n"
                f"- ADR: {met['adr']:.2f} €\n"
                f"- RevPAR: {met['revpar']:.2f} €\n"
                f"- Top alojamiento: {met['top_alojamiento']} ({met['top_revenue']:.2f} €)"
            ),
        }

    # =========================
    # 2) Planner LLM (para frases raras)
    # =========================
    plan = _llm_plan(q)
    action = (plan.get("action") or "").strip()
    params = plan.get("params") or {}

    if action == "series":
        y = int(params.get("year") or ctx.get("year") or date.today().year)
        kind = str(params.get("kind") or "revenue").lower().strip()
        if kind not in ("revenue", "occupancy"):
            kind = "revenue"
        series = compute_series(year=y, kind=kind)
        return {"ok": True, "answer": f"📈 Serie ({kind}) {y}.", "chart": series}

    if action == "metrics":
        scope = str(params.get("scope") or "month").strip()
        if scope not in ("month", "year", "all"):
            scope = "month"
        y = int(params.get("year") or ctx.get("year") or date.today().year)
        m = int(params.get("month") or ctx.get("month") or date.today().month)
        met = compute_metrics(scope=scope, year=y, month=m)
        return {"ok": True, "answer": json.dumps(met, ensure_ascii=False, indent=2)}

    if action == "top":
        y = int(params.get("year") or ctx.get("year") or date.today().year)
        m = int(params.get("month") or ctx.get("month") or date.today().month)
        met = compute_metrics(scope="month", year=y, month=m)
        return {"ok": True, "answer": f"🏆 Top alojamiento {m:02d}/{y}: {met['top_alojamiento']} ({met['top_revenue']:.2f} €)"}

    # fallback
    return {
        "ok": True,
        "answer": "🤖 No he entendido esa petición admin todavía. Prueba: “Grafica la facturación 2026”, “¿Cuánto facturé en 2026?”, “días libres en Casa Bruna en marzo”, “cancela la 32”.",
    }
