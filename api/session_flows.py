# api/session_flows.py
from __future__ import annotations

from typing import Dict
from datetime import date, timedelta

import pandas as pd

from .domain_reservas import (
    hay_disponibilidad,
    capacidad_de,
    nombre_de,
    precio_noche_de,
    crear_reserva_excel,
    get_reserva_by_id,
    format_reserva_row,
    cancelar_reserva_excel,
    modificar_reserva_excel,
    list_reservas_by_email,
)
from .utils_nlu import (
    strip_accents,
    CONFIRM_RE,
    CANCEL_RE,
    RESERVA_ID_RE,
)
from .domain_reservas import encontrar_aloj_por_nombre
from .pricing import dynamic_discount_pct, apply_discount


# --- Memoria de sesión (en RAM) ---
SESS: dict[str, dict] = {}

# Campos obligatorios para crear reserva
REQ_FIELDS = [
    "aloj_id",
    "check_in",
    "check_out",
    "huespedes",
    "cliente_nombre",
    "cliente_email",
    "cliente_tel",
    "cliente_dni",
]


def _reset_session_mode(session_id: str) -> None:
    """Limpia modo/pendientes pero conserva cosas como last_range."""
    sess = SESS.setdefault(session_id, {})
    for key in (
        "mode",
        "pending",
        "awaiting_confirm",
        "pending_cancel",
        "pending_modify",
    ):
        sess.pop(key, None)


def resolve_aloj_if_needed(p: dict):
    if not p.get("aloj_id"):
        aid = encontrar_aloj_por_nombre(p.get("raw_text", ""))
        if aid:
            p["aloj_id"] = aid


def merge_slots(pending: dict, new: dict) -> dict:
    out = dict(pending or {})
    for k, v in new.items():
        if v is None:
            continue
        out[k] = v
    resolve_aloj_if_needed(out)
    return out


def missing_fields(p: dict) -> list[str]:
    return [k for k in REQ_FIELDS if not p.get(k)]


def summarize(p: dict) -> str:
    aloj_id = p["aloj_id"]
    nombre = nombre_de(aloj_id)
    guests = p["huespedes"]
    cin, cout = p["check_in"], p["check_out"]
    nombre_cli = p.get("cliente_nombre", "")
    email = p.get("cliente_email", "")
    tel = p.get("cliente_tel", "")
    dni = p.get("cliente_dni","")
    dni_mask = (dni[:2] + "****" + dni[-2:]) if len(dni) >= 4 else dni

    pn_base = float(precio_noche_de(aloj_id))
    noches = (cout - cin).days if cin and cout else 0

    disc = float(dynamic_discount_pct(cin)) if cin else 0.0
    pn_final = float(apply_discount(pn_base, disc))
    total = round(noches * pn_final, 2) if noches else 0.0

    disc_line = ""
    if disc > 0:
        disc_pct_txt = int(round(disc * 100))
        disc_line = f"💸 Descuento dinámico: {disc_pct_txt}% (de {pn_base} → {pn_final} €/noche).\n"


    return (
    f"📝 Vas a reservar {nombre} del {cin} al {cout} "
    f"({noches} noche(s)) para {guests}.\n"
    f"👤 A nombre de {nombre_cli}, email {email}, tel {tel}, DNI/NIE {dni_mask}.\n"
    f"{disc_line}"
    f"💶 Total estimado: {total} € (a {pn_final} €/noche).\n"
    f"¿Confirmas la reserva? (sí / no)"
)


def validar_fechas_futuras(cin: date, cout: date) -> str | None:
    """
    Devuelve un mensaje de error si las fechas no son válidas
    (pasado, hoy o salida <= entrada). Si todo OK, devuelve None.
    """
    today = date.today()

    if cin <= today:
        if cin == today:
            return (
                "📅 Solo puedo crear reservas con **al menos un día de antelación**.\n"
                "El check-in no puede ser **hoy**. ¿Probamos desde mañana o más adelante?"
            )
        else:
            return (
                "📅 No puedo crear reservas para **fechas que ya han pasado**.\n"
                "Indica un check-in a partir de mañana, por favor. 🙂"
            )

    if cout <= cin:
        return "La fecha de salida debe ser posterior a la de entrada. 📅"

    return None


