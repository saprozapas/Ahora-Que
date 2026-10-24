"""Lo que muestra el Inicio de cada usuario: avisos pendientes, cuenta regresiva y menciones.

Junta en un solo lugar lo que viene de las votaciones de los grupos (GrupoPlanService), de las menciones del
chat (ChatService) y del próximo plan confirmado, para que la página y el refresco automático armen lo mismo.
"""

from datetime import datetime, timedelta, timezone

import psycopg2

from database import get_db_connection, release_db_connection
from services.chat_service import ChatService
from services.grupo_plan_service import GrupoPlanService
from services.plan_service import PlanService

# Uruguay no tiene horario de verano: siempre UTC-3.
_HUSO = timezone(timedelta(hours=-3))
# Un plan sigue siendo "el próximo" hasta 3 horas después de que arrancó (ahí la cuenta dice que está pasando ahora).
_GRACIA_HORAS = 3


class InicioService:

    def __init__(self):
        self._grupo_planes = GrupoPlanService()
        self._planes = PlanService()
        self._chat = ChatService()

    def pendientes(self, user_id):
        """Las votaciones que esperan respuesta más las menciones sin leer. Mismo formato que
        GrupoPlanService.get_pendientes, con "menciones" y el "total" actualizado."""
        datos = self._grupo_planes.get_pendientes(user_id)
        menciones = self._chat.get_menciones(user_id)
        datos["menciones"] = menciones
        datos["total"] += len(menciones)
        return datos

    def proximo_plan(self, user_id):
        """El plan confirmado más cercano al que el usuario va, o None.

        Trae el momento exacto con huso (para la cuenta regresiva en el navegador), el primer lugar con
        ubicación (para la distancia) y cuántos van."""
        desde = datetime.now(_HUSO).replace(tzinfo=None) - timedelta(hours=_GRACIA_HORAS)
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", COALESCE(p."Hora", '00:00'::time), p."Grupo_id", g."Nombre",
                           (SELECT COUNT(*) FROM public."Usuario-Plan" x WHERE x."Plan_id" = p."id_Plan" AND x."Confirmado"),
                           p."Precio_Min", p."Precio_Max"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    LEFT JOIN public."Grupos" g ON g."Id_Grupo" = p."Grupo_id"
                    WHERE up."Usuario_id" = %s AND up."Confirmado" AND p."Estado" = 'confirmado'
                      AND p."Fecha" IS NOT NULL
                      AND p."Fecha" + COALESCE(p."Hora", '00:00'::time) >= %s
                    ORDER BY p."Fecha", p."Hora"
                    LIMIT 1
                    """,
                    (user_id, desde),
                )
                fila = cursor.fetchone()
                if fila is None:
                    return None
                lugares = self._planes._lugares_de_plan(cursor, fila[0])
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

        momento = datetime.combine(fila[2], fila[3]).replace(tzinfo=_HUSO)
        return {
            "id": fila[0],
            "nombre": fila[1],
            "fecha": fila[2],
            "hora": fila[3],
            "momento_iso": momento.isoformat(),
            "grupo_id": str(fila[4]) if fila[4] else None,
            "grupo": fila[5],
            "van": fila[6],
            "lugares": lugares,
            "resumen_lugares": self._planes._resumen_lugares(lugares),
        }
