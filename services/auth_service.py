import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import psycopg2

from database import get_db_connection, release_db_connection
from models.user import User
from services.group_auth_service import GroupAuthService


class AuthService:
    MAX_INTENTOS_LOGIN = 5
    VENTANA_LOGIN_MINUTOS = 30

    @staticmethod
    def _clave_login(username_or_email):
        """No guardar el identificador ingresado en claro en la tabla de intentos."""
        identificador = (username_or_email or "").strip().casefold()
        return hashlib.sha256(identificador.encode("utf-8")).hexdigest()

    def registrar_intento_login(self, username_or_email, user_id=None):
        """Reserva un intento de login de forma atómica; retorna si fue permitido."""
        clave = self._clave_login(username_or_email)
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN")
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (clave,),
                )
                cursor.execute(
                    '''DELETE FROM public."Intentos_Login"
                       WHERE "Creado_En" < NOW() - (%s * INTERVAL '1 minute')''',
                    (self.VENTANA_LOGIN_MINUTOS,),
                )
                cursor.execute(
                    '''SELECT COUNT(*) FROM public."Intentos_Login"
                       WHERE "Clave_Identificador" = %s
                         AND "Creado_En" >= NOW() - (%s * INTERVAL '1 minute')''',
                    (clave, self.VENTANA_LOGIN_MINUTOS),
                )
                cantidad = cursor.fetchone()[0]
                if cantidad >= self.MAX_INTENTOS_LOGIN:
                    connection.commit()
                    return False
                cursor.execute(
                    '''INSERT INTO public."Intentos_Login"
                       ("Clave_Identificador", "Id_Usuario") VALUES (%s, %s)''',
                    (clave, user_id),
                )
            connection.commit()
            return True
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def create_pending_registration(self, user, confirmation_code_hash):
        """Guarda los datos de registro temporalmente, sin crear aún el usuario activo."""
        user_id = uuid4()
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM public."Confirmaciones_Registro" WHERE "Expira_En" <= NOW()'
                )
                cursor.execute(
                    '''SELECT 1 FROM public."Usuarios"
                       WHERE "Mail" = %s OR "Username" = %s LIMIT 1''',
                    (user.get_email(), user.get_username()),
                )
                if cursor.fetchone():
                    raise ValueError("El mail o el nombre de usuario ya está en uso.")
                cursor.execute(
                    """
                    INSERT INTO public."Confirmaciones_Registro"
                        ("Id_Usuario", "Codigo_Hash", "Nombre", "Mail", "Fecha_Nac",
                         "Password_Hash", "Username", "Descripcion", "Expira_En")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW() + INTERVAL '24 hours')
                    """,
                    (
                        str(user_id),
                        confirmation_code_hash,
                        user.get_name(),
                        user.get_email(),
                        user.get_birth_date(),
                        user.get_password_hash(),
                        user.get_username(),
                        user.get_descripcion(),
                    ),
                )
            connection.commit()
            return user_id
        except ValueError:
            connection.rollback()
            raise
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def discard_pending_registration(self, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM public."Confirmaciones_Registro" WHERE "Id_Usuario" = %s',
                    (str(user_id),),
                )
            connection.commit()
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def discard_pending_by_code_hash(self, confirmation_code_hash):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM public."Confirmaciones_Registro" WHERE "Codigo_Hash" = %s',
                    (confirmation_code_hash,),
                )
            connection.commit()
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def confirm_registration(self, confirmation_code_hash):
        """Consume un código válido y crea el usuario en la tabla Usuarios."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN")
                cursor.execute(
                    '''SELECT "Id_Usuario", "Nombre", "Mail", "Fecha_Nac", "Password_Hash",
                              "Username", "Descripcion", "Expira_En"
                       FROM public."Confirmaciones_Registro"
                       WHERE "Codigo_Hash" = %s FOR UPDATE''',
                    (confirmation_code_hash,),
                )
                pending = cursor.fetchone()
                if not pending:
                    connection.commit()
                    return "invalido", None

                user_id, name, email, birth_date, password_hash, username, description, expires_at = pending
                if expires_at <= datetime.now(timezone.utc):
                    cursor.execute(
                        'DELETE FROM public."Confirmaciones_Registro" WHERE "Id_Usuario" = %s',
                        (str(user_id),),
                    )
                    connection.commit()
                    return "expirado", None

                cursor.execute(
                    '''INSERT INTO public."Usuarios"
                       ("Id_Usuario", "Nombre", "Mail", "Fecha_Nac", "Password_Hash", "Username", "Descripcion")
                       VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                    (str(user_id), name, email, birth_date, password_hash, username, description),
                )
                cursor.execute(
                    'DELETE FROM public."Confirmaciones_Registro" WHERE "Id_Usuario" = %s',
                    (str(user_id),),
                )
            connection.commit()
            return "confirmado", user_id
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def get_registration_status(self, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT 1 FROM public."Usuarios" WHERE "Id_Usuario" = %s',
                    (str(user_id),),
                )
                if cursor.fetchone():
                    return "confirmado"
                cursor.execute(
                    '''SELECT "Expira_En" FROM public."Confirmaciones_Registro"
                       WHERE "Id_Usuario" = %s''',
                    (str(user_id),),
                )
                pending = cursor.fetchone()
                if not pending:
                    return "invalido"
                if pending[0] <= datetime.now(timezone.utc):
                    return "expirado"
                return "pendiente"
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    def getUserAndId(self, username_or_email):
        connection = get_db_connection()

        try:
            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT
                        "Id_Usuario",
                        "Nombre",
                        "Fecha_Nac",
                        "Username",
                        "Mail",
                        "Password_Hash",
                        "Descripcion"
                    FROM public."Usuarios"
                    WHERE "Username" = %s
                    """,
                    (username_or_email,),
                )

                result = cursor.fetchone()

                # Si no encontró por username, busca por mail
                if result is None:
                    cursor.execute(
                        """
                        SELECT
                            "Id_Usuario",
                            "Nombre",
                            "Fecha_Nac",
                            "Username",
                            "Mail",
                            "Password_Hash",
                            "Descripcion"
                        FROM public."Usuarios"
                        WHERE "Mail" = %s
                        """,
                        (username_or_email,),
                    )

                    result = cursor.fetchone()

                # Si encontró por username O por mail
                if result:
                    return User(
                        result[1],  # Nombre
                        result[2],  # Fecha_Nac
                        result[3],  # Username
                        result[4],  # Mail
                        result[5],  # Password_Hash
                        result[6],   # Descripcion
                    ), result[0]  # Id_Usuario

                return None

        except psycopg2.Error:
            raise

        finally:
            release_db_connection(connection)

    def update_name(self, user_id, name):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE public."Usuarios" SET "Nombre" = %s WHERE "Id_Usuario" = %s',
                    (name, user_id),
                )
            connection.commit()
            return True, None
        except psycopg2.Error:
            connection.rollback()
            return False, "Hubo un error al guardar el nombre. Intentá de nuevo."
        finally:
            release_db_connection(connection)

    def update_username(self, user_id, username):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT "Id_Usuario" FROM public."Usuarios" WHERE "Username" = %s AND "Id_Usuario" != %s',
                    (username, user_id),
                )
                if cursor.fetchone():
                    return False, "El nombre de usuario ya está en uso."

                cursor.execute(
                    'UPDATE public."Usuarios" SET "Username" = %s WHERE "Id_Usuario" = %s',
                    (username, user_id),
                )
            connection.commit()
            return True, None
        except psycopg2.errors.UniqueViolation:
            connection.rollback()
            return False, "El nombre de usuario ya está en uso."
        except psycopg2.Error:
            connection.rollback()
            return False, "Hubo un error al guardar el usuario. Intentá de nuevo."
        finally:
            release_db_connection(connection)

    def get_password_hash_by_id(self, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT "Password_Hash" FROM public."Usuarios" WHERE "Id_Usuario" = %s',
                    (user_id,),
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    def update_password(self, user_id, password_hash):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE public."Usuarios" SET "Password_Hash" = %s WHERE "Id_Usuario" = %s',
                    (password_hash, user_id),
                )
            connection.commit()
            return True, None
        except psycopg2.Error:
            connection.rollback()
            return False, "Hubo un error al guardar la contraseña. Intentá de nuevo."
        finally:
            release_db_connection(connection)

    def update_descripcion(self, user_id, descripcion):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE public."Usuarios" SET "Descripcion" = %s WHERE "Id_Usuario" = %s',
                    (descripcion, user_id),
                )
            connection.commit()
            return True, None
        except psycopg2.Error:
            connection.rollback()
            return False, "Hubo un error al guardar la descripción. Intentá de nuevo."
        finally:
            release_db_connection(connection)

    # Borrado de cuenta. Social, deudas, cuenta bancaria, sugerencias y ubicaciones
    # se van solas por ON DELETE CASCADE al borrar el usuario; lo demás se limpia acá.
    _BORRAR_CUENTA = (
        # Ideas personales (sin grupo): se borran enteras. Planes de grupo: quedan sin creador.
        'DELETE FROM public."Usuario-Plan" WHERE "Plan_id" IN (SELECT "id_Plan" FROM public."Plan" WHERE "Creado_Por" = %(u)s AND "Grupo_id" IS NULL)',
        'DELETE FROM public."Plan" WHERE "Creado_Por" = %(u)s AND "Grupo_id" IS NULL',
        'UPDATE public."Plan" SET "Creado_Por" = NULL WHERE "Creado_Por" = %(u)s',
        'UPDATE public."Grupos" SET "Creado_Por" = NULL WHERE "Creado_Por" = %(u)s',
        'UPDATE public."Grupo_Encuesta" SET "Creado_Por" = NULL WHERE "Creado_Por" = %(u)s',
        'DELETE FROM public."Usuario-Plan" WHERE "Usuario_id" = %(u)s',
        'DELETE FROM public."Plan_Voto" WHERE "Id_Usuario" = %(u)s',
        'DELETE FROM public."Plan_Horario_Voto" WHERE "Id_Usuario" = %(u)s OR "Id_Horario" IN (SELECT "Id_Horario" FROM public."Plan_Horario" WHERE "Propuesto_Por" = %(u)s)',
        'DELETE FROM public."Plan_Horario" WHERE "Propuesto_Por" = %(u)s',
        'DELETE FROM public."Grupo_Encuesta_Voto" WHERE "Id_Usuario" = %(u)s',
        'DELETE FROM public."Grupo_Encuesta_Respuesta" WHERE "Id_Usuario" = %(u)s',
        'DELETE FROM public."Grupo_Encuesta_Disponibilidad" WHERE "Id_Usuario" = %(u)s',
        'DELETE FROM public."gasto_detalle" WHERE "usuario_id" = %(u)s OR "gasto_id" IN (SELECT "id_gasto" FROM public."gasto" WHERE "pagado_por" = %(u)s)',
        'DELETE FROM public."gasto" WHERE "pagado_por" = %(u)s',
        'DELETE FROM public."Invitaciones" WHERE "Id_Usuario" = %(u)s',
        'DELETE FROM public."Amistades" WHERE "Id_Usuario1" = %(u)s OR "Id_Usuario2" = %(u)s',
        'DELETE FROM public."Solicitudes_Amistad" WHERE "Id_Solicitante" = %(u)s OR "Id_Destinatario" = %(u)s',
        'DELETE FROM public."Mensajes" WHERE "Id_Usuario" = %(u)s',
        # Conversaciones: la del bot y las privadas se borran (con sus mensajes, por CASCADE).
        'DELETE FROM public."Conversacion" c WHERE c."Id_Usuario_A" = %(u)s OR c."Id_Usuario_B" = %(u)s OR (c."Tipo" = \'bot\' AND EXISTS (SELECT 1 FROM public."Conversacion_Miembro" cm WHERE cm."Id_Conversacion" = c."Id_Conversacion" AND cm."Id_Usuario" = %(u)s))',
        'DELETE FROM public."Mensaje" WHERE "Id_Remitente" = %(u)s',
        'DELETE FROM public."Conversacion_Miembro" WHERE "Id_Usuario" = %(u)s',
        'DELETE FROM public."Intentos_Login" WHERE "Id_Usuario" = %(u)s',
        'DELETE FROM public."Usuarios" WHERE "Id_Usuario" = %(u)s',
    )

    def delete_user(self, user_id):
        """Borra la cuenta y todo lo suyo. Una sola transacción: si algo falla, no se borra nada."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT "Id_Grupo" FROM public."Usuario-Grupo" WHERE "Id_Usuario" = %s', (user_id,))
                for (grupo,) in cursor.fetchall():
                    GroupAuthService.salir_del_grupo(cursor, grupo, user_id)  # sucesión de admin incluida
                cursor.execute(";\n".join(self._BORRAR_CUENTA), {"u": str(user_id)})
            connection.commit()
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Olvidé mi contraseña ---------------------------------------------

    def crear_codigo_recuperacion(self, user_id, codigo_hash):
        """Un solo código vigente por usuario: pedir otro invalida el anterior. Vence en 1 hora."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    '''INSERT INTO public."Recuperacion_Contrasena" ("Id_Usuario", "Codigo_Hash", "Expira_En")
                       VALUES (%s, %s, NOW() + INTERVAL '1 hour')
                       ON CONFLICT ("Id_Usuario") DO UPDATE
                       SET "Codigo_Hash" = EXCLUDED."Codigo_Hash", "Expira_En" = EXCLUDED."Expira_En"''',
                    (user_id, codigo_hash),
                )
            connection.commit()
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def codigo_recuperacion_valido(self, codigo_hash):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT 1 FROM public."Recuperacion_Contrasena" WHERE "Codigo_Hash" = %s AND "Expira_En" > NOW()',
                    (codigo_hash,),
                )
                return cursor.fetchone() is not None
        finally:
            release_db_connection(connection)

    def restablecer_contrasena(self, codigo_hash, password_hash):
        """Cambia la contraseña y gasta el código en una sola sentencia (sirve una vez).
        Devuelve False si el código no existe o venció."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    '''WITH usado AS (
                           DELETE FROM public."Recuperacion_Contrasena"
                           WHERE "Codigo_Hash" = %s AND "Expira_En" > NOW()
                           RETURNING "Id_Usuario")
                       UPDATE public."Usuarios" u SET "Password_Hash" = %s
                       FROM usado WHERE u."Id_Usuario" = usado."Id_Usuario"''',
                    (codigo_hash, password_hash),
                )
                cambiado = cursor.rowcount == 1
            connection.commit()
            return cambiado
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)
