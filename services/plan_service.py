import psycopg2

from database import get_db_connection


class PlanService:

    # --- Helpers internos ---------------------------------------------------

    def _lugares_de_plan(self, cursor, plan_id):
        """Paradas de un plan.

        Salen de "Plan_Lugar" (un plan puede tener varias, cada una con su
        precio). Si el plan todavía no tiene filas ahí pero sí el "Lugar_id"
        único de "Plan" (los planes viejos), se usa ese lugar como única
        parada.
        """
        cursor.execute(
            """
            SELECT "Nombre", "Precio", "Hora"
            FROM public."Plan_Lugar"
            WHERE "Id_Plan" = %s
            ORDER BY "Orden", "Id_Plan_Lugar"
            """,
            (plan_id,),
        )
        lugares = [
            {"nombre": fila[0], "precio": fila[1], "hora": fila[2]}
            for fila in cursor.fetchall()
        ]

        if lugares:
            return lugares

        # Fallback al lugar único de "Plan"."Lugar_id".
        cursor.execute(
            """
            SELECT l."Nombre"
            FROM public."Plan" p
            JOIN public."Lugar" l ON l."Id_Lugar" = p."Lugar_id"
            WHERE p."id_Plan" = %s
            """,
            (plan_id,),
        )
        fila = cursor.fetchone()
        if fila:
            return [{"nombre": fila[0], "precio": None, "hora": None}]

        return []

    def _resumen_lugares(self, lugares):
        if not lugares:
            return "Sin lugar específico"
        nombres = [lugar["nombre"] for lugar in lugares]
        if len(nombres) == 1:
            return nombres[0]
        return f"{nombres[0]} y {len(nombres) - 1} más"

    def _armar_plan(self, cursor, fila, extra=None):
        plan_id = fila[0]
        lugares = self._lugares_de_plan(cursor, plan_id)
        plan = {
            "id": plan_id,
            "nombre": fila[1],
            "fecha": fila[2],
            "hora": fila[3],
            "precio": fila[4],
            "estado": fila[5],
            "lugares": lugares,
            "resumen_lugares": self._resumen_lugares(lugares),
        }
        if extra:
            plan.update(extra)
        return plan

    # --- Listados -------------------------------------------------------

    def get_planes_confirmados(self, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    WHERE up."Usuario_id" = %s
                      AND up."Confirmado" = true
                    ORDER BY p."Fecha", p."Hora"
                    """,
                    (user_id,),
                )
                return [self._armar_plan(cursor, fila) for fila in cursor.fetchall()]
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    def get_planes_grupo(self, user_id):
        """Planes futuros de grupos del usuario que todavía no confirmó."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado", g."Nombre"
                    FROM public."Plan" p
                    JOIN public."Grupos" g ON g."Id_Grupo" = p."Grupo_id"
                    JOIN public."Usuario-Grupo" ug ON ug."Id_Grupo" = p."Grupo_id"
                    WHERE ug."Id_Usuario" = %s
                      AND p."Fecha" >= CURRENT_DATE
                      AND NOT EXISTS (
                          SELECT 1 FROM public."Usuario-Plan" up
                          WHERE up."Plan_id" = p."id_Plan"
                            AND up."Usuario_id" = %s
                            AND up."Confirmado" = true
                      )
                    ORDER BY p."Fecha", p."Hora"
                    """,
                    (user_id, user_id),
                )
                return [
                    self._armar_plan(cursor, fila, {"grupo": fila[6]})
                    for fila in cursor.fetchall()
                ]
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    def get_planes_guardados(self, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    WHERE up."Usuario_id" = %s
                      AND up."Guardado" = true
                    ORDER BY p."Nombre"
                    """,
                    (user_id,),
                )
                return [self._armar_plan(cursor, fila) for fila in cursor.fetchall()]
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    def get_historial(self, user_id):
        """Planes confirmados de los últimos 3 meses, con fecha ya pasada."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    WHERE up."Usuario_id" = %s
                      AND up."Confirmado" = true
                      AND p."Fecha" < CURRENT_DATE
                      AND p."Fecha" >= CURRENT_DATE - INTERVAL '3 months'
                    ORDER BY p."Fecha" DESC, p."Hora" DESC
                    """,
                    (user_id,),
                )
                return [self._armar_plan(cursor, fila) for fila in cursor.fetchall()]
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    # --- Detalle ----------------------------------------------------------

    def get_plan_detalle(self, plan_id, user_id):
        """Devuelve el detalle de un plan si el usuario tiene acceso a él
        (lo confirmó, lo guardó, o pertenece al grupo dueño del plan).
        Devuelve None si el plan no existe o el usuario no tiene acceso."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                        p."Grupo_id", g."Nombre"
                    FROM public."Plan" p
                    LEFT JOIN public."Grupos" g ON g."Id_Grupo" = p."Grupo_id"
                    WHERE p."id_Plan" = %s
                    """,
                    (plan_id,),
                )
                fila = cursor.fetchone()
                if fila is None:
                    return None

                cursor.execute(
                    """
                    SELECT "Confirmado", "Guardado"
                    FROM public."Usuario-Plan"
                    WHERE "Plan_id" = %s AND "Usuario_id" = %s
                    """,
                    (plan_id, user_id),
                )
                relacion = cursor.fetchone()
                confirmado = bool(relacion[0]) if relacion else False
                guardado = bool(relacion[1]) if relacion else False

                id_grupo = fila[6]
                en_grupo = False
                if id_grupo is not None:
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM public."Usuario-Grupo"
                            WHERE "Id_Grupo" = %s AND "Id_Usuario" = %s
                        )
                        """,
                        (id_grupo, user_id),
                    )
                    en_grupo = cursor.fetchone()[0]

                if not (confirmado or guardado or en_grupo):
                    return None

                return self._armar_plan(
                    cursor,
                    fila,
                    {
                        "grupo": fila[7],
                        "confirmado": confirmado,
                        "guardado": guardado,
                    },
                )
        except psycopg2.Error:
            raise
        finally:
            connection.close()
