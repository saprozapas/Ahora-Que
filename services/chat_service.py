import re
import threading
import time

from database import get_db_connection, release_db_connection
from services.avatar_service import AvatarService


_LIMPIEZA_CADA_SEGUNDOS = 24 * 60 * 60
_ultima_limpieza = 0.0
_lock_limpieza = threading.Lock()


# Cada cuánto como máximo se anota "leyó el chat" mientras la conversación está abierta (la página pide los
# mensajes cada 3 segundos y no hace falta escribir en la base cada vez).
_VISTO_CADA_SEGUNDOS = 15
_ultimo_visto = {}


class ChatService:

    @staticmethod
    def handle(username, nombre):
        """Cómo se menciona a alguien con @: su username (o su nombre sin espacios si el username es un mail)."""
        return "".join(ChatService._nombre_visible(username, nombre).split())

    def marcar_visto(self, user_id, group_id, siempre=False):
        """Anota que este usuario leyó el chat del grupo hasta ahora: lo que lo mencionaron antes ya no avisa."""
        clave = (str(user_id), str(group_id))
        if not siempre and time.monotonic() - _ultimo_visto.get(clave, 0) < _VISTO_CADA_SEGUNDOS:
            return
        _ultimo_visto[clave] = time.monotonic()
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public."Usuario-Grupo"
                    SET "Chat_Visto_En" = (now() AT TIME ZONE 'America/Montevideo')
                    WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s
                    """,
                    (user_id, group_id),
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"No se pudo anotar la lectura del chat: {e}")
        finally:
            release_db_connection(conn)

    def get_menciones(self, user_id):
        """Menciones (@usuario o @all) que todavía no leyó, agrupadas por grupo: una entrada por grupo con el último
        mensaje. [{"grupo_id", "grupo", "cantidad", "mensaje_id", "autor", "texto", "es_todos"}], las más nuevas primero."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT "Username", "Nombre" FROM public."Usuarios" WHERE "Id_Usuario" = %s', (user_id,))
                fila = cursor.fetchone()
                if fila is None:
                    return []
                handle = self.handle(fila[0], fila[1])
                nombres = f"all|todos|{re.escape(handle)}" if handle else "all|todos"
                patron = rf"(^|[^[:alnum:]_@])@({nombres})($|[^[:alnum:]_])"
                cursor.execute(
                    """
                    SELECT g."Id_Grupo", g."Nombre", m."Id_Mensaje", u."Username", u."Nombre", m."Contenido", m."Fecha_Envio"
                    FROM public."Usuario-Grupo" ug
                    JOIN public."Grupos" g ON g."Id_Grupo" = ug."Id_Grupo"
                    JOIN public."Mensajes" m ON m."Id_Grupo" = ug."Id_Grupo"
                    JOIN public."Usuarios" u ON u."Id_Usuario" = m."Id_Usuario"
                    WHERE ug."Id_Usuario" = %s AND m."Id_Usuario" <> %s
                      AND m."Fecha_Envio" > ug."Chat_Visto_En"
                      AND m."Contenido" ~* %s
                    ORDER BY m."Fecha_Envio" DESC
                    """,
                    (user_id, user_id, patron),
                )
                por_grupo = {}
                for f in cursor.fetchall():
                    entrada = por_grupo.get(str(f[0]))
                    if entrada is None:  # la primera de cada grupo es la más nueva
                        texto = " ".join(str(f[5]).split())
                        por_grupo[str(f[0])] = {
                            "grupo_id": str(f[0]), "grupo": f[1], "cantidad": 1, "mensaje_id": str(f[2]),
                            "autor": self._nombre_visible(f[3], f[4]),
                            "texto": texto if len(texto) <= 90 else texto[:87].rstrip() + "…",
                            "momento": f[6],
                        }
                    else:
                        entrada["cantidad"] += 1
                return sorted(por_grupo.values(), key=lambda e: e["momento"], reverse=True)
        except Exception as e:
            print(f"No se pudieron leer las menciones: {e}")
            return []
        finally:
            release_db_connection(conn)

    def eliminar_mensajes_viejos(self):
        """Programa la limpieza diaria fuera del tiempo de respuesta web."""
        global _ultima_limpieza
        with _lock_limpieza:
            if time.monotonic() - _ultima_limpieza < _LIMPIEZA_CADA_SEGUNDOS:
                return
            _ultima_limpieza = time.monotonic()
        threading.Thread(target=self._eliminar_mensajes_viejos, daemon=True).start()

    @staticmethod
    def _eliminar_mensajes_viejos():
        """Elimina mensajes de más de 14 días en segundo plano."""
        global _ultima_limpieza
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''
                    DELETE FROM public."Mensajes"
                    WHERE "Fecha_Envio" < now() - INTERVAL '14 days'
                ''')
            conn.commit()
        except Exception as e:
            if conn is not None:
                conn.rollback()
            print(f"Error al eliminar mensajes viejos: {e}")
            with _lock_limpieza:
                _ultima_limpieza = 0.0
        finally:
            if conn is not None:
                release_db_connection(conn)

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
                        c."Fecha_Envio",
                        u."Premium"
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
                        "avatar": AvatarService.version_de(fila[1]),
                        "username": self._nombre_visible(fila[2], fila[3]),
                        "premium": bool(fila[6]),
                        "message": fila[4],
                        "created_at": fila[5].isoformat()
                    })

                return mensajes

        except Exception as e:
            print(f"Error al obtener mensajes: {e}")
            return []

        finally:
            release_db_connection(conn)


    # Mensajes que invocan al bot: "@AhoraQue ...", "@Ahora Que ..." o "@bot ...".
    PATRON_BOT = r"@(ahora\s*que|ahoraque|bot)\M"

    def eliminar_mensajes(self, group_id, solo_bot=False, de_usuario=None):
        """Borra mensajes del chat de un grupo y devuelve cuántos.

        solo_bot:   solo los que mencionan al bot (@AhoraQue / @bot).
        de_usuario: si se indica, solo los que escribió ese usuario."""
        condiciones = ['"Id_Grupo" = %s']
        parametros = [group_id]
        if solo_bot:
            condiciones.append('"Contenido" ~* %s')
            parametros.append(self.PATRON_BOT)
        if de_usuario is not None:
            condiciones.append('"Id_Usuario" = %s')
            parametros.append(de_usuario)
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM public."Mensajes" WHERE ' + " AND ".join(condiciones),
                    parametros,
                )
                borrados = cursor.rowcount
            conn.commit()
            return borrados
        except Exception as e:
            conn.rollback()
            print(f"Error al eliminar mensajes: {e}")
            raise
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