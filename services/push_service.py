"""Persistencia de suscripciones y envío de Web Push."""

import json
import base64
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from flask import current_app

from database import get_db_connection, release_db_connection


class PushService:
    def guardar_suscripcion(self, user_id, suscripcion):
        endpoint = suscripcion.get("endpoint")
        keys = suscripcion.get("keys") or {}
        p256dh, auth = keys.get("p256dh"), keys.get("auth")
        if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            raise ValueError("El endpoint de push no es válido.")
        if (len(endpoint) > 2048 or not isinstance(p256dh, str) or not isinstance(auth, str)
                or len(p256dh) > 512 or len(auth) > 512):
            raise ValueError("Faltan datos de la suscripción push.")

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''INSERT INTO public."Notificacion_Push_Suscripcion"
                       ("Id_Usuario", "Endpoint", "P256dh", "Auth", "Activa", "Actualizada_En")
                       VALUES (%s, %s, %s, %s, true, now())
                       ON CONFLICT ("Endpoint") DO UPDATE SET
                         "Id_Usuario" = EXCLUDED."Id_Usuario",
                         "P256dh" = EXCLUDED."P256dh",
                         "Auth" = EXCLUDED."Auth",
                         "Activa" = true,
                         "Actualizada_En" = now()''',
                    (user_id, endpoint, p256dh, auth),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def eliminar_suscripcion(self, user_id, endpoint):
        if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            raise ValueError("El endpoint de push no es válido.")
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''DELETE FROM public."Notificacion_Push_Suscripcion"
                       WHERE "Id_Usuario" = %s AND "Endpoint" = %s''',
                    (user_id, endpoint),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def enviar_a_usuario(self, user_id, titulo, cuerpo, url="/dashboard"):
        clave_privada = current_app.config.get("VAPID_PRIVATE_KEY")
        if not clave_privada:
            current_app.logger.error("No se envió Web Push: falta configurar VAPID_PRIVATE_KEY.")
            return 0

        # En desarrollo se admite una ruta PEM; en servicios como Render, donde
        # no hay disco persistente, la variable puede contener el PEM o su base64.
        if isinstance(clave_privada, str):
            if "-----BEGIN" in clave_privada:
                pem = clave_privada.replace("\\n", "\n").encode("utf-8")
                clave_privada = self._pem_a_clave_vapid(pem)
            else:
                try:
                    es_archivo = Path(clave_privada).is_file()
                except OSError:
                    es_archivo = False
                if not es_archivo:
                    try:
                        contenido = base64.b64decode(
                            clave_privada + "=" * (-len(clave_privada) % 4),
                            altchars=b"-_",
                            validate=True,
                        )
                        if b"-----BEGIN" in contenido:
                            clave_privada = self._pem_a_clave_vapid(contenido)
                        else:
                            # pywebpush recibe DER en base64 URL-safe como str,
                            # no los bytes decodificados.
                            clave_privada = base64.urlsafe_b64encode(contenido).rstrip(b"=").decode("ascii")
                    except (ValueError, TypeError, UnicodeEncodeError):
                        current_app.logger.error(
                            "VAPID_PRIVATE_KEY debe ser una ruta PEM existente, PEM o clave DER en base64."
                        )
                        return 0

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT "Endpoint", "P256dh", "Auth"
                       FROM public."Notificacion_Push_Suscripcion"
                       WHERE "Id_Usuario" = %s AND "Activa"''',
                    (user_id,),
                )
                suscripciones = cursor.fetchall()
        finally:
            release_db_connection(conn)

        if not suscripciones:
            current_app.logger.info(
                "No hay suscripciones push activas para user_id=%s.", user_id
            )
            return 0

        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            current_app.logger.exception("No está instalado pywebpush; instalá las dependencias del proyecto.")
            return 0

        enviados = 0
        mensaje = json.dumps(
            {"title": titulo, "body": cuerpo, "url": url},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for endpoint, p256dh, auth in suscripciones:
            try:
                headers = None
                if (urlsplit(endpoint).hostname or "").endswith(".notify.windows.com"):
                    # WNS, usado por Microsoft Edge en Windows, requiere el formato toast XML.
                    mensaje_endpoint = (
                        "<toast><visual><binding template=\"ToastGeneric\">"
                        f"<text>{escape(titulo)}</text><text>{escape(cuerpo)}</text>"
                        "</binding></visual></toast>"
                    )
                    headers = {"X-WNS-Type": "wns/toast", "TTL": "600", "Content-Type": "text/xml"}
                else:
                    mensaje_endpoint = mensaje
                webpush(
                    subscription_info={
                        "endpoint": endpoint,
                        "keys": {"p256dh": p256dh, "auth": auth},
                    },
                    data=mensaje_endpoint,
                    vapid_private_key=clave_privada,
                    vapid_claims={"sub": current_app.config["VAPID_SUBJECT"]},
                    ttl=60 * 60,
                    timeout=10,
                    headers=headers,
                )
                enviados += 1
            except WebPushException as error:
                status = getattr(getattr(error, "response", None), "status_code", None)
                if status in (404, 410):
                    self.eliminar_suscripcion(user_id, endpoint)
                else:
                    current_app.logger.exception("Falló el envío Web Push (status=%s).", status)
            except Exception:
                current_app.logger.exception("Falló el envío Web Push.")
        current_app.logger.info(
            "Envío Web Push terminado para user_id=%s: suscripciones=%s, enviados=%s.",
            user_id,
            len(suscripciones),
            enviados,
        )
        return enviados

    @staticmethod
    def _pem_a_clave_vapid(pem):
        """Convierte un PEM a DER base64 URL-safe, formato aceptado por pywebpush."""
        from cryptography.hazmat.primitives import serialization

        clave = serialization.load_pem_private_key(pem, password=None)
        der = clave.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return base64.urlsafe_b64encode(der).rstrip(b"=").decode("ascii")
