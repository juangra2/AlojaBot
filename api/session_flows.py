# api/session_flows.py
from __future__ import annotations

from datetime import date
from typing import Dict
import re

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
    encontrar_aloj_por_nombre,
)
from .utils_nlu import (
    strip_accents,
    CONFIRM_RE,
    CANCEL_RE,
    RESERVA_ID_RE,
)
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

# =========================
# UX: Mensajes guiados (pedir datos)
# =========================

_FIELD_ORDER = [
    "aloj_id",
    "check_in",
    "check_out",
    "huespedes",
    "cliente_nombre",
    "cliente_email",
    "cliente_tel",
    "cliente_dni",
]

_FIELD_LABELS = {
    "aloj_id": "🏡 Alojamiento",
    "check_in": "📅 Check-in",
    "check_out": "📅 Check-out",
    "huespedes": "👥 Huéspedes",
    "cliente_nombre": "👤 Nombre",
    "cliente_email": "📧 Email",
    "cliente_tel": "📞 Teléfono",
    "cliente_dni": "🪪 DNI/NIE",
}

_FIELD_EXAMPLES = {
    "aloj_id": "Casa Bruna (o ID 2)",
    "check_in": "del 20/09",
    "check_out": "al 23/09",
    "huespedes": "4 personas",
    "cliente_nombre": "Juan Pérez",
    "cliente_email": "juanperez@gmail.com",
    "cliente_tel": "600123456 o +34600123456",
    "cliente_dni": "12345678Z o X1234567L",
}


def _ordered_missing(faltan: list[str]) -> list[str]:
    """Orden bonito según el flujo natural."""
    s = set(faltan or [])
    ordered = [k for k in _FIELD_ORDER if k in s]
    for k in (faltan or []):
        if k not in ordered:
            ordered.append(k)
    return ordered


def build_missing_fields_message(faltan: list[str]) -> str:
    """
    Mensaje moderno + guiado para pedir datos de RESERVA.
    Pide una sola frase, separado por comas, con ejemplos.
    """
    faltan = _ordered_missing(faltan)

    lines = ["🧩 Para continuar necesito estos datos (en **una sola frase**, separados por comas):"]
    for k in faltan:
        label = _FIELD_LABELS.get(k, k)
        ex = _FIELD_EXAMPLES.get(k, "")
        if ex:
            lines.append(f"- {label}: ej. **{ex}**")
        else:
            lines.append(f"- {label}")

    example_sentence = (
        "Del 20/09 al 23/09, 4 personas, Juan Pérez, juanperez@gmail.com, +34600123456, 12345678Z"
    )
    lines.append("")
    lines.append("✅ Ejemplo de mensaje:")
    lines.append(f"**{example_sentence}**")
    lines.append("")
    lines.append("💡 Tip: si no sabes el alojamiento exacto, dime el nombre (ej. *Casa Bruna*).")
    return "\n".join(lines)


def build_auth_message(action: str, rid: int) -> str:
    """
    Mensaje guiado de verificación para CANCELAR/MODIFICAR.
    """
    return (
        f"🔒 Para **{action}** la reserva **{rid}**, necesito verificar que eres el propietario.\n\n"
        "Envíame **UNO** de estos datos (en una sola frase):\n"
        "- 📧 Email usado en la reserva (ej. **persona@correo.com**)\n"
        "- 🪪 DNI/NIE usado en la reserva (ej. **12345678Z** o **X1234567L**)\n\n"
        "✅ Ejemplos:\n"
        "• **Mi email es persona@correo.com**\n"
        "• **Mi DNI es 12345678Z**"
    )


