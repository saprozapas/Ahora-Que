"""Planes dentro de un grupo: postular ideas, votarlas y elegir horario.

Flujo de un plan de grupo (columna "Plan"."Estado"):

    idea guardada --postular--> votacion
        votacion: cada integrante vota "¿me gusta?" y "¿puedo en esa fecha?".
        La votación se resuelve cuando votaron TODOS los integrantes, o
        antes si el creador del plan la cierra a mano:
          - me gusta < UMBRAL_GUSTA          -> rechazado
          - me gusta ok y puedo >= UMBRAL    -> confirmado (se confirma a
                                                 los que votaron "puedo")
          - me gusta ok pero no pueden       -> esperando_horario
        esperando_horario: cualquiera propone fecha/hora y se vota "puedo /
        no puedo". Mismo criterio de cierre; el primer horario aprobado
        confirma el plan con esa fecha.
    confirmado --12 h después de arrancar--> archivado (ver
        PlanService.archivar_vencidos): se puntúa y se publica en Social.

Los porcentajes se calculan sobre los votos emitidos.
"""

import psycopg2

from database import get_db_connection, release_db_connection
from services.plan_service import PlanService

# Mínimo de "me gusta" para que la idea pase (se puede cambiar más adelante).
UMBRAL_GUSTA = 0.66
# Mínimo de "puedo" para que una fecha/hora quede confirmada.
UMBRAL_PUEDEN = 0.66


class GrupoPlanError(Exception):
    """Error pensado para mostrarle al usuario tal cual (flash)."""


