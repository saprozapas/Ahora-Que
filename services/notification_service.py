from services.mail_service import MailService


class NotificationService:
    """Envía notificaciones usando el canal de correo disponible actualmente."""

    def __init__(self, mail_service=None):
        self.mail_service = mail_service or MailService()

    def enviar(self, destino, subject, cuerpo):
        """Envía una notificación con la misma interfaz que MailService.enviar."""
        return self.mail_service.enviar(destino, subject, cuerpo)
