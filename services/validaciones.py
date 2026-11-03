"""Chequeos de los datos de una cuenta que se hacen en el servidor (el navegador solo avisa, no alcanza)."""

import re

NOMBRE_MAX = 80
USERNAME_MIN = 3
USERNAME_MAX = 50
EMAIL_MAX = 254

# Letras, números y . _ - @ + (algunas cuentas viejas usan su mail como usuario). Sin espacios ni signos de HTML.
_USERNAME = re.compile(r"^[\w.@+\-]+$")
_EMAIL = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']{2,}$")


def validar_nombre(nombre):
    """Mensaje de error, o None si el nombre sirve."""
    nombre = (nombre or "").strip()
    if not nombre:
        return "Escribí tu nombre."
    if len(nombre) > NOMBRE_MAX:
        return f"El nombre puede tener hasta {NOMBRE_MAX} caracteres."
    if re.search(r"[\x00-\x1f\x7f<>]", nombre):
        return "El nombre tiene caracteres que no se pueden usar."
    return None


def validar_username(username):
    username = (username or "").strip()
    if len(username) < USERNAME_MIN:
        return f"El usuario tiene que tener al menos {USERNAME_MIN} caracteres."
    if len(username) > USERNAME_MAX:
        return f"El usuario puede tener hasta {USERNAME_MAX} caracteres."
    if not _USERNAME.match(username):
        return "El usuario solo puede tener letras, números y . _ - @ + (sin espacios)."
    return None


def validar_email(email):
    email = (email or "").strip()
    if len(email) > EMAIL_MAX or not _EMAIL.match(email):
        return "Ingresá un correo electrónico válido."
    return None
