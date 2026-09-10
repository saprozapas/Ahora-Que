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
            RETURNING "Id_Grupo"
            """,
            (user_id, group.get_name(), group.get_descripcion())
        )
        group_id = cursor.fetchone()[0]
        
        self.add_user(user_id, group_id)

        conn.commit()

        cursor.close()
        conn.close()

    def add_user(self, user_id, group_id):
    
            conn = get_db_connection()
            cursor = conn.cursor()
    
            cursor.execute(
                """
                INSERT INTO public."Usuario-Grupo" ("Usuario_id", "Grupo_id")
                VALUES (%s, %s)
                """,
                (user_id, group_id)
            )
            
    
            conn.commit()
    
            cursor.close()
            conn.close()