def build_modify_request_message(rid: int) -> str:
    """
    Mensaje guiado cuando ya verificó y falta que diga QUÉ quiere cambiar.
    """
    return (
        "✏️ Dime qué quieres cambiar (en una sola frase, separado por comas).\n"
        "Puedes mandar:\n"
        "- 📅 Nuevas fechas (ej. **del 20/07 al 22/07**)\n"
        "- 👥 Nuevos huéspedes (ej. **4 personas**)\n"
        "- o ambos\n\n"
        "✅ Ejemplos:\n"
        f"• **Mueve la reserva {rid} del 20/07 al 22/07**\n"
        f"• **Cambia la reserva {rid} a 4 personas**\n"
        f"• **Reserva {rid}: del 20/07 al 22/07, 4 personas**"
    )


# =========================
# VALIDACIONES (DNI/NIE + TEL)
# =========================

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def normalize_dni_nie(s: str | None) -> str:
    """Quita espacios/guiones y pone en mayúsculas."""
    return (s or "").strip().replace(" ", "").replace("-", "").upper()


def is_valid_dni_nie(s: str | None) -> bool:
    """
    Valida DNI (8 dígitos + letra) y NIE (X/Y/Z + 7 dígitos + letra) con cálculo de letra.
    """
    v = normalize_dni_nie(s)
    if not v:
        return False

    # DNI
    if re.fullmatch(r"\d{8}[A-Z]", v):
        num = int(v[:8])
        letra = v[-1]
        return _DNI_LETTERS[num % 23] == letra

    # NIE
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", v):
        prefix = v[0]
        num7 = v[1:8]
        letra = v[-1]
        map_prefix = {"X": "0", "Y": "1", "Z": "2"}
        num = int(map_prefix[prefix] + num7)
        return _DNI_LETTERS[num % 23] == letra

    return False


def normalize_phone(s: str | None) -> str:
    """
    Normaliza teléfono:
    - conserva '+' si venía
    - elimina espacios/guiones/paréntesis/puntos
    """
    if not s:
        return ""
    raw = str(s).strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return ""
    return ("+" + digits) if has_plus else digits


def validate_phone(s: str | None) -> tuple[bool, str]:
    """
    Regla práctica:
    - Si empieza con '+': 8-15 dígitos (E.164 aproximado)
    - Si NO: asumimos España y exigimos 9 dígitos
    """
    v = normalize_phone(s)
    if not v:
        return False, "📞 El teléfono está vacío o no parece válido."

    if v.startswith("+"):
        digits = v[1:]
        if not digits.isdigit():
            return False, "📞 El teléfono con prefijo debe contener solo números tras el '+'."
        if not (8 <= len(digits) <= 15):
            return False, "📞 El teléfono internacional debe tener entre 8 y 15 dígitos (ej: +34600123456)."
        return True, ""

    # Sin '+': España (permitimos ambos formatos: nacional o internacional)
    if not v.isdigit():
        return False, "📞 El teléfono debe contener solo números."
    if len(v) != 9:
        return False, "📞 Para España necesito 9 dígitos (ej: 600123456) o formato internacional +34..."
    if v[0] not in {"6", "7", "8", "9"}:
        return False, "📞 El teléfono no parece de España (debería empezar por 6/7/8/9) o usa +prefijo."
    return True, ""


def validate_contact_fields_partial(p: dict) -> str | None:
    """
    Valida DNI/NIE y teléfono si existen en 'p'.
    No exige que estén presentes (eso lo hace missing_fields),
    pero si están, deben ser correctos.
    """
    if p.get("cliente_dni"):
        dni = normalize_dni_nie(p.get("cliente_dni"))
        if not is_valid_dni_nie(dni):
            return (
                "🪪 El **DNI/NIE no es válido** (la letra no coincide).\n"
                "Revísalo y envíamelo de nuevo, por favor.\n"
                "Ejemplos:\n"
                "• DNI: 12345678Z\n"
                "• NIE: X1234567L"
            )
        p["cliente_dni"] = dni

    if p.get("cliente_tel"):
        ok, msg = validate_phone(p.get("cliente_tel"))
        if not ok:
            return msg + "\nEjemplos:\n• 600123456\n• +34600123456"
        p["cliente_tel"] = normalize_phone(p.get("cliente_tel"))

    return None


