"""La guía de bienvenida es solo para cuentas nuevas y se muestra una única vez.

Se acuerda en una cookie del navegador donde se creó la cuenta (no hace falta tocar la base): al registrarse se
guarda un valor atado al mail; mientras la cookie coincida con el mail de quien está logueado, el Inicio ofrece la
guía. Al terminarla (o al omitirla) la cookie se borra y no vuelve. Otra persona en el mismo navegador, o una
cuenta vieja, no la ve nunca."""

import hashlib

COOKIE = "aq_guia"
VIGENCIA_SEGUNDOS = 30 * 24 * 3600


def token(mail):
    return hashlib.sha256(("guia:" + (mail or "").strip().lower()).encode("utf-8")).hexdigest()[:24]


def es_guia_pendiente(cookies, mail):
    return bool(mail) and cookies.get(COOKIE) == token(mail)
