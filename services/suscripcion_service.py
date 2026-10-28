"""Plan gratis y plan premium.

Gratis: 1 plan por semana armado con la IA (la semana arranca el lunes a las 00:00,
hora de Montevideo). Premium: sin límite y con una estrella en el nombre.
Un plan "con IA" cuenta cuando se guarda o se postula (/chatbot/confirmar_plan).
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database import get_db_connection, release_db_connection

PLANES_IA_GRATIS_POR_SEMANA = 1
MENSAJE_LIMITE_IA = (
    "Llegaste a tu límite semanal de planes con la IA. Se recarga los lunes. "
    "Si querés seguir armando planes con la IA, pasate al plan Premium."
)
_MONTEVIDEO = ZoneInfo("America/Montevideo")


def inicio_de_semana(ahora=None):
    """El lunes a las 00:00 (Montevideo) de la semana de `ahora`."""
    ahora = ahora or datetime.now(_MONTEVIDEO)
    return (ahora - timedelta(days=ahora.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


class SuscripcionService:

    def es_premium(self, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT "Premium" FROM public."Usuarios" WHERE "Id_Usuario" = %s', (str(user_id),))
                fila = cursor.fetchone()
            return bool(fila and fila[0])
        finally:
            release_db_connection(connection)

    def limite_ia_alcanzado(self, user_id):
        """True si es del plan gratis y ya usó su plan con IA de esta semana."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    '''SELECT u."Premium",
                              (SELECT COUNT(*) FROM public."Uso_IA_Plan" x
                                WHERE x."Id_Usuario" = u."Id_Usuario" AND x."Creado_En" >= %s)
                       FROM public."Usuarios" u
                       WHERE u."Id_Usuario" = %s''',
                    (inicio_de_semana(), str(user_id)),
                )
                fila = cursor.fetchone()
            # ponytail: dos confirmaciones a la vez podrían colar un segundo plan; no vale un lock.
            return bool(fila) and not fila[0] and fila[1] >= PLANES_IA_GRATIS_POR_SEMANA
        finally:
            release_db_connection(connection)

    def registrar_plan_ia(self, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO public."Uso_IA_Plan" ("Id_Usuario") VALUES (%s)', (str(user_id),))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def cambiar_plan(self, user_id, premium):
        """Activa (True) o cancela (False) el Premium. Todavía no hay cobro real: lo llama la maqueta de pago."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE public."Usuarios" SET "Premium" = %s WHERE "Id_Usuario" = %s',
                    (bool(premium), str(user_id)),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)