def _validate_auth_inputs(provided: dict) -> str | None:
    """
    Si han proporcionado DNI/NIE, validamos formato y letra.
    """
    dni = provided.get("dni") or ""
    if dni:
        if not is_valid_dni_nie(dni):
            return (
                "🪪 El **DNI/NIE no es válido** (la letra no coincide).\n"
                "Revísalo y envíamelo de nuevo.\n"
                "Ejemplos:\n"
                "• DNI: 12345678Z\n"
                "• NIE: X1234567L"
            )
    return None


def _reset_session_mode(session_id: str) -> None:
    """Limpia modo/pendientes pero conserva cosas como last_range."""
    sess = SESS.setdefault(session_id, {})
    for key in (
        "mode",
        "pending",
        "awaiting_confirm",
        "pending_cancel",
        "pending_modify",
        "awaiting_auth",
    ):
        sess.pop(key, None)


def resolve_aloj_if_needed(p: dict):
    if not p.get("aloj_id"):
        aid = encontrar_aloj_por_nombre(p.get("raw_text", ""))
        if aid:
            p["aloj_id"] = aid


def merge_slots(pending: dict, new: dict) -> dict:
    out = dict(pending or {})
    for k, v in (new or {}).items():
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
    dni = p.get("cliente_dni", "")
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

def handle_reserva_with_session(session_id: str, text: str, slots: dict) -> dict:
    sess = SESS.setdefault(session_id, {})
    norm = strip_accents(text.lower())

    # 1) Esperando confirmación
    if sess.get("awaiting_confirm") and sess.get("mode") == "reservar":
        p = sess.get("pending", {}) or {}

        # Revalidar DNI/TEL por si el usuario los cambió antes de confirmar
        msg_contacto = validate_contact_fields_partial(p)
        if msg_contacto:
            sess["pending"] = p
            return {"answer": msg_contacto}

        if p and p.get("aloj_id") and p.get("check_in") and p.get("check_out"):
            # Validar fechas
            msg_fecha = validar_fechas_futuras(p["check_in"], p["check_out"])
            if msg_fecha:
                _reset_session_mode(session_id)
                return {"answer": msg_fecha}

            # Rechequear disponibilidad (por si hay carrera)
            if not hay_disponibilidad(p["aloj_id"], p["check_in"], p["check_out"]):
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
                pn_base,  # pasamos BASE; domain_reservas recalcula y guarda descuento/final
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
                extra_disc = (
                    f"\n💸 Descuento aplicado: {int(round(disc*100))}% "
                    f"(precio/noche {pn_base} → {pn_final} €)."
                )

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
            return {"answer": "👌 De acuerdo, he cancelado el proceso de reserva."}

        return {"answer": "Solo necesito un **sí** o un **no** para continuar. 🙂"}

    # 2) Mezclar slots nuevos con los que ya teníamos
    pending = sess.get("pending", {}) or {}
    merged = merge_slots(pending, slots or {})

    # Validación inmediata si han metido DNI/TEL en este turno
    msg_contacto = validate_contact_fields_partial(merged)
    if msg_contacto:
        sess["mode"] = "reservar"
        sess["pending"] = merged
        return {"answer": msg_contacto}

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

    # ¿Faltan todavía campos?
    faltan = missing_fields(merged)
    if faltan:
        sess["mode"] = "reservar"
        sess["pending"] = merged
        return {"answer": build_missing_fields_message(faltan)}

    # 3) Validación completa antes de pedir confirmación
    aid = merged["aloj_id"]
    cin = merged["check_in"]
    cout = merged["check_out"]
    guests = merged["huespedes"]

    msg_fecha = validar_fechas_futuras(cin, cout)
    if msg_fecha:
        return {"answer": msg_fecha}

    cap = capacidad_de(aid)
    if guests and guests > cap:
        return {
            "answer": (
                f"⚠️ El alojamiento ({nombre_de(aid)}) admite hasta {cap} huéspedes. "
                "¿Ajustamos el número?"
            )
        }

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
    return normalize_dni_nie(s)


