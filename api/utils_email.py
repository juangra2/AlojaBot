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

    html = f"""\
<html>
  <body style="margin:0; padding:0; background-color:#f4f4f7; font-family: Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7; padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; max-width:600px; width:100%; border:1px solid #e3e6ec;">
            <!-- Cabecera -->
            <tr>
              <td style="background-color:#1f3a5f; padding:28px 32px;">
                <span style="font-size:22px; font-weight:bold; color:#ffffff; letter-spacing:0.5px;">AlojaBot</span>
                <div style="font-size:13px; color:#cdd7e4; margin-top:4px;">Cobisa · Toledo</div>
              </td>
            </tr>
            <!-- Saludo -->
            <tr>
              <td style="padding:28px 32px 12px 32px;">
                <p style="margin:0 0 8px 0; font-size:16px; color:#222222;">Hola {cliente_nombre or ''},</p>
                <p style="margin:0; font-size:15px; color:#444444; line-height:1.5;">{saludo}</p>
              </td>
            </tr>
            <!-- Tarjeta de detalles -->
            <tr>
              <td style="padding:12px 32px 8px 32px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8f9fb; border:1px solid #e3e6ec;">
                  <tr>
                    <td style="padding:16px 20px; font-size:14px; color:#666666; border-bottom:1px solid #e3e6ec;">Reserva</td>
                    <td style="padding:16px 20px; font-size:14px; color:#1f3a5f; font-weight:bold; text-align:right; border-bottom:1px solid #e3e6ec;">#{reserva_id}</td>
                  </tr>
                  <tr>
                    <td style="padding:14px 20px; font-size:14px; color:#666666; border-bottom:1px solid #e3e6ec;">Alojamiento</td>
                    <td style="padding:14px 20px; font-size:14px; color:#222222; text-align:right; border-bottom:1px solid #e3e6ec;">{nombre_alojamiento}</td>
                  </tr>
                  <tr>
                    <td style="padding:14px 20px; font-size:14px; color:#666666; border-bottom:1px solid #e3e6ec;">Check-in</td>
                    <td style="padding:14px 20px; font-size:14px; color:#222222; text-align:right; border-bottom:1px solid #e3e6ec;">{check_in}</td>
                  </tr>
                  <tr>
                    <td style="padding:14px 20px; font-size:14px; color:#666666; border-bottom:1px solid #e3e6ec;">Check-out</td>
                    <td style="padding:14px 20px; font-size:14px; color:#222222; text-align:right; border-bottom:1px solid #e3e6ec;">{check_out}</td>
                  </tr>
                  <tr>
                    <td style="padding:14px 20px; font-size:14px; color:#666666; border-bottom:1px solid #e3e6ec;">Noches</td>
                    <td style="padding:14px 20px; font-size:14px; color:#222222; text-align:right; border-bottom:1px solid #e3e6ec;">{noches}</td>
                  </tr>
                  <tr>
                    <td style="padding:14px 20px; font-size:14px; color:#666666; border-bottom:1px solid #e3e6ec;">Huéspedes</td>
                    <td style="padding:14px 20px; font-size:14px; color:#222222; text-align:right; border-bottom:1px solid #e3e6ec;">{huespedes}</td>
                  </tr>
                  <tr>
                    <td style="padding:14px 20px; font-size:14px; color:#666666; border-bottom:1px solid #e3e6ec;">Precio base/noche</td>
                    <td style="padding:14px 20px; font-size:14px; color:#222222; text-align:right; border-bottom:1px solid #e3e6ec;">{precio_noche_base} €</td>
                  </tr>
                  <tr>
                    <td style="padding:14px 20px; font-size:14px; color:#666666; border-bottom:1px solid #e3e6ec;">Descuento aplicado</td>
                    <td style="padding:14px 20px; font-size:14px; color:#1f8a4c; font-weight:bold; text-align:right; border-bottom:1px solid #e3e6ec;">{descuento_txt}</td>
                  </tr>
                  <tr>
                    <td style="padding:14px 20px; font-size:14px; color:#666666; border-bottom:1px solid #e3e6ec;">Precio final/noche</td>
                    <td style="padding:14px 20px; font-size:14px; color:#222222; text-align:right; border-bottom:1px solid #e3e6ec;">{precio_noche_final} €</td>
                  </tr>
                  <tr>
                    <td style="padding:16px 20px; font-size:15px; color:#1f3a5f; font-weight:bold;">Total</td>
                    <td style="padding:16px 20px; font-size:18px; color:#1f3a5f; font-weight:bold; text-align:right;">{precio_total} €</td>
                  </tr>
                </table>
              </td>
            </tr>
            <!-- Despedida -->
            <tr>
              <td style="padding:20px 32px 28px 32px;">
                <p style="margin:0; font-size:15px; color:#444444;">¡Esperamos darte la bienvenida pronto! 🙂</p>
              </td>
            </tr>
            <!-- Pie de página -->
            <tr>
              <td style="background-color:#f4f4f7; padding:18px 32px; border-top:1px solid #e3e6ec;">
                <p style="margin:0; font-size:12px; color:#9a9a9a; text-align:center;">AlojaBot · Cobisa, Toledo · Correo automático de confirmación</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
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