# ---------- Flujo de reserva con sesión ----------


def handle_reserva_with_session(
    session_id: str, text: str, slots: dict
) -> dict:
    sess = SESS.setdefault(session_id, {})
    norm = strip_accents(text.lower())

    # 1) Esperando confirmación
    if sess.get("awaiting_confirm") and sess.get("mode") == "reservar":
        p = sess.get("pending", {})

        if (
            p
            and p.get("aloj_id")
            and p.get("check_in")
            and p.get("check_out")
        ):
            # Validar fechas (no pasado / no hoy / salida > entrada)
            msg_fecha = validar_fechas_futuras(p["check_in"], p["check_out"])
            if msg_fecha:
                _reset_session_mode(session_id)
                return {"answer": msg_fecha}

            # Rechequear disponibilidad (por si hay carrera)
            if not hay_disponibilidad(
                p["aloj_id"], p["check_in"], p["check_out"]
            ):
                _reset_session_mode(session_id)
                return {
                    "answer": (
                        "🟥 Lo siento, esas fechas acaban de quedar ocupadas. "
                        "¿Probamos otras fechas?"
                    )
                }

        if CONFIRM_RE.search(norm):
            pn_base = float(precio_noche_de(p["aloj_id"]))
            disc = float(dynamic_discount_pct(p["check_in"]))
            pn_final = float(apply_discount(pn_base, disc))

            rid = crear_reserva_excel(
                p["aloj_id"],
                p["check_in"],
                p["check_out"],
                p["huespedes"],
                pn_base,  # 👈 pasamos BASE; domain_reservas aplicará descuento igualmente
                p.get("cliente_nombre"),
                p.get("cliente_email"),
                p.get("cliente_tel"),
                p.get("cliente_dni"),
            )

            # Guardamos último rango para el meteo-bot
            sess["last_range"] = {
                "check_in": p["check_in"],
                "check_out": p["check_out"],
                "aloj_id": p["aloj_id"],
            }

            _reset_session_mode(session_id)

            noches = (p["check_out"] - p["check_in"]).days
            total = round(noches * pn_final, 2)
            extra_disc = ""
            if disc > 0:
                extra_disc = f"\n💸 Descuento aplicado: {int(round(disc*100))}% (precio/noche {pn_base} → {pn_final} €)."

            nombre_aloj = nombre_de(p["aloj_id"])
            return {
                "answer": (
                    f"✅ Reserva creada (ID {rid}).\n"
                    f"- 🏡 Alojamiento: {nombre_aloj}\n"
                    f"- 📅 Fechas: {p['check_in']} → {p['check_out']} ({noches} noche(s))\n"
                    f"- 👥 Huéspedes: {p['huespedes']}\n"
                    f"- 💶 Importe total: {total} €\n"
                    f"{extra_disc}\n"
                    f"He bloqueado el calendario para esas fechas. 📌"
                )
                }


        if CANCEL_RE.search(norm):
            _reset_session_mode(session_id)
            return {
                "answer": "👌 De acuerdo, he cancelado el proceso de reserva."
            }

        return {"answer": "Solo necesito un **sí** o un **no** para continuar. 🙂"}

    # 2) Mezclar slots nuevos con los que ya teníamos
    pending = sess.get("pending", {})
    merged = merge_slots(pending, slots)

    # --- Validación temprana de negocio (antes de pedir datos de cliente) ---
    essential_keys = ["aloj_id", "check_in", "check_out", "huespedes"]
    essential_missing = [k for k in essential_keys if not merged.get(k)]

    if not essential_missing:
        aid = merged["aloj_id"]
        cin = merged["check_in"]
        cout = merged["check_out"]
        guests = merged["huespedes"]

        # Fechas
        msg_fecha = validar_fechas_futuras(cin, cout)
        if msg_fecha:
            return {"answer": msg_fecha}

        # Capacidad
        cap = capacidad_de(aid)
        if guests and guests > cap:
            return {
                "answer": (
                    f"❌ El alojamiento ({nombre_de(aid)}) admite hasta {cap} huéspedes. "
                    f"Has pedido {guests}. ¿Ajustamos el número?"
                )
            }

        # Disponibilidad
        if not hay_disponibilidad(aid, cin, cout):
            return {
                "answer": (
                    f"🟥 No hay disponibilidad en ese rango para {nombre_de(aid)}.\n"
                    f"¿Probamos otras fechas?"
                )
            }

    # ¿Faltan todavía campos (sobre todo de cliente)?
    faltan = missing_fields(merged)
    if faltan:
        sess["mode"] = "reservar"
        sess["pending"] = merged
        nice = {
            "aloj_id": "alojamiento",
            "check_in": "check-in",
            "check_out": "check-out",
            "huespedes": "huéspedes",
            "cliente_nombre": "nombre",
            "cliente_email": "email",
            "cliente_tel": "teléfono",
            "cliente_dni": "DNI/NIE",
        }
        faltan_nice = ", ".join(nice.get(f, f) for f in faltan)
        return {
            "answer": f"Me falta: {faltan_nice}. 🧩 Dímelo y continúo."
        }

    # 3) Validación completa antes de pedir confirmación
    aid = merged["aloj_id"]
    cin = merged["check_in"]
    cout = merged["check_out"]
    guests = merged["huespedes"]

    # Fechas otra vez por seguridad (por si se han modificado en este turno)
    msg_fecha = validar_fechas_futuras(cin, cout)
    if msg_fecha:
        return {"answer": msg_fecha}

    # Capacidad
    cap = capacidad_de(aid)
    if guests and guests > cap:
        return {
            "answer": (
                f"⚠️ El alojamiento ({nombre_de(aid)}) admite hasta {cap} "
                "huéspedes. ¿Ajustamos el número?"
            )
        }

    # Disponibilidad
    if not hay_disponibilidad(aid, cin, cout):
        return {
            "answer": (
                f"🟥 No hay disponibilidad en ese rango para {nombre_de(aid)}. "
                "¿Probamos otras fechas?"
            )
        }

    # Todo OK → resumen y pedir confirmación
    sess["mode"] = "reservar"
    sess["pending"] = merged
    sess["awaiting_confirm"] = True
    return {"answer": summarize(merged)}



