from flask import current_app
from brevo import Brevo
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)


class MailService:
    def enviar(self, destino, subject, cuerpo):
        """Envía un correo transaccional mediante la API HTTPS de Brevo."""
        if not destino:
            raise ValueError("El destinatario es obligatorio.")
        if not subject:
            raise ValueError("El asunto es obligatorio.")
        if cuerpo is None:
            raise ValueError("El cuerpo del correo es obligatorio.")

        api_key = current_app.config.get("BREVO_API_KEY")
        sender_email = current_app.config.get("BREVO_SENDER_EMAIL")
        sender_name = current_app.config.get("BREVO_SENDER_NAME", "Ahora Qué")
        if not api_key or not sender_email:
            raise RuntimeError("Falta configurar BREVO_API_KEY o BREVO_SENDER_EMAIL.")

        cliente = Brevo(api_key=api_key, timeout=10.0)
        return cliente.transactional_emails.send_transac_email(
            subject=subject,
            text_content=cuerpo,
            sender=SendTransacEmailRequestSender(
                name=sender_name,
                email=sender_email,
            ),
            to=[SendTransacEmailRequestToItem(email=destino)],
            request_options={"timeout_in_seconds": 10, "max_retries": 0},
        )
