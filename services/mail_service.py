from flask import current_app
from flask_mail import Message


class MailService:
    def enviar(self, destino, subject, cuerpo):
        """Envía un correo de texto usando la configuración Flask-Mail de la app activa."""
        if not destino:
            raise ValueError("El destinatario es obligatorio.")
        if not subject:
            raise ValueError("El asunto es obligatorio.")
        if cuerpo is None:
            raise ValueError("El cuerpo del correo es obligatorio.")

        mensaje = Message(
            subject=subject,
            recipients=[destino],
            body=cuerpo,
        )
        current_app.extensions["mail"].send(mensaje)