# ---------- Flujos de cancelar / modificar / consultar ----------

def _norm_email(s: str | None) -> str:
    return (s or "").strip().lower()

def _norm_dni(s: str | None) -> str:
    # Normalización simple: sin espacios y en mayúsculas
    return (s or "").strip().replace(" ", "").upper()

def _extract_auth_from_slots(slots: dict) -> dict:
    """Saca credenciales de verificación desde slots."""
    return {
        "email": _norm_email(slots.get("cliente_email")),
        "dni": _norm_dni(slots.get("cliente_dni") or slots.get("dni") or slots.get("nie")),
    }

def _row_owner_auth(row) -> dict:
    """Saca credenciales del propietario guardadas en la reserva (row de pandas)."""
    # OJO: depende de cómo tengas las columnas en reservas.xlsx
    return {
        "email": _norm_email(row.get("cliente_email") if hasattr(row, "get") else row["cliente_email"]),
        "dni": _norm_dni(row.get("cliente_dni") if hasattr(row, "get") else row["cliente_dni"]),
    }

def _auth_matches(owner: dict, provided: dict) -> bool:
    """
    Regla: Para autorizar debe coincidir (email o dni).
    """
    if provided.get("email") and owner.get("email") and provided["email"] == owner["email"]:
        return True
    if provided.get("dni") and owner.get("dni") and provided["dni"] == owner["dni"]:
        return True
    return False

def _ask_for_auth(action: str, rid: int) -> dict:
    """
    Mensaje estándar para pedir verificación.
    """
    return {
        "answer": (
            f"🔒 Para {action} la reserva {rid}, necesito verificar que eres el propietario.\n"
            "Envíame **el email de la reserva** o tu **DNI/NIE** (solo uno vale). 😊\n"
            f"Ejemplos:\n"
            f"• \"mi email es persona@correo.com\"\n"
            f"• \"mi DNI es 12345678Z\""
        )
    }


