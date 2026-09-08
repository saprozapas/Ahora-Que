import psycopg2

from database import get_db_connection


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