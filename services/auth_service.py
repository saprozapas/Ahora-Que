import psycopg2

from database import get_db_connection


class AuthService:
    def register(self, user):
        connection = get_db_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (name, birth_date, username, password)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        user.get_name(),
                        user.get_birth_date(),
                        user.get_username(),
                        user.get_password_hash(),
                    ),
                )
            connection.commit()
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            connection.close()