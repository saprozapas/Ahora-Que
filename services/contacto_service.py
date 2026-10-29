"""Formulario de contacto: valida, limita abusos y manda el mensaje por mail al equipo.

El mensaje NO se guarda en la base de datos: solo se envía por correo (Brevo) a CONTACTO_EMAIL
(por defecto ahora.que.app@gmail.com). Así no se acumulan datos personales que después haya que gestionar.
"""
import os
import re
import threading
import time

from services.mail_service import MailService

DESTINO_POR_DEFECTO = "ahora.que.app@gmail.com"

_VENTANA_SEGUNDOS = 3600
_MAX_POR_EMAIL = 3      # mensajes por hora desde el mismo correo
_MAX_EN_TOTAL = 30      # mensajes por hora en toda la app (protege la cuota de Brevo y la casilla)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactoInvalido(ValueError):
    pass


class ContactoLimitado(RuntimeError):
    pass


class ContactoService:
    def __init__(self):
        self._lock = threading.Lock()
        self._envios = []  # [(momento, email)]

    def _registrar_o_limitar(self, email):
        ahora = time.monotonic()
        with self._lock:
            self._envios = [(t, e) for t, e in self._envios if ahora - t < _VENTANA_SEGUNDOS]
            if len(self._envios) >= _MAX_EN_TOTAL or sum(1 for _, e in self._envios if e == email) >= _MAX_POR_EMAIL:
                raise ContactoLimitado()
            self._envios.append((ahora, email))

    def enviar(self, nombre, email, mensaje):
        nombre = " ".join((nombre or "").split())  # sin saltos de línea: va en el asunto
        email = (email or "").strip().lower()
        mensaje = (mensaje or "").strip()

        if not nombre or len(nombre) > 80:
            raise ContactoInvalido("Escribí tu nombre (hasta 80 caracteres).")
        if len(email) > 254 or not _EMAIL.match(email):
            raise ContactoInvalido("Ingresá un correo válido para poder responderte.")
        if len(mensaje) < 10:
            raise ContactoInvalido("Contanos un poco más: el mensaje es muy corto.")
        if len(mensaje) > 3000:
            raise ContactoInvalido("El mensaje es muy largo (máximo 3000 caracteres).")

        self._registrar_o_limitar(email)

        destino = os.environ.get("CONTACTO_EMAIL", DESTINO_POR_DEFECTO)
        cuerpo = f"Nombre: {nombre}\nCorreo para responder: {email}\n\n{mensaje}"
        MailService().enviar(destino, f"Contacto desde Ahora Qué — {nombre}", cuerpo)
