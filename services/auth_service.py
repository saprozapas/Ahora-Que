import psycopg2

from database import get_db_connection
from models.user import User


class AuthService:
    def register(self, user):
        connection = get_db_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public."Usuarios" ("Nombre", "Mail", "Fecha_Nac", "Password_Hash", "Username", "Descripcion")
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user.get_name(),
                        user.get_email(),
                        user.get_birth_date(),
                        user.get_password_hash(),
                        user.get_username(),
                        user.get_Descripcion(),
                    ),
                )
            connection.commit()
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

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
            connection.close()

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
            connection.close()

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
            connection.close()

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
            connection.close()

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
            connection.close()

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
            connection.close()