class GrupoPlanService:

    def __init__(self):
        self._planes = PlanService()

    # --- Helpers ------------------------------------------------------------

    def _plan_del_grupo(self, cursor, plan_id, group_id, user_id):
        """Devuelve (estado, creado_por, miembros) si el plan es de ese grupo
        y el usuario es integrante. Si no, levanta GrupoPlanError."""
        cursor.execute(
            """
            SELECT p."Estado", p."Creado_Por",
                   (SELECT COUNT(*) FROM public."Usuario-Grupo" x WHERE x."Id_Grupo" = p."Grupo_id")
            FROM public."Plan" p
            JOIN public."Usuario-Grupo" ug
                 ON ug."Id_Grupo" = p."Grupo_id" AND ug."Id_Usuario" = %(uid)s
            WHERE p."id_Plan" = %(pid)s AND p."Grupo_id" = %(gid)s
            """,
            {"uid": user_id, "pid": plan_id, "gid": group_id},
        )
        fila = cursor.fetchone()
        if fila is None:
            raise GrupoPlanError("Ese plan no es de este grupo.")
        return fila[0], fila[1], fila[2]

    def _confirmar_usuarios(self, cursor, plan_id, user_ids):
        for uid in user_ids:
            cursor.execute(
                """
                INSERT INTO public."Usuario-Plan" ("Usuario_id", "Plan_id", "Confirmado", "Guardado")
                VALUES (%s, %s, true, false)
                ON CONFLICT ("Usuario_id", "Plan_id") DO UPDATE SET "Confirmado" = true
                """,
                (uid, plan_id),
            )

    def _resolver_votacion(self, cursor, plan_id, forzar=False):
        """Si ya votaron todos (o forzar), decide el destino del plan.
        Devuelve el estado nuevo, o None si todavía no se resolvió."""
        cursor.execute(
            """
            SELECT p."Estado",
                   (SELECT COUNT(*) FROM public."Usuario-Grupo" x WHERE x."Id_Grupo" = p."Grupo_id"),
                   COUNT(v."Id_Usuario"),
                   COUNT(*) FILTER (WHERE v."Me_Gusta"),
                   COUNT(*) FILTER (WHERE v."Puedo")
            FROM public."Plan" p
            LEFT JOIN public."Plan_Voto" v ON v."Id_Plan" = p."id_Plan"
            WHERE p."id_Plan" = %s
            GROUP BY p."id_Plan", p."Estado", p."Grupo_id"
            """,
            (plan_id,),
        )
        estado, miembros, votos, gustan, pueden = cursor.fetchone()
        if estado != "votacion" or votos == 0:
            return None
        if votos < miembros and not forzar:
            return None

        if gustan / votos < UMBRAL_GUSTA:
            nuevo = "rechazado"
        elif pueden / votos >= UMBRAL_PUEDEN:
            nuevo = "confirmado"
            cursor.execute(
                'SELECT "Id_Usuario" FROM public."Plan_Voto" WHERE "Id_Plan" = %s AND "Puedo"',
                (plan_id,),
            )
            self._confirmar_usuarios(cursor, plan_id, [f[0] for f in cursor.fetchall()])
        else:
            nuevo = "esperando_horario"

        cursor.execute(
            'UPDATE public."Plan" SET "Estado" = %s WHERE "id_Plan" = %s',
            (nuevo, plan_id),
        )
        return nuevo

    def _resolver_horario(self, cursor, horario_id, forzar=False):
        """Igual que _resolver_votacion pero para un horario propuesto.
        Devuelve 'aprobado', 'rechazado' o None."""
        cursor.execute(
            """
            SELECT h."Estado", h."Id_Plan", h."Fecha", h."Hora", p."Estado",
                   (SELECT COUNT(*) FROM public."Usuario-Grupo" x WHERE x."Id_Grupo" = p."Grupo_id"),
                   COUNT(hv."Id_Usuario"),
                   COUNT(*) FILTER (WHERE hv."Puedo")
            FROM public."Plan_Horario" h
            JOIN public."Plan" p ON p."id_Plan" = h."Id_Plan"
            LEFT JOIN public."Plan_Horario_Voto" hv ON hv."Id_Horario" = h."Id_Horario"
            WHERE h."Id_Horario" = %s
            GROUP BY h."Id_Horario", h."Estado", h."Id_Plan", h."Fecha", h."Hora",
                     p."Estado", p."Grupo_id"
            """,
            (horario_id,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        estado_h, plan_id, fecha, hora, estado_p, miembros, votos, pueden = fila
        if estado_h != "votacion" or estado_p != "esperando_horario" or votos == 0:
            return None
        if votos < miembros and not forzar:
            return None

        if pueden / votos < UMBRAL_PUEDEN:
            cursor.execute(
                """UPDATE public."Plan_Horario" SET "Estado" = 'rechazado' WHERE "Id_Horario" = %s""",
                (horario_id,),
            )
            return "rechazado"

        cursor.execute(
            """
            UPDATE public."Plan" SET "Fecha" = %s, "Hora" = %s, "Estado" = 'confirmado'
            WHERE "id_Plan" = %s
            """,
            (fecha, hora, plan_id),
        )
        cursor.execute(
            """
            UPDATE public."Plan_Horario"
            SET "Estado" = CASE WHEN "Id_Horario" = %s THEN 'aprobado' ELSE 'rechazado' END
            WHERE "Id_Plan" = %s AND "Estado" = 'votacion'
            """,
            (horario_id, plan_id),
        )
        cursor.execute(
            'SELECT "Id_Usuario" FROM public."Plan_Horario_Voto" WHERE "Id_Horario" = %s AND "Puedo"',
            (horario_id,),
        )
        self._confirmar_usuarios(cursor, plan_id, [f[0] for f in cursor.fetchall()])
        return "aprobado"

    # --- Tablero del grupo --------------------------------------------------

    def get_tablero(self, group_id, user_id):
        """Todo lo que se muestra en la página del grupo, separado por
        estado. Son 3-4 viajes a la base en total."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                           p."Creado_Por", uc."Nombre", p."Descripcion",
                           cv.votos, cv.gustan, cv.pueden,
                           mv."Me_Gusta", mv."Puedo",
                           (SELECT ARRAY_AGG(u."Nombre" ORDER BY u."Nombre")
                              FROM public."Usuario-Plan" up
                              JOIN public."Usuarios" u ON u."Id_Usuario" = up."Usuario_id"
                             WHERE up."Plan_id" = p."id_Plan" AND up."Confirmado"),
                           COALESCE(mp."Confirmado", false), mp."Puntaje",
                           (SELECT COUNT(*) FROM public."Usuario-Grupo" x WHERE x."Id_Grupo" = p."Grupo_id"),
                           p."Precio_Min", p."Precio_Max"
                    FROM public."Plan" p
                    LEFT JOIN public."Usuarios" uc ON uc."Id_Usuario" = p."Creado_Por"
                    LEFT JOIN LATERAL (
                        SELECT COUNT(*) AS votos,
                               COUNT(*) FILTER (WHERE v."Me_Gusta") AS gustan,
                               COUNT(*) FILTER (WHERE v."Puedo") AS pueden
                        FROM public."Plan_Voto" v WHERE v."Id_Plan" = p."id_Plan"
                    ) cv ON true
                    LEFT JOIN public."Plan_Voto" mv
                           ON mv."Id_Plan" = p."id_Plan" AND mv."Id_Usuario" = %(uid)s
                    LEFT JOIN public."Usuario-Plan" mp
                           ON mp."Plan_id" = p."id_Plan" AND mp."Usuario_id" = %(uid)s
                    WHERE p."Grupo_id" = %(gid)s
                      AND (p."Estado" IN ('votacion', 'esperando_horario', 'confirmado')
                           OR (p."Estado" = 'archivado' AND mp."Confirmado" AND mp."Puntaje" IS NULL))
                    ORDER BY p."Fecha" NULLS LAST, p."Hora"
                    """,
                    {"uid": user_id, "gid": group_id},
                )
                planes = self._planes._armar_planes(
                    cursor,
                    cursor.fetchall(),
                    lambda f: {
                        "creado_por": f[6],
                        "es_creador": str(f[6]) == str(user_id),
                        "creador": f[7],
                        "descripcion": f[8],
                        "votos": f[9],
                        "gustan": f[10],
                        "pueden": f[11],
                        "mi_gusta": f[12],
                        "mi_puedo": f[13],
                        "van": f[14] or [],
                        "confirmado": bool(f[15]),
                        "mi_puntaje": f[16],
                        "miembros": f[17],
                        "horarios": [],
                    },
                )

                esperando = {p["id"]: p for p in planes if p["estado"] == "esperando_horario"}
                if esperando:
                    cursor.execute(
                        """
                        SELECT h."Id_Horario", h."Id_Plan", h."Fecha", h."Hora", u."Nombre",
                               COUNT(hv."Id_Usuario"),
                               COUNT(*) FILTER (WHERE hv."Puedo"),
                               BOOL_OR(hv."Puedo") FILTER (WHERE hv."Id_Usuario" = %(uid)s)
                        FROM public."Plan_Horario" h
                        JOIN public."Usuarios" u ON u."Id_Usuario" = h."Propuesto_Por"
                        LEFT JOIN public."Plan_Horario_Voto" hv ON hv."Id_Horario" = h."Id_Horario"
                        WHERE h."Id_Plan" IN %(ids)s AND h."Estado" = 'votacion'
                        GROUP BY h."Id_Horario", u."Nombre"
                        ORDER BY h."Fecha", h."Hora"
                        """,
                        {"uid": user_id, "ids": tuple(esperando)},
                    )
                    for f in cursor.fetchall():
                        esperando[f[1]]["horarios"].append({
                            "id": f[0], "fecha": f[2], "hora": f[3], "propuesto_por": f[4],
                            "votos": f[5], "pueden": f[6], "mi_puedo": f[7],
                        })

            return {
                "votacion": [p for p in planes if p["estado"] == "votacion"],
                "esperando_horario": list(esperando.values()),
                "confirmados": [p for p in planes if p["estado"] == "confirmado"],
                "para_puntuar": [p for p in planes if p["estado"] == "archivado"],
            }
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    # --- Postular -------------------------------------------------------------

    def postular_idea(self, group_id, user_id, idea_id, fecha, hora):
        """Copia una idea del usuario (guardada o archivada) como plan nuevo
        del grupo, con la fecha y hora que eligió, y la pone en votación.
        El que la postula ya cuenta como "me gusta" y "puedo".

        Se copia (en vez de mover) para que la idea original le siga
        quedando al usuario y la pueda postular en otros grupos."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        EXISTS (SELECT 1 FROM public."Usuario-Grupo"
                                WHERE "Id_Grupo" = %(gid)s AND "Id_Usuario" = %(uid)s),
                        EXISTS (SELECT 1 FROM public."Usuario-Plan"
                                WHERE "Plan_id" = %(idea)s AND "Usuario_id" = %(uid)s
                                  AND ("Guardado" OR "Confirmado"))
                    """,
                    {"gid": group_id, "uid": user_id, "idea": idea_id},
                )
                es_miembro, tiene_idea = cursor.fetchone()
                if not es_miembro:
                    raise GrupoPlanError("No sos integrante de este grupo.")
                if not tiene_idea:
                    raise GrupoPlanError("Esa idea no está en tus guardados ni archivados.")

                cursor.execute(
                    """
                    INSERT INTO public."Plan"
                        ("Nombre", "Fecha", "Hora", "Descripcion", "Precio",
                         "Precio_Min", "Precio_Max", "Creado_Por", "Estado", "Grupo_id", "Lugar_id")
                    SELECT "Nombre", %(fecha)s, %(hora)s, "Descripcion", "Precio",
                           "Precio_Min", "Precio_Max", %(uid)s, 'votacion', %(gid)s, "Lugar_id"
                    FROM public."Plan" WHERE "id_Plan" = %(idea)s
                    RETURNING "id_Plan"
                    """,
                    {"fecha": fecha, "hora": hora, "uid": user_id, "gid": group_id, "idea": idea_id},
                )
                plan_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO public."Plan_Lugar"
                        ("Id_Plan", "Id_Lugar", "Nombre", "Precio_Min", "Precio_Max", "Hora", "Orden")
                    SELECT %s, "Id_Lugar", "Nombre", "Precio_Min", "Precio_Max", "Hora", "Orden"
                    FROM public."Plan_Lugar" WHERE "Id_Plan" = %s
                    """,
                    (plan_id, idea_id),
                )
                cursor.execute(
                    """
                    INSERT INTO public."Plan_Voto" ("Id_Plan", "Id_Usuario", "Me_Gusta", "Puedo")
                    VALUES (%s, %s, true, true)
                    """,
                    (plan_id, user_id),
                )
                # Si el grupo es de una sola persona, se resuelve ya.
                self._resolver_votacion(cursor, plan_id)
            connection.commit()
            return plan_id
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Votar el plan ----------------------------------------------------------

    def votar_plan(self, group_id, plan_id, user_id, me_gusta, puedo):
        """Guarda (o cambia) el voto. Devuelve el estado nuevo si con este
        voto se resolvió la votación, o None."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                estado, _, _ = self._plan_del_grupo(cursor, plan_id, group_id, user_id)
                if estado != "votacion":
                    raise GrupoPlanError("La votación de este plan ya se cerró.")
                cursor.execute(
                    """
                    INSERT INTO public."Plan_Voto" ("Id_Plan", "Id_Usuario", "Me_Gusta", "Puedo")
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT ("Id_Plan", "Id_Usuario")
                    DO UPDATE SET "Me_Gusta" = EXCLUDED."Me_Gusta",
                                  "Puedo" = EXCLUDED."Puedo",
                                  "Fecha" = now()
                    """,
                    (plan_id, user_id, me_gusta, puedo),
                )
                resultado = self._resolver_votacion(cursor, plan_id)
            connection.commit()
            return resultado
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def cerrar_votacion(self, group_id, plan_id, user_id):
        """El creador cierra la votación sin esperar a que voten todos."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                estado, creado_por, _ = self._plan_del_grupo(cursor, plan_id, group_id, user_id)
                if str(creado_por) != str(user_id):
                    raise GrupoPlanError("Solo quien postuló el plan puede cerrar la votación.")
                if estado != "votacion":
                    raise GrupoPlanError("La votación de este plan ya se cerró.")
                resultado = self._resolver_votacion(cursor, plan_id, forzar=True)
            connection.commit()
            return resultado
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Horarios -----------------------------------------------------------------

    def proponer_horario(self, group_id, plan_id, user_id, fecha, hora):
        """Propone una fecha/hora nueva para un plan que gustó pero en el
        que no podían. Quien lo propone ya cuenta como "puedo"."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                estado, _, _ = self._plan_del_grupo(cursor, plan_id, group_id, user_id)
                if estado != "esperando_horario":
                    raise GrupoPlanError("Este plan no está esperando horario.")
                cursor.execute(
                    """
                    INSERT INTO public."Plan_Horario" ("Id_Plan", "Propuesto_Por", "Fecha", "Hora")
                    VALUES (%s, %s, %s, %s)
                    RETURNING "Id_Horario"
                    """,
                    (plan_id, user_id, fecha, hora),
                )
                horario_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO public."Plan_Horario_Voto" ("Id_Horario", "Id_Usuario", "Puedo")
                    VALUES (%s, %s, true)
                    """,
                    (horario_id, user_id),
                )
                resultado = self._resolver_horario(cursor, horario_id)
            connection.commit()
            return resultado
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def _horario_del_grupo(self, cursor, horario_id, group_id, user_id):
        cursor.execute(
            'SELECT "Id_Plan" FROM public."Plan_Horario" WHERE "Id_Horario" = %s',
            (horario_id,),
        )
        fila = cursor.fetchone()
        if fila is None:
            raise GrupoPlanError("Ese horario no existe.")
        return fila[0], self._plan_del_grupo(cursor, fila[0], group_id, user_id)

    def votar_horario(self, group_id, horario_id, user_id, puedo):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                _, (estado, _, _) = self._horario_del_grupo(cursor, horario_id, group_id, user_id)
                if estado != "esperando_horario":
                    raise GrupoPlanError("Este plan ya tiene horario.")
                cursor.execute(
                    """
                    INSERT INTO public."Plan_Horario_Voto" ("Id_Horario", "Id_Usuario", "Puedo")
                    VALUES (%s, %s, %s)
                    ON CONFLICT ("Id_Horario", "Id_Usuario") DO UPDATE SET "Puedo" = EXCLUDED."Puedo"
                    """,
                    (horario_id, user_id, puedo),
                )
                resultado = self._resolver_horario(cursor, horario_id)
            connection.commit()
            return resultado
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def cerrar_horario(self, group_id, horario_id, user_id):
        """El creador del plan cierra la votación de un horario."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                _, (estado, creado_por, _) = self._horario_del_grupo(cursor, horario_id, group_id, user_id)
                if str(creado_por) != str(user_id):
                    raise GrupoPlanError("Solo quien postuló el plan puede cerrar la votación.")
                resultado = self._resolver_horario(cursor, horario_id, forzar=True)
            connection.commit()
            return resultado
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)
