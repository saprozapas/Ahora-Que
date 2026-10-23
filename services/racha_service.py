from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from database import get_db_connection, release_db_connection


_MONTEVIDEO = ZoneInfo("America/Montevideo")
_DIAS_SEMANA = ("L", "M", "M", "J", "V", "S", "D")
_HITOS = (3, 5, 10, 20, 30, 40, 50, 70, 90, 100)
# Los rangos son los planetas, del Sol hacia afuera. El mismo rango es el título que muestra el chip
# y el marco de la tarjeta. Los hitos que no están acá (5, 30, 50 y 90) son marcas del viaje sin rango.
# En la base se guardan las semanas, no el nombre: renombrar un rango es cambiar solo este diccionario
# y los textos de templates/_macros.html.
_RANGOS = {3: "mercurio", 10: "venus", 20: "tierra", 40: "marte", 70: "jupiter", 100: "saturno"}
_MARCOS = _RANGOS
_COLORES_TITULO = _RANGOS


def _color_fuego(semanas):
    if semanas <= 10:
        return "normal"
    if semanas <= 30:
        return "verde"
    if semanas <= 70:
        return "violeta"
    return "azul"


class RachaService:
    """Calcula y persiste la racha de reuniones de un grupo."""

    def obtener_resumenes(self, group_ids):
        """Lee de una vez los datos que muestran las tarjetas de grupos."""
        if not group_ids:
            return {}

        hoy = datetime.now(_MONTEVIDEO).date()
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''
                    SELECT r."Id_Grupo", r."Semanas", r."Ultima_Reunion",
                           r."Activa", a."Marco_Semanas", a."Titulo_Semanas",
                           ARRAY(
                               SELECT i."Semanas"
                               FROM public."Grupo_Insignia" i
                               WHERE i."Id_Grupo" = r."Id_Grupo"
                           )
                    FROM public."Rachas" r
                    LEFT JOIN public."Grupo_Apariencia" a
                      ON a."Id_Grupo" = r."Id_Grupo"
                    WHERE r."Id_Grupo" = ANY(%s::uuid[])
                    ''',
                    (group_ids,),
                )
                filas = cursor.fetchall()

            resumenes = {}
            for group_id, semanas_guardadas, ultima, _activa_guardada, marco_guardado, titulo_guardado, hitos in filas:
                semanas = semanas_guardadas or 0
                dias_desde_ultima = (hoy - ultima).days if ultima else None
                if dias_desde_ultima is None or dias_desde_ultima >= 14:
                    semanas = 0
                activa = semanas > 0 and dias_desde_ultima < 7

                hitos = set(hitos or [])
                marcos = sorted(hitos.intersection(_MARCOS))
                titulos = sorted(hitos.intersection(_COLORES_TITULO))
                marco = marco_guardado if marco_guardado in marcos else (max(marcos) if marcos else None)
                # El rango es uno solo: el título del chip siempre es el mismo planeta que el marco.
                # (El "Titulo_Semanas" viejo de la base puede quedar en otro rango y se ignora.)
                titulo = marco
                resumenes[group_id] = {
                    "activa": activa,
                    "semanas": semanas,
                    "fuego": _color_fuego(semanas),
                    "marco": _MARCOS.get(marco),
                    "titulo_color": _COLORES_TITULO.get(titulo),
                }
            return resumenes
        finally:
            release_db_connection(conn)

    def actualizar_racha(self, group_id):
        """Acumula solo planes nuevos y persiste el punto de control.

        Las semanas y los planes ya contabilizados quedan en Rachas, así que
        borrar planes viejos no modifica el acumulado. Una semana ISO suma
        como máximo una vez; la racha se pausa a los 7 días y se reinicia
        a los 14 días sin reunión.
        """
        hoy = datetime.now(_MONTEVIDEO).date()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''
                    SELECT "Activa", "Semanas", "Ultima_Reunion",
                           "Ultimo_Plan_Procesado", "Planes_Hechos"
                    FROM public."Rachas"
                    WHERE "Id_Grupo" = %s
                    ''',
                    (group_id,),
                )
                estado_guardado = cursor.fetchone()
                if estado_guardado:
                    _activa_guardada, semanas, ultima_reunion, ultimo_procesado, planes_hechos = estado_guardado
                    planes_hechos = planes_hechos or 0
                    # Migración gradual de filas creadas antes del checkpoint:
                    # conserva el contador ya guardado y marca como procesado
                    # todo lo que ocurrió hasta el último día contabilizado.
                    if ultimo_procesado is None and ultima_reunion is not None:
                        ultimo_procesado = datetime.combine(ultima_reunion, time.max)
                        cursor.execute(
                            '''
                            SELECT COUNT(*)
                            FROM public."Plan"
                            WHERE "Grupo_id" = %s
                              AND "Fecha" IS NOT NULL
                              AND (
                                "Estado" = 'archivado'
                                OR (
                                  "Estado" = 'confirmado'
                                  AND "Fecha" + COALESCE("Hora", '00:00'::time)
                                      <= (now() AT TIME ZONE 'America/Montevideo')
                                )
                              )
                            ''',
                            (group_id,),
                        )
                        planes_hechos = cursor.fetchone()[0]
                else:
                    semanas = 0
                    ultima_reunion = None
                    ultimo_procesado = None
                    planes_hechos = 0

                cursor.execute(
                    '''
                    SELECT "Fecha" + COALESCE("Hora", '00:00'::time) AS reunion
                    FROM public."Plan"
                    WHERE "Grupo_id" = %s
                      AND "Fecha" IS NOT NULL
                      AND (
                        "Estado" = 'archivado'
                        OR (
                          "Estado" = 'confirmado'
                          AND "Fecha" + COALESCE("Hora", '00:00'::time)
                              <= (now() AT TIME ZONE 'America/Montevideo')
                        )
                      )
                      AND "Fecha" + COALESCE("Hora", '00:00'::time)
                          > COALESCE(%s::timestamp, '-infinity'::timestamp)
                    ORDER BY reunion
                    ''',
                    (group_id, ultimo_procesado),
                )
                planes_nuevos = cursor.fetchall()

                for (reunion_at,) in planes_nuevos:
                    fecha = reunion_at.date()
                    if ultima_reunion and (fecha - ultima_reunion).days >= 14:
                        semanas = 0
                    if ultima_reunion is None or fecha.isocalendar()[:2] != ultima_reunion.isocalendar()[:2]:
                        semanas += 1
                    ultima_reunion = fecha
                    ultimo_procesado = reunion_at
                planes_hechos += len(planes_nuevos)

                if ultima_reunion is None or (hoy - ultima_reunion).days >= 14:
                    semanas = 0
                    activa = False
                else:
                    activa = semanas > 0 and (hoy - ultima_reunion).days < 7

                cursor.execute(
                    '''
                    INSERT INTO public."Rachas"
                        ("Id_Grupo", "Activa", "Semanas", "Ultima_Reunion",
                         "Ultimo_Plan_Procesado", "Planes_Hechos")
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT ("Id_Grupo") DO UPDATE SET
                        "Activa" = EXCLUDED."Activa",
                        "Semanas" = EXCLUDED."Semanas",
                        "Ultima_Reunion" = EXCLUDED."Ultima_Reunion",
                        "Ultimo_Plan_Procesado" = EXCLUDED."Ultimo_Plan_Procesado",
                        "Planes_Hechos" = EXCLUDED."Planes_Hechos"
                    ''',
                    (group_id, activa, semanas, ultima_reunion, ultimo_procesado, planes_hechos),
                )

                # Los logros son permanentes aunque la racha actual se reinicie.
                hitos_a_insertar = [hito for hito in _HITOS if semanas >= hito]
                if hitos_a_insertar:
                    cursor.execute(
                        '''
                        INSERT INTO public."Grupo_Insignia" ("Id_Grupo", "Semanas")
                        SELECT %s, hito
                        FROM UNNEST(%s::integer[]) AS hitos(hito)
                        ON CONFLICT ("Id_Grupo", "Semanas") DO NOTHING
                        ''',
                        (group_id, hitos_a_insertar),
                    )
                cursor.execute(
                    'SELECT "Semanas" FROM public."Grupo_Insignia" WHERE "Id_Grupo" = %s',
                    (group_id,),
                )
                hitos_desbloqueados = {fila[0] for fila in cursor.fetchall()}
                cursor.execute(
                    '''SELECT "Marco_Semanas", "Titulo_Semanas"
                       FROM public."Grupo_Apariencia" WHERE "Id_Grupo" = %s''',
                    (group_id,),
                )
                apariencia = cursor.fetchone()
                marco_seleccionado, titulo_seleccionado = apariencia or (None, None)

                cursor.execute(
                    '''
                    SELECT DISTINCT "Fecha"
                    FROM public."Plan"
                    WHERE "Grupo_id" = %s
                      AND "Fecha" BETWEEN %s AND %s
                      AND (
                        "Estado" = 'archivado'
                        OR (
                          "Estado" = 'confirmado'
                          AND "Fecha" + COALESCE("Hora", '00:00'::time)
                              <= (now() AT TIME ZONE 'America/Montevideo')
                        )
                      )
                    ''',
                    (group_id, inicio_semana, hoy),
                )
                reuniones_semana = {fila[0] for fila in cursor.fetchall()}

            conn.commit()
            proximo_hito = next((hito for hito in _HITOS if hito not in hitos_desbloqueados), None)
            marcos_desbloqueados = [hito for hito in _MARCOS if hito in hitos_desbloqueados]
            titulos_desbloqueados = sorted(h for h in hitos_desbloqueados if h in _COLORES_TITULO)
            if marco_seleccionado not in marcos_desbloqueados:
                marco_seleccionado = max(marcos_desbloqueados) if marcos_desbloqueados else None
            # Un solo rango: el título es siempre el mismo planeta que el marco.
            titulo_seleccionado = marco_seleccionado
            calendario = [
                {
                    "dia": _DIAS_SEMANA[indice],
                    "hecho": inicio_semana + timedelta(days=indice) in reuniones_semana,
                    "hoy": inicio_semana + timedelta(days=indice) == hoy,
                    "futuro": inicio_semana + timedelta(days=indice) > hoy,
                }
                for indice in range(7)
            ]
            dias_desde_ultima = (hoy - ultima_reunion).days if ultima_reunion else None
            return {
                "activa": activa,
                "semanas": semanas,
                "ultima_reunion": ultima_reunion,
                "planes_hechos": planes_hechos,
                "dias_desde_ultima": dias_desde_ultima,
                "calendario": calendario,
                "fuego": _color_fuego(semanas),
                "marco": _MARCOS.get(marco_seleccionado),
                "marco_semanas": marco_seleccionado,
                "marcos_desbloqueados": marcos_desbloqueados,
                "titulo_color": _COLORES_TITULO.get(titulo_seleccionado),
                "titulo_semanas": titulo_seleccionado,
                "titulos_desbloqueados": titulos_desbloqueados,
                "hitos": [
                    {
                        "semanas": hito,
                        "logrado": hito in hitos_desbloqueados,
                        "proximo": hito == proximo_hito,
                        "marco": _MARCOS.get(hito),
                        "titulo_color": _COLORES_TITULO.get(hito),
                        "fuego": _color_fuego(hito),
                    }
                    for hito in _HITOS
                ],
                "proximo_hito": proximo_hito,
                "progreso_hito": min(100, round(semanas / proximo_hito * 100)) if proximo_hito else 100,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def guardar_apariencia(self, group_id, marco_semanas, titulo_semanas):
        """Guarda solo cosméticos que el grupo ya haya desbloqueado."""
        marco_semanas = int(marco_semanas) if marco_semanas else None
        titulo_semanas = int(titulo_semanas) if titulo_semanas else None
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT "Semanas" FROM public."Grupo_Insignia" WHERE "Id_Grupo" = %s',
                    (group_id,),
                )
                ganados = {fila[0] for fila in cursor.fetchall()}
                if marco_semanas is not None and marco_semanas not in ganados.intersection(_MARCOS):
                    raise ValueError("Ese marco todavía no está desbloqueado.")
                if titulo_semanas is not None and titulo_semanas not in ganados.intersection(_COLORES_TITULO):
                    raise ValueError("Ese título todavía no está desbloqueado.")
                cursor.execute(
                    '''INSERT INTO public."Grupo_Apariencia"
                       ("Id_Grupo", "Marco_Semanas", "Titulo_Semanas")
                       VALUES (%s, %s, %s)
                       ON CONFLICT ("Id_Grupo") DO UPDATE SET
                         "Marco_Semanas" = EXCLUDED."Marco_Semanas",
                         "Titulo_Semanas" = EXCLUDED."Titulo_Semanas"''',
                    (group_id, marco_semanas, titulo_semanas),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)
