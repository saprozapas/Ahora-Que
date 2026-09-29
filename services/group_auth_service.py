from database import get_db_connection, release_db_connection

class GroupAuthService:

    def register(self, group, user_id):

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO public."Grupos" ("Creado_Por", "Nombre", "Descripcion")
            VALUES (%s, %s, %s)
            """,
            (user_id, group.get_name(), group.get_description())
        )        
        # EL USUARIO SE AGREGA COMO INTEGRANTE DEL GRUPO AUTOMATICAMENTE POR UNA AUTOMATIZACION EN SUPABASE
        conn.commit()

        cursor.close()
        release_db_connection(conn)

    def add_user(self, user_id, group_id, conn=None):
        if conn is None:
            conn = get_db_connection()
        cursor = conn.cursor()
    
        cursor.execute(
            """
            INSERT INTO public."Usuario-Grupo" ("Usuario_Id", "Grupo_Id")
            VALUES (%s, %s)
            """,
            (user_id, group_id)
        )
        

        conn.commit()

        cursor.close()
        release_db_connection(conn)

    def is_user_in_group(self, user_id, group_id):
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM public."Usuario-Grupo"
                WHERE "Id_Usuario" = %s
                AND "Id_Grupo" = %s
            )
            """,
            (user_id, group_id)
        )

        result = cursor.fetchone()

        cursor.close()
        release_db_connection(conn)

        return result[0]

    def update_group(self, group_id, name, description):
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE public."Grupos"
            SET "Nombre" = %s, "Descripcion" = %s
            WHERE "Id_Grupo" = %s
            """,
            (name, description, group_id)
        )

        conn.commit()

        cursor.close()
        release_db_connection(conn)

    def delete_user_from_group(self, group_id, user_id):
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM public."Usuario-Grupo"
            WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s
            """,
            (user_id, group_id)
        )

        conn.commit()
        
        cursor.close()
        release_db_connection(conn)

    
