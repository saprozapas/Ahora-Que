"""Plan gratis y plan premium.

Gratis: 1 plan por semana armado con la IA (la semana arranca el lunes a las 00:00,
hora de Montevideo). Premium: sin límite y con una estrella en el nombre.
Un plan "con IA" cuenta cuando se guarda o se postula (/chatbot/confirmar_plan).
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from database import get_db_connection, release_db_connection
from services.legal_info import EDAD_MINIMA_PREMIUM

PLANES_IA_GRATIS_POR_SEMANA = 1
MENSAJE_LIMITE_IA = (
    "Llegaste a tu límite semanal de planes con la IA. Se recarga los lunes. "
    "Si querés seguir armando planes con la IA, pasate al plan Premium."
)
_MONTEVIDEO = ZoneInfo("America/Montevideo")

# Precios de EJEMPLO (todavía no hay cobros): se cambian acá y se ven en las pantallas de Premium.
# "por_mes" es lo que se muestra grande; "total" es lo que se cobraría de una vez.
# Moneda: pesos uruguayos, IVA incluido (así se aclara en _premium_legal.html).
# Las notas aclaran que la suscripción se renueva sola: es información obligatoria antes de pagar.
PRECIOS = {
    "mensual": {"por_mes": 199, "total": 199, "nota": "Se renueva cada mes hasta que canceles · IVA incluido", "descuento": 0},
    "anual": {"por_mes": 159, "total": 1908, "nota": "$ 1.908 por año (ahorrás $ 480) · se renueva cada año hasta que canceles · IVA incluido", "descuento": 20},
}


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

    def planes_ia_usados(self, user_id):
        """Cuántos planes con la IA armó esta semana (para el medidor de Tu suscripción)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT COUNT(*) FROM public."Uso_IA_Plan" WHERE "Id_Usuario" = %s AND "Creado_En" >= %s',
                    (str(user_id), inicio_de_semana()),
                )
                return int(cursor.fetchone()[0])
        except Exception as e:  # si todavía no se corrió migraciones/planes_suscripcion.sql
            print(f"No se pudo contar los planes con IA: {e}")
            return 0
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

    def es_mayor_de_edad(self, user_id):
        """True si la persona tiene EDAD_MINIMA_PREMIUM años o más (un menor no puede contratar por su cuenta)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT "Fecha_Nac" FROM public."Usuarios" WHERE "Id_Usuario" = %s', (str(user_id),))
                fila = cursor.fetchone()
        finally:
            release_db_connection(connection)
        if not fila or not fila[0]:
            return False  # sin fecha de nacimiento no podemos asegurar que sea mayor: no se deja contratar
        nacimiento = fila[0]
        if isinstance(nacimiento, str):
            nacimiento = date.fromisoformat(nacimiento[:10])
        hoy = datetime.now(_MONTEVIDEO).date()
        edad = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
        return edad >= EDAD_MINIMA_PREMIUM

    def _cambiar_plan(self, user_id, premium, accion, ciclo, version):
        """Cambia el plan y anota el evento en Premium_Historial, las dos cosas en una sola transacción:
        o quedan las dos o no queda ninguna (nunca un Premium sin su constancia de aceptación)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE public."Usuarios" SET "Premium" = %s WHERE "Id_Usuario" = %s',
                    (bool(premium), str(user_id)),
                )
                cursor.execute(
                    'INSERT INTO public."Premium_Historial" ("Id_Usuario", "Accion", "Ciclo", "Version_Condiciones") '
                    'VALUES (%s, %s, %s, %s)',
                    (str(user_id), accion, ciclo, version),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def activar_premium(self, user_id, ciclo, version_condiciones):
        """Alta de Premium (hoy, de demostración). Guarda la frecuencia y la versión de las condiciones aceptadas."""
        self._cambiar_plan(user_id, True, "alta", ciclo, version_condiciones)

    def cancelar_premium(self, user_id):
        """Baja de Premium: vuelve al plan gratis."""
        self._cambiar_plan(user_id, False, "baja", None, None)
