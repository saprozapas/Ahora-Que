"""Foto de perfil: uno de los 5 avatares genéricos o una imagen subida desde el dispositivo.

La imagen subida llega ya recortada en cuadrado y achicada por el navegador (JPEG de ~320 px); acá solo se valida
que sea un JPEG y que pese poco, y se guarda en la base igual que las fotos de las publicaciones.
"""

import threading
import time

import psycopg2

from database import get_db_connection, release_db_connection

CANTIDAD_PRESETS = 5
MAX_BYTES = 150 * 1024


# Versiones de las fotos de todos (id -> número), para mostrar la foto de cualquiera en listas sin una consulta por persona.
# Dura pocos segundos y se renueva sola; al cambiar una foto se invalida de inmediato.
_VERSIONES = {"hasta": 0.0, "datos": {}}
_CANDADO = threading.Lock()
_VIGENCIA_S = 30


class AvatarError(Exception):
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.codigo = codigo


class AvatarService:

    @staticmethod
    def _version(fila):
        return int(fila.timestamp()) if fila else None

    @classmethod
    def versiones(cls):
        """{id (texto): versión} de todos los que eligieron foto. Si la base falla, devuelve lo último que se supo."""
        with _CANDADO:
            if time.monotonic() < _VERSIONES["hasta"]:
                return _VERSIONES["datos"]
        connection = None
        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute('SELECT "Id_Usuario"::text, EXTRACT(EPOCH FROM "Actualizada_En")::bigint FROM public."Usuario_Avatar"')
                datos = {fila[0]: int(fila[1]) for fila in cursor.fetchall() if fila[1]}
        except Exception as e:
            print(f"No se pudieron leer las fotos de perfil: {e}")
            return _VERSIONES["datos"]
        finally:
            if connection is not None:
                release_db_connection(connection)
        with _CANDADO:
            _VERSIONES["datos"] = datos
            _VERSIONES["hasta"] = time.monotonic() + _VIGENCIA_S
        return datos

    @classmethod
    def version_de(cls, user_id):
        return cls.versiones().get(str(user_id)) if user_id else None

    @staticmethod
    def invalidar():
        with _CANDADO:
            _VERSIONES["hasta"] = 0.0

    def obtener(self, user_id):
        """{"tipo", "preset", "datos", "version"} o None si el usuario no eligió foto."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT "Tipo", "Preset", "Datos", "Actualizada_En" FROM public."Usuario_Avatar" WHERE "Id_Usuario"::text = %s',
                    (str(user_id),),
                )
                fila = cursor.fetchone()
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)
        if fila is None:
            return None
        return {"tipo": fila[0], "preset": fila[1], "datos": bytes(fila[2]) if fila[2] is not None else None, "version": self._version(fila[3])}

    def version(self, user_id):
        """Número que cambia cada vez que cambia la foto (para que el navegador no use una vieja), o None."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT "Actualizada_En" FROM public."Usuario_Avatar" WHERE "Id_Usuario"::text = %s', (str(user_id),))
                fila = cursor.fetchone()
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)
        return self._version(fila[0]) if fila else None

    def _guardar(self, user_id, tipo, preset, datos):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public."Usuario_Avatar" ("Id_Usuario", "Tipo", "Preset", "Datos", "Actualizada_En")
                    VALUES (%s, %s, %s, %s, now())
                    ON CONFLICT ("Id_Usuario")
                    DO UPDATE SET "Tipo" = EXCLUDED."Tipo", "Preset" = EXCLUDED."Preset",
                                  "Datos" = EXCLUDED."Datos", "Actualizada_En" = now()
                    RETURNING "Actualizada_En"
                    """,
                    (user_id, tipo, preset, psycopg2.Binary(datos) if datos is not None else None),
                )
                fila = cursor.fetchone()
            connection.commit()
            self.invalidar()
            return self._version(fila[0])
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def elegir_preset(self, user_id, preset):
        try:
            preset = int(preset)
        except (TypeError, ValueError):
            raise AvatarError("Ese avatar no existe.")
        if not 1 <= preset <= CANTIDAD_PRESETS:
            raise AvatarError("Ese avatar no existe.")
        return self._guardar(user_id, "preset", preset, None)

    def subir_foto(self, user_id, datos):
        if not datos or len(datos) > MAX_BYTES:
            raise AvatarError("La foto pesa demasiado. Probá con otra.", 413)
        if not datos.startswith(b"\xff\xd8\xff"):
            raise AvatarError("La foto tiene que ser una imagen válida.")
        return self._guardar(user_id, "foto", None, datos)

    def quitar(self, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM public."Usuario_Avatar" WHERE "Id_Usuario"::text = %s', (str(user_id),))
            connection.commit()
            self.invalidar()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)
