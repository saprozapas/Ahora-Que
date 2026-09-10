from database import get_db_connection
class GroupAuthService:

    def register(self, group):

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(#####CHEQUEAR BIEN LOS NOMBRES DE TABLAS Y ATRIBUTOS, SI NO ESTAN BIEN, CAMBIARLOS POR LOS CORRECTOS#####
            """
            INSERT INTO public."Grupos" (Creado_Por, Nombre, Descripcion)
            VALUES (%s, %s, %s)
            """,
            (group.get_user_id(), group.get_name(), group.get_descripcion())
        )

        conn.commit()

        cursor.close()
        conn.close()