def _extract_auth_from_slots(slots: dict) -> dict:
    """Saca credenciales de verificación desde slots."""
    return {
        "email": _norm_email((slots or {}).get("cliente_email")),
        "dni": _norm_dni((slots or {}).get("cliente_dni") or (slots or {}).get("dni") or (slots or {}).get("nie")),
    }


def _row_owner_auth(row) -> dict:
    """Saca credenciales del propietario guardadas en la reserva (row de pandas)."""
    return {
        "email": _norm_email(row.get("cliente_email") if hasattr(row, "get") else row["cliente_email"]),
        "dni": _norm_dni(row.get("cliente_dni") if hasattr(row, "get") else row["cliente_dni"]),
    }


def _auth_matches(owner: dict, provided: dict) -> bool:
    """Regla: Para autorizar debe coincidir (email o dni)."""
    if provided.get("email") and owner.get("email") and provided["email"] == owner["email"]:
        return True
    if provided.get("dni") and owner.get("dni") and provided["dni"] == owner["dni"]:
        return True
    return False


def _ask_for_auth(action: str, rid: int) -> dict:
    return {"answer": build_auth_message(action, rid)}


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
        return {"answer": f"⚠️ La reserva {rid} está en estado '{estado}' y no puede cancelarse."}

    owner = _row_owner_auth(row)
    provided = _extract_auth_from_slots(slots)

    sess["mode"] = "cancelar"
    sess["pending_cancel"] = {"reserva_id": rid}
    sess["awaiting_confirm"] = False

    if not (provided["email"] or provided["dni"]):
        sess["awaiting_auth"] = True
        return _ask_for_auth("cancelar", rid)

    msg_auth = _validate_auth_inputs(provided)
    if msg_auth:
        sess["awaiting_auth"] = True
        return {"answer": msg_auth}

    if not _auth_matches(owner, provided):
        return {
            "answer": (
                "⛔ No puedo cancelar esa reserva: el email/DNI no coincide con el propietario.\n"
                "Si crees que es un error, prueba con el email o DNI que se usó al reservar. 🙏"
            )
        }

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
    pending = sess.get("pending_cancel", {}) or {}
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

        msg_auth = _validate_auth_inputs(provided)
        if msg_auth:
            return {"answer": msg_auth}

        if not _auth_matches(owner, provided):
            return {
                "answer": (
                    "⛔ El email/DNI no coincide con el propietario de esa reserva.\n"
                    "Prueba otra vez con el dato correcto (email o DNI/NIE). 🔒"
                )
            }

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

    # fallback
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

    owner = _row_owner_auth(row)
    provided = _extract_auth_from_slots(slots)

    sess["mode"] = "modificar"
    sess["awaiting_confirm"] = False
    sess["pending_modify"] = {"reserva_id": rid}

    id_aloj = int(row["id_alojamiento"])
    old_ci = pd.to_datetime(row["check_in"]).date()
    old_co = pd.to_datetime(row["check_out"]).date()
    old_hues = int(row.get("huespedes") or 0)

    if not (provided["email"] or provided["dni"]):
        sess["awaiting_auth"] = True
        return _ask_for_auth("modificar", rid)

    msg_auth = _validate_auth_inputs(provided)
    if msg_auth:
        sess["awaiting_auth"] = True
        return {"answer": msg_auth}

    if not _auth_matches(owner, provided):
        return {
            "answer": (
                "⛔ No puedo modificar esa reserva: el email/DNI no coincide con el propietario.\n"
                "Prueba con el email o DNI/NIE que se usó al reservar. 🔒"
            )
        }

    sess["awaiting_auth"] = False

    # Caso 1: todavía no ha dado nuevas fechas / huéspedes
    if not ((slots or {}).get("check_in") or (slots or {}).get("check_out") or (slots or {}).get("huespedes")):
        nombre_aloj = nombre_de(id_aloj)
        return {
            "answer": (
                f"✅ Verificación correcta.\n\n"
                f"Esta es tu reserva {rid} en {nombre_aloj}:\n"
                f"- 📅 Fechas: {old_ci} → {old_co}\n"
                f"- 👥 Huéspedes: {old_hues}\n\n"
                f"{build_modify_request_message(rid)}"
            )
        }

    # Caso 2: el mensaje ya trae nuevas fechas / huéspedes
    new_ci = (slots or {}).get("check_in") or old_ci
    new_co = (slots or {}).get("check_out") or old_co
    new_hues = (slots or {}).get("huespedes") or old_hues

    if new_co <= new_ci:
        return {"answer": "📅 La fecha de salida debe ser posterior a la de entrada."}

    noches = max(1, (new_co - new_ci).days)
    pn_base = float(precio_noche_de(id_aloj))
    disc = float(dynamic_discount_pct(new_ci))
    pn_final = float(apply_discount(pn_base, disc))
    total = round(noches * pn_final, 2)

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
    pending = sess.get("pending_modify", {}) or {}
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

        msg_auth = _validate_auth_inputs(provided)
        if msg_auth:
            return {"answer": msg_auth}

        if not _auth_matches(owner, provided):
            return {
                "answer": (
                    "⛔ El email/DNI no coincide con el propietario de esa reserva.\n"
                    "Prueba otra vez con el dato correcto (email o DNI/NIE). 🔒"
                )
            }

        sess["awaiting_auth"] = False

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
                f"{build_modify_request_message(int(rid))}"
            )
        }

    # 2) Si todavía no tenemos propuesta, la construimos con este mensaje
    if not pending.get("new_check_in") and not pending.get("new_check_out") and not pending.get("new_huespedes"):
        id_aloj = int(row["id_alojamiento"])
        old_ci = pd.to_datetime(row["check_in"]).date()
        old_co = pd.to_datetime(row["check_out"]).date()
        old_hues = int(row.get("huespedes") or 0)

        if not ((slots or {}).get("check_in") or (slots or {}).get("check_out") or (slots or {}).get("huespedes")):
            nombre_aloj = nombre_de(id_aloj)
            return {
                "answer": (
                    f"✏️ Vale, esta es tu reserva {rid} en {nombre_aloj}:\n"
                    f"- 📅 Fechas: {old_ci} → {old_co}\n"
                    f"- 👥 Huéspedes: {old_hues}\n\n"
                    f"{build_modify_request_message(int(rid))}"
                )
            }

        new_ci = (slots or {}).get("check_in") or old_ci
        new_co = (slots or {}).get("check_out") or old_co
        new_hues = (slots or {}).get("huespedes") or old_hues

        if new_co <= new_ci:
            return {"answer": "📅 La fecha de salida debe ser posterior a la de entrada."}

        noches = max(1, (new_co - new_ci).days)
        pn_base = float(precio_noche_de(id_aloj))
        disc = float(dynamic_discount_pct(new_ci))
        pn_final = float(apply_discount(pn_base, disc))
        total = round(noches * pn_final, 2)

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
                f"💶 Nuevo total estimado: {total} €.\n\n"
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
                return {"answer": res.get("message", "😕 No he podido modificar la reserva.")}

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
    email = (slots or {}).get("cliente_email")
    if not email:
        return {
            "answer": (
                "Puedo consultar reservas por ID (*'consulta la reserva 12'*) "
                "o por email (*'mis reservas para tu_correo@ejemplo.com'*). 🔎"
            )
        }

    cin = (slots or {}).get("check_in")
    cout = (slots or {}).get("check_out")
    reservas = list_reservas_by_email(email, cin, cout, solo_activas=True, max_items=20)
    if not reservas:
        return {"answer": f"No encuentro reservas activas para {email}. 😕"}

    bloques = [format_reserva_row(r) for r in reservas]
    joined = "\n\n".join(bloques)
    return {"answer": f"Estas son tus reservas activas para {email}: 📂\n\n{joined}"}