def start_cancel_flow(session_id: str, text: str, slots: dict) -> dict:
    norm = strip_accents(text.lower())
    sess = SESS.setdefault(session_id, {})

    m = RESERVA_ID_RE.search(norm)
    if not m:
        return {
            "answer": (
                "🗑️ Para cancelar necesito el ID de la reserva. 🙏\n"
                "Por ejemplo: *'cancela la reserva 12'*."
            )
        }

    rid = int(m.group(1))
    row = get_reserva_by_id(rid)
    if row is None:
        return {"answer": f"❓ No encuentro la reserva {rid}."}

    estado = str(row.get("estado") or "").lower()
    if estado != "creada":
        return {
            "answer": (
                f"⚠️ La reserva {rid} está en estado '{estado}' y no puede cancelarse."
            )
        }

    # --- Verificación de propietario (email o DNI/NIE) ---
    owner = _row_owner_auth(row)
    provided = _extract_auth_from_slots(slots)

    sess["mode"] = "cancelar"
    sess["pending_cancel"] = {"reserva_id": rid}
    sess["awaiting_confirm"] = False  # aún no, primero verificación

    # Si no nos han dado credenciales -> pedimos
    if not (provided["email"] or provided["dni"]):
        sess["awaiting_auth"] = True
        return _ask_for_auth("cancelar", rid)

    # Si no coincide -> rechazamos
    if not _auth_matches(owner, provided):
        return {
            "answer": (
                "⛔ No puedo cancelar esa reserva: el email/DNI no coincide con el propietario.\n"
                "Si crees que es un error, prueba con el email o DNI que se usó al reservar. 🙏"
            )
        }

    # Si coincide -> pasamos a confirmación
    resumen = format_reserva_row(row.to_dict())
    sess["awaiting_auth"] = False
    sess["awaiting_confirm"] = True

    return {
        "answer": (
            f"✅ Verificación correcta.\n\n"
            f"Vas a cancelar esta reserva:\n\n{resumen}\n\n"
            f"¿Confirmas la cancelación de la reserva {rid}? (sí / no) 🗑️"
        )
    }


def handle_cancel_with_session(session_id: str, text: str, slots: dict) -> dict:
    sess = SESS.setdefault(session_id, {})
    pending = sess.get("pending_cancel", {})
    rid = pending.get("reserva_id")

    if not rid:
        _reset_session_mode(session_id)
        return {
            "answer": (
                "😅 No tengo claro qué reserva cancelar.\n"
                "Indica por favor *'cancela la reserva 12'*."
            )
        }

    row = get_reserva_by_id(int(rid))
    if row is None:
        _reset_session_mode(session_id)
        return {"answer": f"❓ No encuentro la reserva {rid}."}

    # 1) Si estamos esperando verificación (auth)
    if sess.get("awaiting_auth"):
        owner = _row_owner_auth(row)
        provided = _extract_auth_from_slots(slots)

        if not (provided["email"] or provided["dni"]):
            return _ask_for_auth("cancelar", int(rid))

        if not _auth_matches(owner, provided):
            return {
                "answer": (
                    "⛔ El email/DNI no coincide con el propietario de esa reserva.\n"
                    "Prueba otra vez con el dato correcto (email o DNI/NIE). 🔒"
                )
            }

        # OK -> pasamos a confirmación
        resumen = format_reserva_row(row.to_dict())
        sess["awaiting_auth"] = False
        sess["awaiting_confirm"] = True
        return {
            "answer": (
                f"✅ Verificación correcta.\n\n"
                f"Vas a cancelar esta reserva:\n\n{resumen}\n\n"
                f"¿Confirmas la cancelación de la reserva {rid}? (sí / no) 🗑️"
            )
        }

    # 2) Confirmación final (sí/no)
    norm = strip_accents(text.lower())

    if sess.get("awaiting_confirm"):
        if CONFIRM_RE.search(norm):
            res = cancelar_reserva_excel(int(rid))
            _reset_session_mode(session_id)
            if not res.get("ok"):
                return {"answer": res.get("message", "😕 No he podido cancelar la reserva.")}

            nombre_aloj = nombre_de(res["id_alojamiento"])
            return {
                "answer": (
                    f"✅ Reserva {rid} cancelada.\n"
                    f"- 🏡 Alojamiento: {nombre_aloj}\n"
                    f"- 📅 Fechas: {res['check_in']} → {res['check_out']}\n"
                    f"He liberado esas fechas en el calendario. 🗓️"
                )
            }

        if CANCEL_RE.search(norm):
            _reset_session_mode(session_id)
            return {"answer": "👌 De acuerdo, no cancelo la reserva."}

        return {"answer": f"¿Confirmas que quieres cancelar la reserva {rid}? (sí / no) 🗑️"}

    # Si no estamos en nada claro, reencauzamos:
    sess["awaiting_auth"] = True
    return _ask_for_auth("cancelar", int(rid))


