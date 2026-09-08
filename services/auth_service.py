from database import get_db_connection
class AuthService:

    def register(self, user):

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(#####CHEQUEAR BIEN LOS NOMBRES DE TABLAS Y ATRIBUTOS, SI NO ESTAN BIEN, CAMBIARLOS POR LOS CORRECTOS#####
            """
            INSERT INTO users (username, password)
            VALUES (%s, %s)
            """,
            (user.get_username(), user.get_password_hash())
        )

        conn.commit()

        cursor.close()
        conn.close()