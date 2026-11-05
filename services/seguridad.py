"""Medidas de seguridad generales de la app: cookies, cabeceras y verificación de origen.

Se activa con una sola línea en app.py:  seguridad.instalar(app)

Qué hace:
  1. Cookie de sesión: HttpOnly (JavaScript no la puede leer), SameSite=Lax (no viaja en pedidos que
     disparan otros sitios) y Secure (solo por HTTPS) cuando la app corre en Render.
  2. Verificación de origen (defensa contra CSRF): un POST/PUT/PATCH/DELETE solo se acepta si viene de
     esta misma página. Los navegadores mandan el encabezado Origin (o Referer) en esos pedidos, y un sitio
     malicioso no puede falsificarlo. Si no viene ninguno, el pedido no lo mandó un navegador desde otra
     página, así que no es un ataque CSRF y se deja pasar.
  3. Cabeceras de seguridad en todas las respuestas.
  4. Detrás del proxy de Render, ProxyFix hace que Flask sepa que la conexión original fue HTTPS
     (así request.is_secure da True).
  5. Los links de los mails (base_publica / url_publica) salen de PUBLIC_BASE_URL y no del Host de la petición.
"""
import hashlib
import os
from urllib.parse import urlparse

from flask import render_template, request, url_for

_METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def en_produccion():
    """True en Render (define RENDER) o si se fuerza con COOKIE_SECURE=1 en el .env."""
    return bool(os.environ.get("RENDER")) or os.environ.get("COOKIE_SECURE") == "1"


def huella_contrasena(password_hash):
    """Una huella corta de la contraseña vigente. Va dentro de la cookie de sesión: si la contraseña cambia
    (restablecerla, cambiarla) o la cuenta se borra, las sesiones que quedaron abiertas dejan de valer."""
    return hashlib.sha256((password_hash or "").encode("utf-8")).hexdigest()[:16]


def base_publica():
    """La dirección pública de la app para los links de los mails. Sale de PUBLIC_BASE_URL (así un Host o
    X-Forwarded-Host falsificado no cambia a dónde apunta un link con un token); si falta, se usa la de la petición."""
    configurada = (os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    return configurada or request.url_root.rstrip("/")


def url_publica(endpoint, **valores):
    """Como url_for(..., _external=True), pero con la dirección de base_publica()."""
    return base_publica() + url_for(endpoint, **valores)


def instalar(app):
    if os.environ.get("RENDER") and not os.environ.get("PUBLIC_BASE_URL"):
        print("AVISO: falta PUBLIC_BASE_URL; los links de los mails se arman con el host de la petición.")
    if os.environ.get("RENDER"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        # Solo se confía en el protocolo y el host que informa el proxy (no en la IP: no la usamos).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=en_produccion(),
    )

    @app.before_request
    def _verificar_origen():
        if request.method in _METODOS_SEGUROS:
            return None
        origen = request.headers.get("Origin") or request.headers.get("Referer")
        if not origen:
            return None
        if urlparse(origen).netloc == request.host:
            return None
        return render_template(
            "error.html",
            codigo=403,
            titulo="No pudimos verificar el origen del pedido.",
            detalle="Volvé a abrir la página desde Ahora Qué e intentá de nuevo.",
        ), 403

    @app.after_request
    def _cabeceras_de_seguridad(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        # Solo se pide la ubicación desde nuestra propia página; cámara y micrófono no se usan.
        response.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
        # CSP mínima: no rompe los scripts propios y bloquea que otros sitios embeban la app
        # o inyecten <base>/<object>. Una CSP completa pide antes sacar los scripts inline.
        response.headers.setdefault(
            "Content-Security-Policy", "frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
        )
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=15552000")
        return response