def start_modificar_flow(session_id: str, text: str, slots: dict) -> dict:
    norm = strip_accents(text.lower())
    sess = SESS.setdefault(session_id, {})

    m = RESERVA_ID_RE.search(norm)
    if not m:
        return {
            "answer": (
                "✏️ Para modificar necesito el ID de la reserva. 🙏\n"
                "Ejemplo:\n"
                "• *\"mueve la reserva 12 al 15/07–17/07\"*\n"
                "• *\"cambia a 4 personas en la reserva 12\"*."
            )
        }

    rid = int(m.group(1))
    row = get_reserva_by_id(rid)
    if row is None:
        return {"answer": f"❓ No encuentro la reserva {rid}."}

    estado = str(row.get("estado") or "").lower()
    if estado != "creada":
        return {"answer": f"⚠️ La reserva {rid} está en estado '{estado}' y no puede modificarse."}

    # --- Verificación de propietario (email o DNI/NIE) ---
    owner = _row_owner_auth(row)
    provided = _extract_auth_from_slots(slots)

    sess["mode"] = "modificar"
    sess["awaiting_confirm"] = False
    sess["pending_modify"] = {"reserva_id": rid}
    # guardamos algo para mostrar
    id_aloj = int(row["id_alojamiento"])
    old_ci = pd.to_datetime(row["check_in"]).date()
    old_co = pd.to_datetime(row["check_out"]).date()
    old_hues = int(row.get("huespedes") or 0)

    # Si no credenciales -> pedirlas antes de permitir modificar
    if not (provided["email"] or provided["dni"]):
        sess["awaiting_auth"] = True
        return _ask_for_auth("modificar", rid)

    if not _auth_matches(owner, provided):
        return {
            "answer": (
                "⛔ No puedo modificar esa reserva: el email/DNI no coincide con el propietario.\n"
                "Prueba con el email o DNI/NIE que se usó al reservar. 🔒"
            )
        }

    sess["awaiting_auth"] = False

    # 👉 Caso 1: el usuario todavía no ha dado nuevas fechas / huéspedes
    if not (slots.get("check_in") or slots.get("check_out") or slots.get("huespedes")):
        nombre_aloj = nombre_de(id_aloj)
        return {
            "answer": (
                f"✅ Verificación correcta.\n\n"
                f"Esta es tu reserva {rid} en {nombre_aloj}:\n"
                f"- 📅 Fechas: {old_ci} → {old_co}\n"
                f"- 👥 Huéspedes: {old_hues}\n\n"
                "Dime qué quieres modificar. ✏️\n"
                "Ejemplos:\n"
                f"• \"mueve la reserva {rid} al 20/07–22/07\"\n"
                f"• \"cambia a 4 personas en la reserva {rid}\"."
            )
        }

    # 👉 Caso 2: el mensaje ya trae nuevas fechas / huéspedes
    new_ci = slots.get("check_in") or old_ci
    new_co = slots.get("check_out") or old_co
    new_hues = slots.get("huespedes") or old_hues

    if new_co <= new_ci:
        return {"answer": "📅 La fecha de salida debe ser posterior a la de entrada."}

    
    noches = max(1, (new_co - new_ci).days)
    pn_base = float(precio_noche_de(id_aloj))
    disc = float(dynamic_discount_pct(new_ci))
    pn_final = float(apply_discount(pn_base, disc))
    total = round(noches * pn_final, 2)

    disc_line = ""
    if disc > 0:
        disc_line = f"\n💸 Descuento dinámico: {int(round(disc*100))}% (de {pn_base} → {pn_final} €/noche)."


    sess["pending_modify"] = {
        "reserva_id": rid,
        "new_check_in": new_ci,
        "new_check_out": new_co,
        "new_huespedes": new_hues,
    }
    sess["awaiting_confirm"] = True

    nombre_aloj = nombre_de(id_aloj)
    return {
        "answer": (
            f"Vas a modificar la reserva {rid} en {nombre_aloj}:\n"
            f"- 📅 Fechas antes: {old_ci} → {old_co}\n"
            f"- 📅 Fechas nuevas: {new_ci} → {new_co}\n"
            f"- 👥 Huéspedes: {old_hues} → {new_hues}\n"
            f"💶 Nuevo total estimado: {total} €.\n"
            f"¿Confirmas la modificación? (sí / no) ✏️"
        )
    }


