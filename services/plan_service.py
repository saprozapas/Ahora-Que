import threading
import time

import psycopg2

from database import get_db_connection
from services.precio_lugar import rango_de_nivel, sumar_rangos


# Texto para mostrar cada estado en pantalla.
ESTADOS_PLAN = {
    "idea": "Idea",
    "votacion": "En votación",
    "esperando_horario": "Esperando horario",
    "confirmado": "Confirmado",
    "rechazado": "Descartado",
    "vencido": "Vencido",
    "archivado": "Archivado",
    "activo": "Confirmado",
}

# El archivado automático corre como mucho una vez cada tantos segundos
# (en toda la app, no por usuario): es un UPDATE barato pero es un viaje
# más a la base.
_SEGUNDOS_MANTENIMIENTO = 60
_ultimo_mantenimiento = 0.0
_lock_mantenimiento = threading.Lock()


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
            "estado_texto": ESTADOS_PLAN.get(fila[5], fila[5]),
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

    # --- Mantenimiento ------------------------------------------------------

    def archivar_vencidos(self, forzar=False):
        """Pasa a "archivado" los planes de grupo confirmados que arrancaron
        hace 12 horas o más (ahí aparece la votación de puntaje y se
        publican en Social). También da por vencidas las votaciones y los
        horarios propuestos cuya fecha ya pasó.

        Las fechas del plan están en hora de Montevideo; la base corre en
        UTC, por eso se compara contra now() convertido."""
        global _ultimo_mantenimiento
        with _lock_mantenimiento:
            if not forzar and time.monotonic() - _ultimo_mantenimiento < _SEGUNDOS_MANTENIMIENTO:
                return
            _ultimo_mantenimiento = time.monotonic()

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public."Plan"
                    SET "Estado" = 'archivado'
                    WHERE "Estado" = 'confirmado'
                      AND "Grupo_id" IS NOT NULL
                      AND "Fecha" + COALESCE("Hora", '00:00'::time) + INTERVAL '12 hours'
                          <= (now() AT TIME ZONE 'America/Montevideo');

                    UPDATE public."Plan"
                    SET "Estado" = 'vencido'
                    WHERE "Estado" = 'votacion'
                      AND "Fecha" + COALESCE("Hora", '00:00'::time)
                          < (now() AT TIME ZONE 'America/Montevideo');

                    UPDATE public."Plan_Horario"
                    SET "Estado" = 'rechazado'
                    WHERE "Estado" = 'votacion'
                      AND "Fecha" + "Hora" < (now() AT TIME ZONE 'America/Montevideo');
                    """
                )
            connection.commit()
        except psycopg2.Error as e:
            connection.rollback()
            print(f"No se pudieron archivar los planes vencidos: {e}")
        finally:
            connection.close()

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
                      AND p."Estado" IN ('confirmado', 'activo')
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
        """Planes activos de los grupos del usuario que él todavía no
        confirmó: los que están en votación, esperando horario, o ya
        confirmados por otros (y a los que se puede sumar)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado", g."Nombre",
                           p."Grupo_id", p."Precio_Min", p."Precio_Max"
                    FROM public."Plan" p
                    JOIN public."Grupos" g ON g."Id_Grupo" = p."Grupo_id"
                    JOIN public."Usuario-Grupo" ug ON ug."Id_Grupo" = p."Grupo_id"
                    WHERE ug."Id_Usuario" = %s
                      AND p."Estado" IN ('votacion', 'esperando_horario', 'confirmado')
                      AND NOT EXISTS (
                          SELECT 1 FROM public."Usuario-Plan" up
                          WHERE up."Plan_id" = p."id_Plan"
                            AND up."Usuario_id" = %s
                            AND up."Confirmado" = true
                      )
                    ORDER BY p."Fecha" NULLS LAST, p."Hora"
                    """,
                    (user_id, user_id),
                )
                return self._armar_planes(
                    cursor, cursor.fetchall(),
                    lambda fila: {"grupo": fila[6], "grupo_id": fila[7]},
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

    def get_archivados(self, user_id):
        """Planes que el usuario hizo: los de grupo ya archivados (12 h
        después de arrancar) y, por compatibilidad, los individuales viejos
        cuya fecha ya pasó. Sirven también como ideas para postular."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                           g."Nombre", up."Puntaje",
                           p."Precio_Min", p."Precio_Max"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    LEFT JOIN public."Grupos" g ON g."Id_Grupo" = p."Grupo_id"
                    WHERE up."Usuario_id" = %s
                      AND up."Confirmado" = true
                      AND (p."Estado" = 'archivado'
                           OR (p."Grupo_id" IS NULL AND p."Fecha" < CURRENT_DATE))
                    ORDER BY p."Fecha" DESC, p."Hora" DESC
                    """,
                    (user_id,),
                )
                return self._armar_planes(
                    cursor, cursor.fetchall(),
                    lambda fila: {"grupo": fila[6], "mi_puntaje": fila[7]},
                )
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    def get_ideas_postulables(self, user_id):
        """Lo que el usuario puede postular en un grupo: sus guardados y
        sus archivados (sin repetir)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                           up."Guardado", p."Descripcion",
                           p."Precio_Min", p."Precio_Max"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    WHERE up."Usuario_id" = %s
                      AND (up."Guardado" = true
                           OR (up."Confirmado" = true
                               AND (p."Estado" = 'archivado'
                                    OR (p."Grupo_id" IS NULL AND p."Fecha" < CURRENT_DATE))))
                    ORDER BY up."Guardado" DESC, p."Nombre"
                    """,
                    (user_id,),
                )
                return self._armar_planes(
                    cursor, cursor.fetchall(),
                    lambda fila: {"guardado": bool(fila[6]), "descripcion": fila[7]},
                )
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    # --- Creación --------------------------------------------------------

    def crear_idea(self, user_id, nombre, descripcion, lugares):
        """Crea una IDEA: un plan sin fecha, sin hora y sin grupo, que queda
        en los Guardados del usuario. Después se puede postular en un grupo
        (ahí se elige la fecha y se vota).

        lugares: lista de dicts con las paradas, en orden:
                 {"id_lugar": uuid o None, "nombre": str,
                  "nivel_precio": 0-4 o None, "hora": "HH:MM" o None}
                 Puede venir vacía: un plan sin lugar específico
                 (por ejemplo "llamada a las 8") es válido.

        El precio no lo elige el usuario: se estima sumando el rango de
        cada lugar según su Nivel_Precio (ver services/precio_lugar.py).

        Devuelve el id de la idea creada.
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
                # Fecha y Hora van en NULL (es una idea). Grupo_id y Lugar_id van en NULL explícito: así no se
                # activa el DEFAULT gen_random_uuid() que tienen esas
                # columnas (que generaría un uuid inexistente y rompería
                # la foreign key). Las paradas van en "Plan_Lugar".
                cursor.execute(
                    """
                    INSERT INTO public."Plan"
                        ("Nombre", "Fecha", "Hora", "Descripcion",
                         "Precio_Min", "Precio_Max",
                         "Creado_Por", "Estado", "Grupo_id", "Lugar_id")
                    VALUES (%s, NULL, NULL, %s, %s, %s, %s, 'idea', NULL, NULL)
                    RETURNING "id_Plan"
                    """,
                    (nombre, descripcion,
                     precio_min_total, precio_max_total, user_id),
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
                    VALUES (%s, %s, false, true)
                    """,
                    (user_id, plan_id),
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

    # --- Sumarse / bajarse / eliminar ---------------------------------------

    def sumarse_a_plan(self, plan_id, user_id):
        """Un integrante del grupo que no había dicho que podía se suma a
        un plan ya confirmado. Devuelve True si se pudo."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public."Usuario-Plan" ("Usuario_id", "Plan_id", "Confirmado", "Guardado")
                    SELECT %(uid)s, p."id_Plan", true, false
                    FROM public."Plan" p
                    JOIN public."Usuario-Grupo" ug
                         ON ug."Id_Grupo" = p."Grupo_id" AND ug."Id_Usuario" = %(uid)s
                    WHERE p."id_Plan" = %(pid)s AND p."Estado" = 'confirmado'
                    ON CONFLICT ("Usuario_id", "Plan_id")
                    DO UPDATE SET "Confirmado" = true
                    """,
                    {"uid": user_id, "pid": plan_id},
                )
                ok = cursor.rowcount > 0
            connection.commit()
            return ok
        except psycopg2.Error:
            connection.rollback()
            raise
        finally:
            connection.close()


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

    # --- Social: planes de amigos -------------------------------------------

    # Niveles de puntaje que se van probando, de mayor a menor. None = todos
    # los planes (incluidos los que nadie puntuó todavía).
    NIVELES_SOCIAL = [4, 3, 2, 1, None]

    def _amigos_sql(self):
        """Subconsulta con los ids de los amigos de %(uid)s."""
        return """
            SELECT CASE WHEN a."Id_Usuario1" = %(uid)s
                        THEN a."Id_Usuario2" ELSE a."Id_Usuario1" END
            FROM public."Amistades" a
            WHERE %(uid)s IN (a."Id_Usuario1", a."Id_Usuario2")
        """

    def get_planes_amigos_semana(self, user_id):
        """Planes archivados (ya hechos y publicados) de los últimos 7 días
        en los que participó al menos un amigo y el usuario no. Cada plan trae el
        promedio de puntaje de sus participantes y qué amigos fueron."""
        amigos = self._amigos_sql()
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                           ROUND(AVG(up."Puntaje")::numeric, 1),
                           COUNT(up."Puntaje"),
                           ARRAY_AGG(DISTINCT u."Nombre")
                               FILTER (WHERE up."Usuario_id" IN ({amigos})),
                           p."Precio_Min", p."Precio_Max"
                    FROM public."Plan" p
                    JOIN public."Usuario-Plan" up
                         ON up."Plan_id" = p."id_Plan" AND up."Confirmado" = true
                    JOIN public."Usuarios" u ON u."Id_Usuario" = up."Usuario_id"
                    WHERE p."Estado" = 'archivado'
                      AND p."Fecha" BETWEEN CURRENT_DATE - 7 AND CURRENT_DATE
                    GROUP BY p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio",
                             p."Estado", p."Precio_Min", p."Precio_Max"
                    HAVING BOOL_OR(up."Usuario_id" IN ({amigos}))
                       AND NOT BOOL_OR(up."Usuario_id" = %(uid)s)
                    ORDER BY AVG(up."Puntaje") DESC NULLS LAST,
                             COUNT(up."Puntaje") DESC,
                             p."Fecha" DESC
                    """,
                    {"uid": user_id},
                )
                return self._armar_planes(
                    cursor,
                    cursor.fetchall(),
                    lambda fila: {
                        "promedio": float(fila[6]) if fila[6] is not None else None,
                        "votos": fila[7],
                        "amigos": fila[8] or [],
                    },
                )
        except psycopg2.Error:
            raise
        finally:
            connection.close()

    def _filtrar_por_nivel(self, planes, nivel):
        if nivel is None:
            return planes
        return [p for p in planes if p["promedio"] is not None and p["promedio"] >= nivel]

    def get_sugerencias_amigos(self, user_id, nivel=4):
        """Arranca mostrando los planes con promedio >= nivel. Si no hay
        ninguno, va bajando (4 -> 3 -> 2 -> 1 -> todos) hasta encontrar.

        Devuelve el nivel que se terminó usando y cuál es el siguiente
        nivel que agregaría planes nuevos (para el botón "Ver más")."""
        planes = self.get_planes_amigos_semana(user_id)
        niveles = self.NIVELES_SOCIAL
        inicio = niveles.index(nivel) if nivel in niveles else 0

        elegidos, nivel_usado = [], None
        for nivel_usado in niveles[inicio:]:
            elegidos = self._filtrar_por_nivel(planes, nivel_usado)
            if elegidos:
                break

        siguiente = None
        hay_siguiente = False
        for otro in niveles[niveles.index(nivel_usado) + 1:]:
            if len(self._filtrar_por_nivel(planes, otro)) > len(elegidos):
                siguiente, hay_siguiente = otro, True
                break

        return {
            "planes": elegidos,
            "nivel": nivel_usado,
            "hay_siguiente": hay_siguiente,
            "siguiente_nivel": siguiente,
            "total": len(planes),
        }

    # --- Puntaje ------------------------------------------------------------

    def set_puntaje(self, plan_id, user_id, puntaje):
        """Guarda el puntaje (0-5) del usuario para el plan. Solo se puede
        si fue al plan (lo confirmó) y el plan ya está archivado, o sea,
        pasaron 12 h desde que arrancó. Devuelve True si se guardó."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public."Usuario-Plan" up
                    SET "Puntaje" = %s
                    FROM public."Plan" p
                    WHERE p."id_Plan" = up."Plan_id"
                      AND up."Plan_id" = %s
                      AND up."Usuario_id" = %s
                      AND up."Confirmado" = true
                      AND p."Estado" = 'archivado'
                    """,
                    (puntaje, plan_id, user_id),
                )
                guardado = cursor.rowcount > 0
            connection.commit()
            return guardado
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
                    f"""
                    SELECT
                        p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                        p."Grupo_id", g."Nombre", p."Descripcion", p."Creado_Por",
                        COALESCE(up."Confirmado", false),
                        COALESCE(up."Guardado", false),
                        EXISTS (
                            SELECT 1 FROM public."Usuario-Grupo" ug
                            WHERE ug."Id_Grupo" = p."Grupo_id" AND ug."Id_Usuario" = %(uid)s
                        ),
                        up."Puntaje",
                        (SELECT ROUND(AVG(x."Puntaje")::numeric, 1)
                           FROM public."Usuario-Plan" x WHERE x."Plan_id" = p."id_Plan"),
                        (SELECT COUNT(x."Puntaje")
                           FROM public."Usuario-Plan" x WHERE x."Plan_id" = p."id_Plan"),
                        EXISTS (
                            SELECT 1 FROM public."Usuario-Plan" x
                            WHERE x."Plan_id" = p."id_Plan"
                              AND x."Confirmado" = true
                              AND x."Usuario_id" IN ({self._amigos_sql()})
                        ),
                        p."Precio_Min", p."Precio_Max"
                    FROM public."Plan" p
                    LEFT JOIN public."Grupos" g ON g."Id_Grupo" = p."Grupo_id"
                    LEFT JOIN public."Usuario-Plan" up
                           ON up."Plan_id" = p."id_Plan" AND up."Usuario_id" = %(uid)s
                    WHERE p."id_Plan" = %(pid)s
                    """,
                    {"uid": user_id, "pid": plan_id},
                )
                fila = cursor.fetchone()
                if fila is None:
                    return None

                confirmado = bool(fila[10])
                guardado = bool(fila[11])
                en_grupo = bool(fila[12])
                fue_un_amigo = bool(fila[16])

                if not (confirmado or guardado or en_grupo or fue_un_amigo):
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
                        "mi_puntaje": fila[13],
                        "promedio": float(fila[14]) if fila[14] is not None else None,
                        "votos": fila[15],
                        "grupo_id": fila[6],
                        "puede_puntuar": confirmado and fila[5] == "archivado",
                    },
                )
        except psycopg2.Error:
            raise
        finally:
            connection.close()