from database import get_db_connection, release_db_connection


class ChatService:

    def obtener_mensajes(self, group_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT c.Id_Grupo, c.Id_Usuario, u.Id_Usuario, c.Contenido, c.Fecha_Envio
                    FROM public."Mensajes" c
                    JOIN public."Usuarios" u ON c.Id_Usuario = u.Id_Usuario
                    WHERE c.Id_Grupo = %s
                    ORDER BY c.Fecha_Envio ASC
                """, (group_id,))
                mensajes = cursor.fetchall()
                conn.commit()
        except Exception as e:
            print(f"Error al obtener mensajes: {e}")
            mensajes = []
        finally:
            release_db_connection(conn)
        
        return mensajes


    def crear_mensaje(self, group_id, user_id, mensaje):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO public."Mensajes" (Id_Grupo, Id_Usuario, Contenido)
                    VALUES (%s, %s, %s)
                """, (group_id, user_id, mensaje))
                conn.commit()
        except Exception as e:
            print(f"Error al crear mensaje: {e}")
        finally:
            release_db_connection(conn)