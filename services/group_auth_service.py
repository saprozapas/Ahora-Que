from database import get_db_connection
class GroupAuthService:

    def register(self, group):

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(#####CHEQUEAR BIEN LOS NOMBRES DE TABLAS Y ATRIBUTOS, SI NO ESTAN BIEN, CAMBIARLOS POR LOS CORRECTOS#####
            """
            INSERT INTO groups (groupname)
            VALUES (%s)
            """,
            (group.get_name())
        )

        conn.commit()

        cursor.close()
        conn.close()