def handle_modificar_with_session(session_id: str, text: str, slots: dict) -> dict:
    sess = SESS.setdefault(session_id, {})
    pending = sess.get("pending_modify", {})
    rid = pending.get("reserva_id")

    if not rid:
        _reset_session_mode(session_id)
        return {
            "answer": (
                "😅 No tengo claro qué reserva modificar.\n"
                "Indica algo como *'modifica la reserva 12'*."
            )
        }

    row = get_reserva_by_id(int(rid))
    if row is None:
        _reset_session_mode(session_id)
        return {"answer": f"❓ No encuentro la reserva {rid}."}

    # 1) Verificación (si está pendiente)
    if sess.get("awaiting_auth"):
        owner = _row_owner_auth(row)
        provided = _extract_auth_from_slots(slots)

        if not (provided["email"] or provided["dni"]):
            return _ask_for_auth("modificar", int(rid))

        if not _auth_matches(owner, provided):
            return {
                "answer": (
                    "⛔ El email/DNI no coincide con el propietario de esa reserva.\n"
                    "Prueba otra vez con el dato correcto (email o DNI/NIE). 🔒"
                )
            }

        sess["awaiting_auth"] = False

        # Tras verificar, pedimos qué quiere cambiar si no lo trae
        id_aloj = int(row["id_alojamiento"])
        old_ci = pd.to_datetime(row["check_in"]).date()
        old_co = pd.to_datetime(row["check_out"]).date()
        old_hues = int(row.get("huespedes") or 0)
        nombre_aloj = nombre_de(id_aloj)

        return {
            "answer": (
                f"✅ Verificación correcta.\n\n"
                f"Esta es tu reserva {rid} en {nombre_aloj}:\n"
                f"- 📅 Fechas: {old_ci} → {old_co}\n"
                f"- 👥 Huéspedes: {old_hues}\n\n"
                "¿Qué quieres modificar? ✏️\n"
                f"• \"mueve la reserva {rid} al 20/07–22/07\"\n"
                f"• \"cambia a 4 personas en la reserva {rid}\"."
            )
        }

    # 2) Si todavía no tenemos propuesta (new_check_in/out/huespedes), la construimos con este mensaje
    #    (esto permite: "modificar reserva 12" -> (verif) -> "del 20/07 al 22/07")
    if not pending.get("new_check_in") and not pending.get("new_check_out") and not pending.get("new_huespedes"):
        id_aloj = int(row["id_alojamiento"])
        old_ci = pd.to_datetime(row["check_in"]).date()
        old_co = pd.to_datetime(row["check_out"]).date()
        old_hues = int(row.get("huespedes") or 0)

        # Si el usuario no ha dado nada útil todavía:
        if not (slots.get("check_in") or slots.get("check_out") or slots.get("huespedes")):
            nombre_aloj = nombre_de(id_aloj)
            return {
                "answer": (
                    f"✏️ Vale, esta es tu reserva {rid} en {nombre_aloj}:\n"
                    f"- 📅 Fechas: {old_ci} → {old_co}\n"
                    f"- 👥 Huéspedes: {old_hues}\n\n"
                    "Dime nuevas fechas y/o huéspedes. 😊"
                )
            }

        new_ci = slots.get("check_in") or old_ci
        new_co = slots.get("check_out") or old_co
        new_hues = slots.get("huespedes") or old_hues

        if new_co <= new_ci:
            return {"answer": "📅 La fecha de salida debe ser posterior a la de entrada."}

        
        noches = max(1, (new_co - new_ci).days)
        pn_base = float(precio_noche_de(id_aloj))
        disc = float(dynamic_discount_pct(new_ci))
        pn_final = float(apply_discount(pn_base, disc))
        total = round(noches * pn_final, 2)

        disc_line = ""
        if disc > 0:
            disc_line = f"\n💸 Descuento dinámico: {int(round(disc*100))}% (de {pn_base} → {pn_final} €/noche)."

        nombre_aloj = nombre_de(id_aloj)

        sess["pending_modify"] = {
            "reserva_id": int(rid),
            "new_check_in": new_ci,
            "new_check_out": new_co,
            "new_huespedes": new_hues,
        }
        sess["awaiting_confirm"] = True

        return {
            "answer": (
                f"Vas a modificar la reserva {rid} en {nombre_aloj}:\n"
                f"- 📅 Fechas nuevas: {new_ci} → {new_co}\n"
                f"- 👥 Huéspedes: {old_hues} → {new_hues}\n"
                f"💶 Nuevo total estimado: {total} €.\n"
                f"{disc_line}\n\n"
                f"¿Confirmas la modificación? (sí / no) ✏️"
            )
        }

    # 3) Confirmación final
    norm = strip_accents(text.lower())

    if sess.get("awaiting_confirm"):
        if CONFIRM_RE.search(norm):
            res = modificar_reserva_excel(
                reserva_id=int(rid),
                new_check_in=pending.get("new_check_in"),
                new_check_out=pending.get("new_check_out"),
                new_huespedes=pending.get("new_huespedes"),
            )
            _reset_session_mode(session_id)

            if not res.get("ok"):
                return {
                    "answer": res.get("message", "😕 No he podido modificar la reserva.")
                }

            nombre_aloj = nombre_de(res["id_alojamiento"])
            noches = (res["check_out"] - res["check_in"]).days

            disc = float(res.get("descuento_pct") or 0.0)
            msg_disc = ""
            if disc > 0:
                msg_disc = (
                    f"\n💸 Descuento aplicado: {int(round(disc * 100))}% "
                    f"(precio/noche {res.get('precio_noche_base')} → {res.get('precio_noche_final')} €)."
                )

            return {
                "answer": (
                    f"✅ Reserva {rid} modificada.\n"
                    f"- 🏡 Alojamiento: {nombre_aloj}\n"
                    f"- 📅 Fechas antes: {res['old_check_in']} → {res['old_check_out']}\n"
                    f"- 📅 Fechas nuevas: {res['check_in']} → {res['check_out']} ({noches} noche(s))\n"
                    f"- 👥 Huéspedes: {res['old_huespedes']} → {res['huespedes']}\n"
                    f"- 💶 Nuevo total: {res['precio_total']} €"
                    f"{msg_disc}"
                )
            }

        if CANCEL_RE.search(norm):
            _reset_session_mode(session_id)
            return {"answer": "👌 De acuerdo, no modifico la reserva."}

        return {"answer": "¿Confirmas la modificación? (sí / no) ✏️"}


    # fallback
    return {"answer": "✏️ ¿Qué quieres modificar exactamente? Indica fechas y/o huéspedes."}



