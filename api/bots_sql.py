# Bot de búsqueda transaccional sobre Excel

from __future__ import annotations

from typing import Dict

from .domain_reservas import (
    buscar_opciones,
    hay_disponibilidad,
    nombre_de,
    precio_noche_de,
    capacidad_de,
)

def sql_buscar_bot(slots: dict):
    cin = slots.get("check_in")
    cout = slots.get("check_out")
    guests = slots.get("huespedes")
    pmin, pmax = slots.get("price_min"), slots.get("price_max")
    aloj_id = slots.get("aloj_id")

    # --- 1) Caso: alojamiento concreto mencionado (Río Frío Montanejos, Casa del Mar...) ---
    if aloj_id:
        nombre = nombre_de(aloj_id)
        cap = capacidad_de(aloj_id)

        # Capacidad
        if guests and guests > cap:
            return {
                "answer": (
                    f"❌ {nombre} admite hasta {cap} huéspedes, "
                    f"y has pedido {guests}. ¿Ajustamos el número?"
                )
            }

        # Faltan fechas
        if not (cin and cout):
            return {
                "answer": (
                    f"Para comprobar si {nombre} está libre necesito las "
                    "fechas de entrada y salida. 📅"
                )
            }

        # Disponibilidad
        if hay_disponibilidad(aloj_id, cin, cout):
            pn = precio_noche_de(aloj_id)
            noches = max(1, (cout - cin).days)
            total = round(noches * pn, 2)
            return {
                "answer": (
                    f"✅ {nombre} está libre del {cin} al {cout} "
                    f"para {guests or 'X'} huéspedes.\n"
                    f"Precio aproximado: {pn} €/noche · {noches} noche(s) → {total} €.\n"
                    "¿Quieres que la reserve? 🙂"
                ),
                "candidatos": [
                    {
                        "id": aloj_id,
                        "nombre": nombre,
                        "capacidad": cap,
                        "precio_noche": pn,
                    }
                ],
            }
        else:
            return {
                "answer": (
                    f"🟥 {nombre} no está disponible del {cin} al {cout}.\n"
                    "¿Probamos otras fechas? 🙂"
                )
            }

    # --- 2) Caso general (sin alojamiento concreto) → comportamiento anterior ---
    candidatos = buscar_opciones(
        capacidad=guests, price_min=pmin, price_max=pmax
    )
    if not candidatos:
        return {
            "answer": (
                "No encuentro opciones con esos criterios. 😕\n"
                "¿Probamos con otra capacidad o presupuesto?"
            )
        }

    # Si tenemos fechas, filtramos por disponibilidad
    if cin and cout:
        disponibles = [
            c for c in candidatos
            if hay_disponibilidad(int(c["id"]), cin, cout)
        ]
        if disponibles:
            lista = "\n".join(
                [f"- {d['nombre']} · {d['precio_noche']} €/noche" for d in disponibles]
            )
            return {
                "answer": (
                    f"📌 Disponibles del {cin} al {cout}:\n{lista}\n"
                    "¿Quieres reservar alguna? 😊"
                ),
                "candidatos": disponibles,
            }
        else:
            return {
                "answer": (
                    f"🟥 No hay disponibilidad del {cin} al {cout} "
                    f"para {guests or 'X'} personas.\n"
                    "¿Probar otras fechas? 🙂"
                )
            }

    # Sin fechas → solo pre-filtro por capacidad/precio
    lista = "\n".join(
        [f"- {c['nombre']} · {c['precio_noche']} €/noche" for c in candidatos]
    )
    return {
        "answer": (
            f"Estas son algunas opciones iniciales para {guests or 'X'} personas:\n"
            f"{lista}\n"
            "Indica fechas para comprobar disponibilidad. 📅"
        ),
        "candidatos": candidatos,
    }
