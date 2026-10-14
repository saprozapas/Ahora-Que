from database import get_db_connection, release_db_connection


class GroupAuthService:
    """Altas, consultas y cambios de grupos. Cada método libera la conexión
    en un finally: si algo falla, la conexión vuelve igual al pool."""

    def register(self, group, user_id, todos_admin=False):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public."Grupos" ("Creado_Por", "Nombre", "Descripcion", "Todos_Admin")
                    VALUES (%s, %s, %s, %s)
                    RETURNING "Id_Grupo"
                    """,
                    (user_id, group.get_name(), group.get_description(), todos_admin)
                )
                group_id = cursor.fetchone()[0]
            # EL USUARIO SE AGREGA COMO INTEGRANTE DEL GRUPO AUTOMATICAMENTE POR UNA AUTOMATIZACION EN SUPABASE
            # (el trigger usuario_grupo_es_admin lo marca admin por ser el creador)
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

    def get_rol(self, user_id, group_id):
        """(es_admin, todos_admin) del usuario en el grupo; (False, False) si no es integrante."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ug."Es_Admin", g."Todos_Admin"
                    FROM public."Usuario-Grupo" ug
                    JOIN public."Grupos" g ON g."Id_Grupo" = ug."Id_Grupo"
                    WHERE ug."Id_Usuario" = %s AND ug."Id_Grupo" = %s
                    """,
                    (user_id, group_id)
                )
                return cursor.fetchone() or (False, False)
        finally:
            release_db_connection(conn)

    def is_admin(self, user_id, group_id):
        return bool(self.get_rol(user_id, group_id)[0])

    def make_admin(self, group_id, user_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public."Usuario-Grupo" SET "Es_Admin" = true
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

    def set_todos_admin(self, group_id, valor):
        """Activarlo también vuelve admins a los integrantes actuales;
        desactivarlo no le quita el rol a nadie."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    'UPDATE public."Grupos" SET "Todos_Admin" = %s WHERE "Id_Grupo" = %s',
                    (valor, group_id)
                )
                if valor:
                    cursor.execute(
                        'UPDATE public."Usuario-Grupo" SET "Es_Admin" = true WHERE "Id_Grupo" = %s',
                        (group_id,)
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
                    RETURNING "Es_Admin"
                    """,
                    (user_id, group_id)
                )
                fila = cursor.fetchone()
                # Se fue un admin y no quedó ninguno: pasa a admin el más antiguo
                # (si la antigüedad empata, al azar). Va en una sentencia aparte
                # porque en un solo CTE todavía vería al admin que se fue.
                if fila and fila[0]:
                    cursor.execute(
                        """
                        UPDATE public."Usuario-Grupo" SET "Es_Admin" = true
                        WHERE "Id_Grupo" = %(g)s
                          AND NOT EXISTS (SELECT 1 FROM public."Usuario-Grupo"
                                          WHERE "Id_Grupo" = %(g)s AND "Es_Admin")
                          AND "Id_Usuario" = (SELECT "Id_Usuario" FROM public."Usuario-Grupo"
                                              WHERE "Id_Grupo" = %(g)s
                                              ORDER BY "Fecha_Union", random() LIMIT 1)
                        """,
                        {"g": group_id}
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)