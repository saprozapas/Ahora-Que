import psycopg2

from database import get_db_connection
from services.precio_lugar import rango_de_nivel, sumar_rangos


class PlanService:

    # --- Helpers internos ---------------------------------------------------

    def _lugares_de_plan(self, cursor, plan_id):
        """Paradas de un plan.

        Salen de "Plan_Lugar" (un plan puede tener varias, cada una con su
        rango de precio estimado). Si el plan todavía no tiene filas ahí
        pero sí el "Lugar_id" único de "Plan" (los planes viejos), se usa
        ese lugar como única parada.
        """
        cursor.execute(
            """
            SELECT "Nombre", "Precio_Min", "Precio_Max", "Hora"
            FROM public."Plan_Lugar"
            WHERE "Id_Plan" = %s
            ORDER BY "Orden", "Id_Plan_Lugar"
            """,
            (plan_id,),
        )
        lugares = [
            {
                "nombre": fila[0],
                "precio_min": fila[1],
                "precio_max": fila[2],
                "hora": fila[3],
            }
            for fila in cursor.fetchall()
        ]

        if lugares:
            return lugares

        # Fallback a "Plan"."Lugar_id" (planes de antes de Plan_Lugar).
        # Se estima igual un rango a partir del Nivel_Precio del lugar.
        cursor.execute(
            """
            SELECT l."Nombre", l."Nivel_Precio"
            FROM public."Plan" p
            JOIN public."Lugar" l ON l."Id_Lugar" = p."Lugar_id"
            WHERE p."id_Plan" = %s
            """,
            (plan_id,),
        )
        fila = cursor.fetchone()
        if fila:
            rango = rango_de_nivel(fila[1])
            return [{
                "nombre": fila[0],
                "precio_min": rango[0] if rango else None,
                "precio_max": rango[1] if rango else None,
                "hora": None,
            }]

        return []

    def _resumen_lugares(self, lugares):
        if not lugares:
            return "Sin lugar específico"
        nombres = [lugar["nombre"] for lugar in lugares]
        if len(nombres) == 1:
            return nombres[0]
        return f"{nombres[0]} y {len(nombres) - 1} más"

    def _armar_plan(self, cursor, fila, extra=None, lugares=None):
        """fila tiene que terminar siempre en (..., Precio_Min, Precio_Max):
        así no importa cuántas columnas más traiga cada consulta."""
        plan_id = fila[0]
        if lugares is None:
            lugares = self._lugares_de_plan(cursor, plan_id)
        plan = {
            "id": plan_id,
            "nombre": fila[1],
            "fecha": fila[2],
            "hora": fila[3],
            "precio": fila[4],  # legacy: planes creados antes del rango
            "estado": fila[5],
            "precio_min": fila[-2],
            "precio_max": fila[-1],
            "lugares": lugares,
            "resumen_lugares": self._resumen_lugares(lugares),
        }
        if extra:
            plan.update(extra)
        return plan

    def _lugares_de_planes(self, cursor, plan_ids):
        """Como _lugares_de_plan, pero para MUCHOS planes en 2 consultas
        en total (antes era 1-2 consultas POR plan). Devuelve
        {plan_id: [lugares]}."""
        resultado = {plan_id: [] for plan_id in plan_ids}
        if not plan_ids:
            return resultado

        cursor.execute(
            """
            SELECT "Id_Plan", "Nombre", "Precio_Min", "Precio_Max", "Hora"
            FROM public."Plan_Lugar"
            WHERE "Id_Plan" IN %s
            ORDER BY "Id_Plan", "Orden", "Id_Plan_Lugar"
            """,
            (tuple(plan_ids),),
        )
        for fila in cursor.fetchall():
            resultado.setdefault(fila[0], []).append({
                "nombre": fila[1],
                "precio_min": fila[2],
                "precio_max": fila[3],
                "hora": fila[4],
            })

        # Fallback a "Plan"."Lugar_id" para los planes viejos sin Plan_Lugar.
        sin_lugares = tuple(plan_id for plan_id, lugares in resultado.items() if not lugares)
        if sin_lugares:
            cursor.execute(
                """
                SELECT p."id_Plan", l."Nombre", l."Nivel_Precio"
                FROM public."Plan" p
                JOIN public."Lugar" l ON l."Id_Lugar" = p."Lugar_id"
                WHERE p."id_Plan" IN %s
                """,
                (sin_lugares,),
            )
            for fila in cursor.fetchall():
                rango = rango_de_nivel(fila[2])
                resultado[fila[0]] = [{
                    "nombre": fila[1],
                    "precio_min": rango[0] if rango else None,
                    "precio_max": rango[1] if rango else None,
                    "hora": None,
                }]

        return resultado

    def _armar_planes(self, cursor, filas, extra=None):
        """Arma varios planes de una. extra (opcional) es una función
        fila -> dict con campos adicionales."""
        lugares_por_plan = self._lugares_de_planes(cursor, [fila[0] for fila in filas])
        return [
            self._armar_plan(
                cursor, fila,
                extra(fila) if extra else None,
                lugares=lugares_por_plan.get(fila[0], []),
            )
            for fila in filas
        ]

    # --- Listados -------------------------------------------------------

    def get_planes_confirmados(self, user_id):
        """Planes confirmados que todavía no pasaron. Una vez que la
        fecha queda atrás, el plan deja de aparecer acá (pasa a
        "Historial") aunque siga Confirmado = true en la base."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                           p."Precio_Min", p."Precio_Max"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    WHERE up."Usuario_id" = %s
                      AND up."Confirmado" = true
                      AND p."Fecha" >= CURRENT_DATE
                    ORDER BY p."Fecha", p."Hora"
                    """,
                    (user_id,),
                )
                return self._armar_planes(cursor, cursor.fetchall())
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    def get_planes_confirmados_calendario(self, user_id):
        """Como get_planes_confirmados, pero sin filtrar por fecha: el
        calendario tiene que poder mostrar también los meses pasados."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                           p."Precio_Min", p."Precio_Max"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    WHERE up."Usuario_id" = %s
                      AND up."Confirmado" = true
                    ORDER BY p."Fecha", p."Hora"
                    """,
                    (user_id,),
                )
                return self._armar_planes(cursor, cursor.fetchall())
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
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado", g."Nombre",
                           p."Precio_Min", p."Precio_Max"
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
                return self._armar_planes(
                    cursor, cursor.fetchall(), lambda fila: {"grupo": fila[6]}
                )
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
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                           p."Precio_Min", p."Precio_Max"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    WHERE up."Usuario_id" = %s
                      AND up."Guardado" = true
                    ORDER BY p."Nombre"
                    """,
                    (user_id,),
                )
                return self._armar_planes(cursor, cursor.fetchall())
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    def get_historial(self, user_id):
        """Planes confirmados de los últimos 3 meses, con fecha ya pasada
        (acá es donde "aterrizan" los que se salen de "Confirmados")."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                           p."Precio_Min", p."Precio_Max"
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
                return self._armar_planes(cursor, cursor.fetchall())
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    # --- Creación --------------------------------------------------------

    def crear_plan(self, user_id, nombre, fecha, hora, descripcion, lugares,
                   guardado=False, grupo_id=None):
        """Crea un plan y lo deja confirmado para el usuario que lo creó.

        lugares: lista de dicts con las paradas, en orden:
                 {"id_lugar": uuid o None, "nombre": str,
                  "nivel_precio": 0-4 o None, "hora": "HH:MM" o None}
                 Puede venir vacía: un plan sin lugar específico
                 (por ejemplo "llamada a las 8") es válido.

        El precio no lo elige el usuario: se estima sumando el rango de
        cada lugar según su Nivel_Precio (ver services/precio_lugar.py).

        Al quedar Confirmado = true, el plan aparece automáticamente en
        el calendario y en "Planes confirmados".

        Devuelve el id del plan creado.
        """
        rangos_por_lugar = [
            rango_de_nivel(lugar.get("nivel_precio")) for lugar in lugares
        ]
        rango_total = sumar_rangos(rangos_por_lugar)
        precio_min_total = rango_total[0] if rango_total else None
        precio_max_total = rango_total[1] if rango_total else None

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                # Grupo_id y Lugar_id van en NULL explícito: así no se
                # activa el DEFAULT gen_random_uuid() que tienen esas
                # columnas (que generaría un uuid inexistente y rompería
                # la foreign key). Las paradas van en "Plan_Lugar".
                cursor.execute(
                    """
                    INSERT INTO public."Plan"
                        ("Nombre", "Fecha", "Hora", "Descripcion",
                         "Precio_Min", "Precio_Max",
                         "Creado_Por", "Estado", "Grupo_id", "Lugar_id")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'activo', %s, NULL)
                    RETURNING "id_Plan"
                    """,
                    (nombre, fecha, hora, descripcion,
                     precio_min_total, precio_max_total, user_id, grupo_id),
                )
                plan_id = cursor.fetchone()[0]

                for orden, (lugar, rango) in enumerate(zip(lugares, rangos_por_lugar), start=1):
                    cursor.execute(
                        """
                        INSERT INTO public."Plan_Lugar"
                            ("Id_Plan", "Id_Lugar", "Nombre", "Precio_Min", "Precio_Max", "Hora", "Orden")
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            plan_id,
                            lugar.get("id_lugar"),
                            lugar["nombre"],
                            rango[0] if rango else None,
                            rango[1] if rango else None,
                            lugar.get("hora"),
                            orden,
                        ),
                    )

                cursor.execute(
                    """
                    INSERT INTO public."Usuario-Plan"
                        ("Usuario_id", "Plan_id", "Confirmado", "Guardado")
                    VALUES (%s, %s, true, %s)
                    """,
                    (user_id, plan_id, guardado),
                )

            connection.commit()
            return plan_id
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

    # --- Guardar / desguardar ----------------------------------------------

    def set_guardado(self, plan_id, user_id, guardado):
        """Marca o desmarca un plan como guardado para ese usuario.

        Si el usuario todavía no tenía ninguna relación con el plan
        (no lo había confirmado ni guardado), se crea una fila nueva
        con Confirmado = false.
        """
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public."Usuario-Plan" ("Usuario_id", "Plan_id", "Confirmado", "Guardado")
                    VALUES (%s, %s, false, %s)
                    ON CONFLICT ("Usuario_id", "Plan_id")
                    DO UPDATE SET "Guardado" = EXCLUDED."Guardado"
                    """,
                    (user_id, plan_id, guardado),
                )
            connection.commit()
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

    # --- Bajarse / eliminar --------------------------------------------------

    def bajarse_de_plan(self, plan_id, user_id):
        """Saca al usuario de un plan (deja de estar confirmado). No
        borra el plan en sí, solo la relación de este usuario con él."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM public."Usuario-Plan"
                    WHERE "Plan_id" = %s AND "Usuario_id" = %s
                    """,
                    (plan_id, user_id),
                )
            connection.commit()
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

    def eliminar_plan(self, plan_id, user_id):
        """Borra el plan entero. Solo puede hacerlo quien lo creó.

        Devuelve True si lo borró, False si el usuario no es el creador
        (o el plan no existe)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT "Creado_Por" FROM public."Plan" WHERE "id_Plan" = %s',
                    (plan_id,),
                )
                fila = cursor.fetchone()
                if fila is None or str(fila[0]) != str(user_id):
                    return False

                # "Plan_Lugar" tiene ON DELETE CASCADE, pero
                # "Usuario-Plan" no, así que esa hay que borrarla a mano
                # antes de poder borrar el Plan.
                cursor.execute(
                    'DELETE FROM public."Usuario-Plan" WHERE "Plan_id" = %s',
                    (plan_id,),
                )
                cursor.execute(
                    'DELETE FROM public."Plan" WHERE "id_Plan" = %s',
                    (plan_id,),
                )

            connection.commit()
            return True
        except psycopg2.Error:
            connection.rollback()
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
                # Plan + relación del usuario + pertenencia al grupo, todo
                # en una sola consulta (antes eran 3 viajes a la base).
                cursor.execute(
                    """
                    SELECT
                        p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                        p."Grupo_id", g."Nombre", p."Descripcion", p."Creado_Por",
                        COALESCE(up."Confirmado", false),
                        COALESCE(up."Guardado", false),
                        EXISTS (
                            SELECT 1 FROM public."Usuario-Grupo" ug
                            WHERE ug."Id_Grupo" = p."Grupo_id" AND ug."Id_Usuario" = %s
                        ),
                        p."Precio_Min", p."Precio_Max"
                    FROM public."Plan" p
                    LEFT JOIN public."Grupos" g ON g."Id_Grupo" = p."Grupo_id"
                    LEFT JOIN public."Usuario-Plan" up
                           ON up."Plan_id" = p."id_Plan" AND up."Usuario_id" = %s
                    WHERE p."id_Plan" = %s
                    """,
                    (user_id, user_id, plan_id),
                )
                fila = cursor.fetchone()
                if fila is None:
                    return None

                confirmado = bool(fila[10])
                guardado = bool(fila[11])
                en_grupo = bool(fila[12])

                if not (confirmado or guardado or en_grupo):
                    return None

                return self._armar_plan(
                    cursor,
                    fila,
                    {
                        "grupo": fila[7],
                        "descripcion": fila[8],
                        "es_creador": str(fila[9]) == str(user_id),
                        "confirmado": confirmado,
                        "guardado": guardado,
                    },
                )
        except psycopg2.Error:
            raise
        finally:
            connection.close()