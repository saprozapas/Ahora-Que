from models.user import User
from database import get_db_connection
import psycopg2

####################################################
##   IMPLEMENTAR LALO, TODO POSIBLE GET DE LA BASE DE DATOS QUE SE PUEDA QUERER HACER.
##   TENES EJEMPLO DE COMO SE USA LA CONEXION EN EL ARCHIVO DE AUTH_SERVICES.PY
##################################################

def getUser(uid):
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    "Id_Usuario",
                    "Nombre",
                    "Fecha_Nac",
                    "Username",
                    "Mail",
                    "Password_Hash"
                FROM public."Usuarios"
                WHERE "Id_Usuario" = %s
                """,
                (uid,)
            )

            result = cursor.fetchone()

            if result is None:
                return None

            return User(
                result[0],  # Id_Usuario
                result[1],  # Nombre
                result[2],  # Fecha_Nac
                result[3],  # Username
                result[4],  # Mail
                result[5]   # Password_Hash
            )

    except psycopg2.Error:
        raise

    finally:
        connection.close()