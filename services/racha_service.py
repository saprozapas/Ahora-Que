from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database import get_db_connection, release_db_connection


_MONTEVIDEO = ZoneInfo("America/Montevideo")
_DIAS_SEMANA = ("L", "M", "M", "J", "V", "S", "D")
_HITOS = (3, 5, 10, 20)


class RachaService:
    """Calcula y persiste la racha de reuniones de un grupo."""

    def actualizar_racha(self, group_id):
        """Actualiza la racha usando planes grupales que ya ocurrieron.

        Una racha queda pausada luego de 7 días sin reunión y se reinicia
        después de 14 días. Los planes separados por menos de 14 días
        pertenecen a la misma racha; solo suma una vez por semana ISO.
        """
        hoy = datetime.now(_MONTEVIDEO).date()
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''
                    SELECT "Fecha", "Hora", "Nombre"
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
                    ORDER BY "Fecha", "Hora"
                    ''',
                    (group_id,),
                )
                planes = cursor.fetchall()

                semanas = 0
                semanas_contadas = set()
                reunion_anterior = None
                for fecha, _hora, _nombre in planes:
                    if reunion_anterior and (fecha - reunion_anterior).days >= 14:
                        semanas = 0
                        semanas_contadas.clear()
                    semana_iso = fecha.isocalendar()[:2]
                    # Cada semana ISO suma como máximo una vez, aunque haya
                    # varias juntadas o planes realizados en esa semana.
                    if semana_iso not in semanas_contadas:
                        semanas += 1
                        semanas_contadas.add(semana_iso)
                    reunion_anterior = fecha

                ultima_reunion = reunion_anterior
                if ultima_reunion is None or (hoy - ultima_reunion).days >= 14:
                    semanas = 0
                    activa = False
                else:
                    activa = semanas > 0 and (hoy - ultima_reunion).days < 7

                cursor.execute(
                    '''
                    INSERT INTO public."Rachas"
                        ("Id_Grupo", "Activa", "Semanas", "Ultima_Reunion")
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT ("Id_Grupo") DO UPDATE SET
                        "Activa" = EXCLUDED."Activa",
                        "Semanas" = EXCLUDED."Semanas",
                        "Ultima_Reunion" = EXCLUDED."Ultima_Reunion"
                    ''',
                    (group_id, activa, semanas, ultima_reunion),
                )

            conn.commit()
            proximo_hito = next((hito for hito in _HITOS if hito > semanas), ((semanas // 5) + 1) * 5)
            inicio_semana = hoy - timedelta(days=hoy.weekday())
            reuniones_semana = {
                plan[0] for plan in planes
                if inicio_semana <= plan[0] <= hoy
            }
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
                "ultimo_plan": planes[-1][2] if planes and ultima_reunion else None,
                "planes_hechos": len(planes),
                "dias_desde_ultima": dias_desde_ultima,
                "calendario": calendario,
                "hitos": [
                    {"semanas": hito, "logrado": semanas >= hito, "proximo": hito == proximo_hito}
                    for hito in sorted(set((*_HITOS, proximo_hito)))
                ],
                "proximo_hito": proximo_hito,
                "progreso_hito": min(100, round(semanas / proximo_hito * 100)) if proximo_hito else 0,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)
