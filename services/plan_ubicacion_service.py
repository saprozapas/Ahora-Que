"""Mapa de un plan confirmado: el lugar y, si cada uno quiere, dónde está cada asistente.

Reglas (las que se pidieron y que acá se hacen cumplir, no solo en la pantalla):
  - Solo ven el mapa y las ubicaciones quienes VAN al plan (lo confirmaron).
  - Está disponible desde que el plan se confirma y hasta que termina (deja de estar "confirmado": ver
    PlanService.archivar_vencidos, 12 h después de que arrancó). Ahí las ubicaciones se borran.
  - Compartir es opcional y por plan: sin compartir, la persona aparece en la lista pero no en el mapa.
  - Se guarda solo la ÚLTIMA ubicación de cada persona, nunca un historial.
  - Al dejar de compartir, o al bajarse del plan, se borra.
"""

import math
from datetime import datetime, timezone

import psycopg2

from database import get_db_connection, release_db_connection
from services.chat_service import ChatService
from services.plan_service import PlanService

# Una ubicación más vieja que esto se marca como "desactualizada" en el mapa.
_VIEJA_SEGUNDOS = 10 * 60


def _km(lat1, lon1, lat2, lon2):
    radio = math.pi / 180
    a = math.sin((lat2 - lat1) * radio / 2) ** 2 + math.cos(lat1 * radio) * math.cos(lat2 * radio) * math.sin((lon2 - lon1) * radio / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


class UbicacionNoPermitida(Exception):
    """El plan no está confirmado (o ya terminó) o la persona no va."""


class PlanUbicacionService:

    def __init__(self):
        self._planes = PlanService()

    def _asistente(self, cursor, plan_id, user_id):
        """Nombre del plan si está confirmado y el usuario va; si no, None."""
        cursor.execute(
            """
            SELECT p."Nombre"
            FROM public."Plan" p
            JOIN public."Usuario-Plan" up ON up."Plan_id" = p."id_Plan" AND up."Usuario_id" = %s AND up."Confirmado"
            WHERE p."id_Plan"::text = %s AND p."Estado" = 'confirmado'
            """,
            (user_id, str(plan_id)),
        )
        fila = cursor.fetchone()
        return fila[0] if fila else None

    def datos(self, plan_id, user_id):
        """Todo lo que dibuja el mapa. Levanta UbicacionNoPermitida si esta persona no puede verlo."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                nombre_plan = self._asistente(cursor, plan_id, user_id)
                if nombre_plan is None:
                    raise UbicacionNoPermitida()
                lugares = [
                    {"nombre": l["nombre"], "direccion": l["direccion"], "barrio": l["barrio"], "lat": l["lat"], "lon": l["lon"]}
                    for l in self._planes._lugares_de_plan(cursor, plan_id)
                    if l.get("lat") is not None and l.get("lon") is not None
                ]
                cursor.execute(
                    """
                    SELECT u."Id_Usuario"::text, u."Nombre", u."Username", pu."Lat", pu."Lon", pu."Actualizada_En"
                    FROM public."Usuario-Plan" up
                    JOIN public."Usuarios" u ON u."Id_Usuario" = up."Usuario_id"
                    LEFT JOIN public."Plan_Ubicacion" pu ON pu."Id_Plan" = up."Plan_id" AND pu."Id_Usuario" = up."Usuario_id"
                    WHERE up."Plan_id"::text = %s AND up."Confirmado"
                    ORDER BY (u."Id_Usuario"::text = %s) DESC, u."Nombre"
                    """,
                    (str(plan_id), str(user_id)),
                )
                filas = cursor.fetchall()
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

        destino = lugares[0] if lugares else None
        ahora = datetime.now(timezone.utc)
        personas = []
        for f in filas:
            comparte = f[3] is not None and f[4] is not None
            persona = {
                "id": f[0],
                "nombre": f[1],
                "handle": ChatService.handle(f[2], f[1]),
                "yo": f[0] == str(user_id),
                "comparte": comparte,
                "lat": f[3] if comparte else None,
                "lon": f[4] if comparte else None,
                "km": None,
                "hace_segundos": None,
                "vieja": False,
            }
            if comparte:
                persona["hace_segundos"] = max(0, int((ahora - f[5]).total_seconds()))
                persona["vieja"] = persona["hace_segundos"] > _VIEJA_SEGUNDOS
                if destino:
                    persona["km"] = round(_km(f[3], f[4], destino["lat"], destino["lon"]), 2)
            personas.append(persona)

        return {
            "plan": nombre_plan,
            "lugares": lugares,
            "personas": personas,
            "yo_comparto": any(p["yo"] and p["comparte"] for p in personas),
        }

    def compartir(self, plan_id, user_id, lat, lon):
        """Guarda (o actualiza) la última ubicación de esta persona en el plan."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                if self._asistente(cursor, plan_id, user_id) is None:
                    raise UbicacionNoPermitida()
                cursor.execute(
                    """
                    INSERT INTO public."Plan_Ubicacion" ("Id_Plan", "Id_Usuario", "Lat", "Lon", "Actualizada_En")
                    VALUES (%s, %s, %s, %s, now())
                    ON CONFLICT ("Id_Plan", "Id_Usuario")
                    DO UPDATE SET "Lat" = EXCLUDED."Lat", "Lon" = EXCLUDED."Lon", "Actualizada_En" = now()
                    """,
                    (plan_id, user_id, lat, lon),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def dejar_de_compartir(self, plan_id, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM public."Plan_Ubicacion" WHERE "Id_Plan"::text = %s AND "Id_Usuario" = %s',
                    (str(plan_id), user_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)
