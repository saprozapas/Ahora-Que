from database import get_db_connection, release_db_connection


class ChatService:

    @staticmethod
    def _nombre_visible(username, nombre):
        """Cómo se identifica a alguien en el chat: por su username. Nunca
        se muestra un mail: si el username es un mail (o está vacío), se usa
        el nombre de la persona."""
        username = (username or "").strip()
        if username and "@" not in username:
            return username
        return (nombre or "").strip() or "Usuario"

    def obtener_mensajes(self, group_id):
        conn = get_db_connection()

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        c."Id_Mensaje",
                        c."Id_Usuario",
                        u."Username",
                        u."Nombre",
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
                        "username": self._nombre_visible(fila[2], fila[3]),
                        "message": fila[4],
                        "created_at": fila[5].isoformat()
                    })

                return mensajes

        except Exception as e:
            print(f"Error al obtener mensajes: {e}")
            return []

        finally:
            release_db_connection(conn)


    def crear_mensaje(self, group_id, user_id, mensaje):
        """Guarda el mensaje. Si falla, el error sube a la ruta para que no
        le diga "ok" al usuario cuando el mensaje se perdió."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO public."Mensajes" ("Id_Grupo", "Id_Usuario", "Contenido")
                    VALUES (%s, %s, %s)
                """, (group_id, user_id, mensaje))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error al crear mensaje: {e}")
            raise
        finally:
            release_db_connection(conn)