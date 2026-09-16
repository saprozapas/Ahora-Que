import psycopg2

from database import get_db_connection


class PlanService:
    def get_planes_confirmados(self, user_id):
        connection = get_db_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        p."id_Plan",
                        p."Nombre",
                        p."Fecha",
                        p."Hora",
                        p."Precio",
                        p."Estado"
                    FROM public."Usuario-Plan" up
                    JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                    WHERE up."Usuario_id" = %s
                      AND up."Confirmado" = true
                    ORDER BY p."Fecha", p."Hora"
                    """,
                    (user_id,),
                )
                filas = cursor.fetchall()

            planes = []
            for fila in filas:
                planes.append({
                    "id": fila[0],
                    "nombre": fila[1],
                    "fecha": fila[2],
                    "hora": fila[3],
                    "precio": fila[4],
                    "estado": fila[5],
                })
            return planes

        except psycopg2.Error:
            raise

        finally:
            connection.close()