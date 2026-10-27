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
        """(es_admin, es_owner) del usuario en el grupo; (False, False) si no es integrante.

        El owner es quien creó el grupo (Grupos.Creado_Por) y siempre cuenta como admin."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ug."Es_Admin", g."Creado_Por"::text = %s
                    FROM public."Usuario-Grupo" ug
                    JOIN public."Grupos" g ON g."Id_Grupo" = ug."Id_Grupo"
                    WHERE ug."Id_Usuario" = %s AND ug."Id_Grupo" = %s
                    """,
                    (str(user_id), user_id, group_id)
                )
                fila = cursor.fetchone()
                if not fila:
                    return (False, False)
                return (bool(fila[0] or fila[1]), bool(fila[1]))
        finally:
            release_db_connection(conn)

    def is_admin(self, user_id, group_id):
        return self.get_rol(user_id, group_id)[0]

    def get_owner_id(self, group_id):
        """Id (texto) del owner del grupo. Si el grupo no tiene (lo creó alguien que ya no está), pasa a serlo
        el admin más antiguo, o el integrante más antiguo si no hubiera admins."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT g."Creado_Por"::text
                    FROM public."Grupos" g
                    JOIN public."Usuario-Grupo" ug
                      ON ug."Id_Grupo" = g."Id_Grupo" AND ug."Id_Usuario" = g."Creado_Por"
                    WHERE g."Id_Grupo" = %s
                    """,
                    (group_id,)
                )
                fila = cursor.fetchone()
                if fila:
                    return fila[0]
                cursor.execute(
                    """
                    UPDATE public."Grupos" SET "Creado_Por" = (
                        SELECT "Id_Usuario" FROM public."Usuario-Grupo"
                        WHERE "Id_Grupo" = %(g)s
                        ORDER BY "Es_Admin" DESC, "Fecha_Union", random() LIMIT 1)
                    WHERE "Id_Grupo" = %(g)s
                    RETURNING "Creado_Por"::text
                    """,
                    {"g": group_id}
                )
                nuevo = cursor.fetchone()
                if nuevo and nuevo[0]:
                    cursor.execute(
                        'UPDATE public."Usuario-Grupo" SET "Es_Admin" = true WHERE "Id_Grupo" = %s AND "Id_Usuario"::text = %s',
                        (group_id, nuevo[0])
                    )
            conn.commit()
            return nuevo[0] if nuevo else None
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def puede_cambiar_admin(self, actor_id, group_id, target_id):
        """Un admin le da o le quita el rol a otro integrante; al owner nunca se lo toca."""
        if str(actor_id) == str(target_id):
            return False
        es_admin, _ = self.get_rol(actor_id, group_id)
        if not es_admin or str(target_id) == self.get_owner_id(group_id):
            return False
        return self.is_user_in_group(target_id, group_id)

    def puede_sacar(self, actor_id, group_id, target_id):
        """El owner saca a cualquiera; un admin solo a quienes no son admin."""
        if str(actor_id) == str(target_id):
            return False
        es_admin, es_owner = self.get_rol(actor_id, group_id)
        if es_owner:
            return self.is_user_in_group(target_id, group_id)
        if not es_admin:
            return False
        objetivo_admin, objetivo_owner = self.get_rol(target_id, group_id)
        pertenece = self.is_user_in_group(target_id, group_id)
        return pertenece and not objetivo_admin and not objetivo_owner

    def make_admin(self, group_id, user_id):
        self._set_admin(group_id, user_id, True)

    def quitar_admin(self, group_id, user_id):
        self._set_admin(group_id, user_id, False)

    def _set_admin(self, group_id, user_id, valor):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public."Usuario-Grupo" SET "Es_Admin" = %s
                    WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s
                    """,
                    (valor, user_id, group_id)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    @staticmethod
    def salir_del_grupo(cursor, group_id, user_id):
        """Saca al usuario del grupo dentro de la transacción del cursor recibido."""
        cursor.execute(
            'SELECT "Creado_Por"::text = %s FROM public."Grupos" WHERE "Id_Grupo" = %s',
            (str(user_id), group_id)
        )
        era_owner = bool((cursor.fetchone() or (False,))[0])
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
        # Se fue el owner: pasa a serlo el admin más antiguo (que ya es admin, así que nadie pierde ni gana permisos de más).
        if era_owner:
            cursor.execute(
                """
                UPDATE public."Grupos" SET "Creado_Por" = (
                    SELECT "Id_Usuario" FROM public."Usuario-Grupo"
                    WHERE "Id_Grupo" = %(g)s AND "Es_Admin"
                    ORDER BY "Fecha_Union", random() LIMIT 1)
                WHERE "Id_Grupo" = %(g)s
                """,
                {"g": group_id}
            )

    def transferir_owner(self, group_id, nuevo_owner_id):
        """El nuevo owner queda también como admin; quien era owner sigue de admin."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public."Usuario-Grupo" SET "Es_Admin" = true
                    WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s
                    """,
                    (nuevo_owner_id, group_id)
                )
                cursor.execute(
                    'UPDATE public."Grupos" SET "Creado_Por" = %s WHERE "Id_Grupo" = %s',
                    (nuevo_owner_id, group_id)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def puede_transferir_owner(self, actor_id, group_id, target_id):
        """Solo el owner, y solo a otro integrante."""
        if str(actor_id) == str(target_id):
            return False
        _, es_owner = self.get_rol(actor_id, group_id)
        return es_owner and self.is_user_in_group(target_id, group_id)

    def delete_user_from_group(self, group_id, user_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                self.salir_del_grupo(cursor, group_id, user_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)