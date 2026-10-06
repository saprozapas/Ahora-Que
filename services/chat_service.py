from database import get_db_connection, release_db_connection


class ChatService:

    def obtener_mensajes(self, group_id):
        conn = get_db_connection()

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        c."Id_Mensaje",
                        c."Id_Usuario",
                        u."Username",
                        c."Contenido",
                        c."Fecha_Envio"
                    FROM public."Mensajes" c
                    JOIN public."Usuarios" u
                        ON c."Id_Usuario" = u."Id_Usuario"
                    WHERE c."Id_Grupo" = %s
                    ORDER BY c."Fecha_Envio" ASC
                """, (group_id,))

                filas = cursor.fetchall()

                mensajes = []

                for fila in filas:
                    mensajes.append({
                        "id": str(fila[0]),
                        "user_id": str(fila[1]),
                        "username": fila[2],
                        "message": fila[3],
                        "created_at": fila[4].isoformat()
                    })

                return mensajes

        except Exception as e:
            print(f"Error al obtener mensajes: {e}")
            return []

        finally:
            release_db_connection(conn)


    def crear_mensaje(self, group_id, user_id, mensaje):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO public."Mensajes" ("Id_Grupo", "Id_Usuario", "Contenido")
                    VALUES (%s, %s, %s)
                """, (group_id, user_id, mensaje))
                conn.commit()
        except Exception as e:
            print(f"Error al crear mensaje: {e}")
        finally:
            release_db_connection(conn)