def handle_consulta_reservas(slots: dict, text: str) -> dict:
    norm = strip_accents(text.lower())

    # 1) Por ID
    m = RESERVA_ID_RE.search(norm)
    if m:
        rid = int(m.group(1))
        row = get_reserva_by_id(rid)
        if row is None:
            return {"answer": f"No encuentro la reserva {rid}. ❓"}
        resumen = format_reserva_row(row.to_dict())
        return {"answer": f"Aquí tienes la reserva {rid}: 📄\n\n{resumen}"}

    # 2) Por email
    email = slots.get("cliente_email")
    if not email:
        return {
            "answer": (
                "Puedo consultar reservas por ID (*'consulta la reserva 12'*) "
                "o por email (*'mis reservas para tu_correo@ejemplo.com'*). 🔎"
            )
        }

    cin = slots.get("check_in")
    cout = slots.get("check_out")
    reservas = list_reservas_by_email(
        email, cin, cout, solo_activas=True, max_items=20
    )
    if not reservas:
        return {
            "answer": f"No encuentro reservas activas para {email}. 😕"
        }

    bloques = [format_reserva_row(r) for r in reservas]
    joined = "\n\n".join(bloques)
    return {
        "answer": f"Estas son tus reservas activas para {email}: 📂\n\n{joined}"
    }
