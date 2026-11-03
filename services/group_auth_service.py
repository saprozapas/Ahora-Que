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
        """Saca al usuario del grupo dentro de la transacción del cursor recibido.

        Además de la membresía, limpia todo lo que el usuario tenía en los planes vivos del grupo
        (votos, asistencia, ubicación compartida) y vuelve a resolver las votaciones que, sin su
        voto, ya tienen respuesta de todos los que quedan. Si era el último integrante, el grupo
        se borra entero: sin integrantes no lo ve nadie y quedaría huérfano.

        Devuelve los avisos pendientes [(plan_id, tipo, resultado)] de las votaciones que se
        resolvieron al irse: quien llama los manda con avisar_tras_salir() DESPUÉS del commit."""
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

        cursor.execute(
            'SELECT COUNT(*) FROM public."Usuario-Grupo" WHERE "Id_Grupo" = %s', (group_id,)
        )
        if cursor.fetchone()[0] == 0:
            GroupAuthService._borrar_grupo_vacio(cursor, group_id)
            return []

        eventos = GroupAuthService._retirar_de_planes_del_grupo(cursor, group_id, user_id)

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
        return eventos

    @staticmethod
    def avisar_tras_salir(group_id, user_id, eventos):
        """Avisa al grupo de las votaciones que se resolvieron cuando alguien se fue (ya con el commit hecho)."""
        if eventos:
            from services.grupo_plan_service import GrupoPlanService  # acá adentro: evita un import circular
            GrupoPlanService().avisar_resultados(group_id, user_id, eventos)

    @staticmethod
    def _retirar_de_planes_del_grupo(cursor, group_id, user_id):
        """Quita al usuario de los planes vivos del grupo (en votación, esperando horario o
        confirmados) y re-resuelve las votaciones que su salida deja completas. Los planes
        archivados no se tocan: su puntaje y su lugar en el historial son del usuario."""
        params = {"g": group_id, "u": user_id}
        planes_vivos = (
            'SELECT "id_Plan" FROM public."Plan" WHERE "Grupo_id" = %(g)s '
            "AND \"Estado\" IN ('votacion', 'esperando_horario', 'confirmado')"
        )
        cursor.execute(
            f'DELETE FROM public."Plan_Voto" WHERE "Id_Usuario" = %(u)s '
            f'AND "Id_Plan" IN (SELECT "id_Plan" FROM public."Plan" WHERE "Grupo_id" = %(g)s AND "Estado" = \'votacion\')',
            params,
        )
        cursor.execute(
            f'DELETE FROM public."Plan_Horario_Voto" WHERE "Id_Usuario" = %(u)s '
            f'AND "Id_Horario" IN (SELECT "Id_Horario" FROM public."Plan_Horario" '
            f"WHERE \"Estado\" = 'votacion' AND \"Id_Plan\" IN ({planes_vivos}))",
            params,
        )
        cursor.execute(
            f'DELETE FROM public."Plan_Ubicacion" WHERE "Id_Usuario" = %(u)s AND "Id_Plan" IN ({planes_vivos})',
            params,
        )
        # Lo que además tenía guardado se conserva; el resto de la relación con el plan se va.
        cursor.execute(
            f'UPDATE public."Usuario-Plan" SET "Confirmado" = false '
            f'WHERE "Usuario_id" = %(u)s AND "Guardado" AND "Plan_id" IN ({planes_vivos})',
            params,
        )
        cursor.execute(
            f'DELETE FROM public."Usuario-Plan" '
            f'WHERE "Usuario_id" = %(u)s AND NOT COALESCE("Guardado", false) AND "Plan_id" IN ({planes_vivos})',
            params,
        )

        # Sin su voto, puede que ya hayan respondido todos los que quedan.
        from services.grupo_plan_service import GrupoPlanService  # acá adentro: evita un import circular
        resolver = GrupoPlanService()
        cursor.execute(
            'SELECT "id_Plan" FROM public."Plan" WHERE "Grupo_id" = %s AND "Estado" = \'votacion\'', (group_id,)
        )
        eventos = []
        for (plan_id,) in cursor.fetchall():
            eventos.append((plan_id, "plan", resolver._resolver_votacion(cursor, plan_id)))
        cursor.execute(
            """
            SELECT h."Id_Horario", h."Id_Plan" FROM public."Plan_Horario" h
            JOIN public."Plan" p ON p."id_Plan" = h."Id_Plan"
            WHERE p."Grupo_id" = %s AND p."Estado" = 'esperando_horario' AND h."Estado" = 'votacion'
            ORDER BY h."Id_Horario"
            """,
            (group_id,),
        )
        for horario_id, plan_id in cursor.fetchall():
            eventos.append((plan_id, "horario", resolver._resolver_horario(cursor, horario_id)))
        return [e for e in eventos if e[2]]

    # Orden pensado para las claves foráneas: primero lo que cuelga de los planes y de las encuestas.
    _BORRAR_GRUPO = (
        'DELETE FROM public."Plan_Ubicacion" WHERE "Id_Plan" IN (SELECT "id_Plan" FROM public."Plan" WHERE "Grupo_id" = %(g)s)',
        'DELETE FROM public."Plan_Horario_Voto" WHERE "Id_Horario" IN (SELECT h."Id_Horario" FROM public."Plan_Horario" h JOIN public."Plan" p ON p."id_Plan" = h."Id_Plan" WHERE p."Grupo_id" = %(g)s)',
        'DELETE FROM public."Plan_Horario" WHERE "Id_Plan" IN (SELECT "id_Plan" FROM public."Plan" WHERE "Grupo_id" = %(g)s)',
        'DELETE FROM public."Plan_Voto" WHERE "Id_Plan" IN (SELECT "id_Plan" FROM public."Plan" WHERE "Grupo_id" = %(g)s)',
        'DELETE FROM public."Usuario-Plan" WHERE "Plan_id" IN (SELECT "id_Plan" FROM public."Plan" WHERE "Grupo_id" = %(g)s)',
        'DELETE FROM public."gasto_detalle" WHERE "gasto_id" IN (SELECT g."id_gasto" FROM public."gasto" g JOIN public."Plan" p ON p."id_Plan" = g."plan_id" WHERE p."Grupo_id" = %(g)s)',
        'DELETE FROM public."gasto" WHERE "plan_id" IN (SELECT "id_Plan" FROM public."Plan" WHERE "Grupo_id" = %(g)s)',
        'DELETE FROM public."Grupo_Encuesta_Voto" WHERE "Id_Encuesta" IN (SELECT "Id_Encuesta" FROM public."Grupo_Encuesta" WHERE "Id_Grupo" = %(g)s)',
        'DELETE FROM public."Grupo_Encuesta_Opcion" WHERE "Id_Encuesta" IN (SELECT "Id_Encuesta" FROM public."Grupo_Encuesta" WHERE "Id_Grupo" = %(g)s)',
        'DELETE FROM public."Grupo_Encuesta_Respuesta" WHERE "Id_Encuesta" IN (SELECT "Id_Encuesta" FROM public."Grupo_Encuesta" WHERE "Id_Grupo" = %(g)s)',
        'DELETE FROM public."Grupo_Encuesta_Disponibilidad" WHERE "Id_Encuesta" IN (SELECT "Id_Encuesta" FROM public."Grupo_Encuesta" WHERE "Id_Grupo" = %(g)s)',
        'DELETE FROM public."Grupo_Encuesta" WHERE "Id_Grupo" = %(g)s',
        'DELETE FROM public."Mensajes" WHERE "Id_Grupo" = %(g)s',
        'DELETE FROM public."Conversacion" WHERE "Id_Grupo" = %(g)s',
        'DELETE FROM public."Invitaciones" WHERE "Id_Grupo" = %(g)s',
        'DELETE FROM public."Plan" WHERE "Grupo_id" = %(g)s',
        'DELETE FROM public."Grupos" WHERE "Id_Grupo" = %(g)s',
    )

    @staticmethod
    def _borrar_grupo_vacio(cursor, group_id):
        """Borra el grupo que se quedó sin integrantes. Va en un SAVEPOINT: si alguna tabla
        no se deja borrar (una clave foránea que no conocemos), el grupo queda como estaba y
        quien se fue igual sale, en vez de fallar toda la salida."""
        cursor.execute("SAVEPOINT borrar_grupo_vacio")
        try:
            for sentencia in GroupAuthService._BORRAR_GRUPO:
                cursor.execute(sentencia, {"g": group_id})
        except Exception as e:
            cursor.execute("ROLLBACK TO SAVEPOINT borrar_grupo_vacio")
            print(f"No se pudo borrar el grupo vacío {group_id}: {e}")
        else:
            cursor.execute("RELEASE SAVEPOINT borrar_grupo_vacio")

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
                eventos = self.salir_del_grupo(cursor, group_id, user_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)
        self.avisar_tras_salir(group_id, user_id, eventos)