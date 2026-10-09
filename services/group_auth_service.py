from database import get_db_connection, release_db_connection


class GroupAuthService:
    """Altas, consultas y cambios de grupos. Cada método libera la conexión
    en un finally: si algo falla, la conexión vuelve igual al pool."""

    def register(self, group, user_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public."Grupos" ("Creado_Por", "Nombre", "Descripcion")
                    VALUES (%s, %s, %s)
                    RETURNING "Id_Grupo"
                    """,
                    (user_id, group.get_name(), group.get_description())
                )
                group_id = cursor.fetchone()[0]
            # EL USUARIO SE AGREGA COMO INTEGRANTE DEL GRUPO AUTOMATICAMENTE POR UNA AUTOMATIZACION EN SUPABASE
            conn.commit()
            return group_id
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def is_user_in_group(self, user_id, group_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
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
                return cursor.fetchone()[0]
        finally:
            release_db_connection(conn)

    def update_group(self, group_id, name, description):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public."Grupos"
                    SET "Nombre" = %s, "Descripcion" = %s
                    WHERE "Id_Grupo" = %s
                    """,
                    (name, description, group_id)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def delete_user_from_group(self, group_id, user_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM public."Usuario-Grupo"
                    WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s
                    """,
                    (user_id, group_id)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)