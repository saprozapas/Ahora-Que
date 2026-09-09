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
                    INSERT INTO public."Usuarios" ("Nombre", "Mail", "Fecha_Nac", "Password_Hash", "Username")
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        user.get_name(),
                        user.get_email(),
                        user.get_birth_date(),
                        user.get_password_hash(),
                        user.get_username(),
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
                        "Password_Hash"
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
                            "Password_Hash"
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
                        result[5]   # Password_Hash
                    ), result[0]  # Id_Usuario

                return None

        except psycopg2.Error:
            raise

        finally:
            connection.close()