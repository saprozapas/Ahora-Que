from database import get_db_connection
from models import group, user
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
        conn.close()

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
        conn.close()
