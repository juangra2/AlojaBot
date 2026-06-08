# api/utils_email.py
from __future__ import annotations

import logging
import os
import smtplib
from datetime import date
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

_SALUDO_BY_LANG = {
    "es": "¡Gracias por tu reserva! Aquí tienes los detalles:",
    "en": "Thank you for your booking! Here are the details:",
    "fr": "Merci pour votre réservation ! Voici les détails :",
    "de": "Vielen Dank für Ihre Buchung! Hier sind die Details:",
    "it": "Grazie per la tua prenotazione! Ecco i dettagli:",
    "pt": "Obrigado pela sua reserva! Aqui estão os detalhes:",
}

_ASUNTO_BY_LANG = {
    "es": "Confirmación de tu reserva #{rid} – AlojaBot",
    "en": "Booking confirmation #{rid} – AlojaBot",
    "fr": "Confirmation de votre réservation n°{rid} – AlojaBot",
    "de": "Buchungsbestätigung Nr. {rid} – AlojaBot",
    "it": "Conferma della prenotazione #{rid} – AlojaBot",
    "pt": "Confirmação da reserva #{rid} – AlojaBot",
}


def enviar_confirmacion_reserva(
    *,
    reserva_id: int,
    nombre_alojamiento: str,
    check_in: date,
    check_out: date,
    huespedes: int,
    precio_noche_base: float,
    descuento_pct: float,
    precio_noche_final: float,
    precio_total: float,
    cliente_nombre: str | None,
    cliente_email: str | None,
    lang: str = "es",
) -> bool:
    """Envía un correo HTML de confirmación. No debe romper la creación de la reserva."""
    if not cliente_email:
        return False

    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    if not sender or not password:
        logger.warning(
            "EMAIL_SENDER/EMAIL_PASSWORD no configurados; no se envía confirmación de la reserva %s.",
            reserva_id,
        )
        return False

    lang = lang if lang in _SALUDO_BY_LANG else "es"
    saludo = _SALUDO_BY_LANG[lang]
    asunto = _ASUNTO_BY_LANG[lang].format(rid=reserva_id)

    noches = max(1, (check_out - check_in).days)
    descuento_txt = f"{round(descuento_pct * 100)}%" if descuento_pct else "0%"

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #222;">
        <h2>AlojaBot</h2>
        <p>Hola {cliente_nombre or ''},</p>
        <p>{saludo}</p>
        <ul>
          <li><strong>Reserva:</strong> #{reserva_id}</li>
          <li><strong>Alojamiento:</strong> {nombre_alojamiento}</li>
          <li><strong>Check-in:</strong> {check_in}</li>
          <li><strong>Check-out:</strong> {check_out}</li>
          <li><strong>Noches:</strong> {noches}</li>
          <li><strong>Huéspedes:</strong> {huespedes}</li>
          <li><strong>Precio base/noche:</strong> {precio_noche_base} €</li>
          <li><strong>Descuento aplicado:</strong> {descuento_txt}</li>
          <li><strong>Precio final/noche:</strong> {precio_noche_final} €</li>
          <li><strong>Total:</strong> {precio_total} €</li>
        </ul>
        <p>¡Esperamos darte la bienvenida pronto! 🙂</p>
      </body>
    </html>
    """

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = asunto
    msg["From"] = sender
    msg["To"] = cliente_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [cliente_email], msg.as_string())
        return True
    except Exception as e:
        logger.warning("No se ha podido enviar la confirmación de la reserva %s: %s", reserva_id, e)
        return False
