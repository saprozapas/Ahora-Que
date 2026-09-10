import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.user import User
from database import get_db_connection
import psycopg2
import psycopg2.extras


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


# 1. Buscar usuarios 
# def buscar_usuarios(mail=None, nombre=None, username=None, id_usuario=None): 
#     connection = get_db_connection() 
#     try: 
#         with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor: 
#             cursor.execute( 
#                 """ 
#                 SELECT * FROM buscar_usuarios(%s, %s, %s, %s) 
#                 """, 
#                 (id_usuario, nombre, mail, username), 
#             ) 
#             return cursor.fetchall() 
#     except psycopg2.Error: 
#         raise 
#     finally: 
#         connection.close() 
# 
# 
# 
# # 2. Buscar lugares 
# def buscar_lugares( 
#     texto=None, 
#     tipo_id=None, 
#     nivel_precio_max=None, 
#     solo_vegano=False, 
#     solo_celiaco=False, 
#     apto_menores=False, 
#     dia_semana=None, 
#     hora=None,          # formato "HH:MM:SS" 
#     limite=10, 
#     offset=0 
# ): 
#     connection = get_db_connection() 
#     try: 
#         with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor: 
#             cursor.execute( 
#                 """ 
#                 SELECT * FROM buscar_lugares(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
#                 """, 
#                 ( 
#                     texto, tipo_id, nivel_precio_max, solo_vegano, 
#                     solo_celiaco, apto_menores, dia_semana, hora, 
#                     limite, offset, 
#                 ), 
#             ) 
#             return cursor.fetchall() 
#     except psycopg2.Error: 
#         raise 
#     finally: 
#         connection.close() 
# 
# 
# # 3. Buscar planes 
# def buscar_planes(usuario_id=None, grupo_id=None, confirmado=None): 
#     connection = get_db_connection() 
#     try: 
#         with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor: 
#             cursor.execute( 
#                 """ 
#                 SELECT * FROM buscar_planes(%s, %s, %s) 
#                 """, 
#                 (usuario_id, grupo_id, confirmado), 
#             ) 
#             return cursor.fetchall() 
#     except psycopg2.Error: 
#         raise 
#     finally: 
#         connection.close() 
# 
# resultado = buscar_usuarios(username = "maximodipalma") 
# print(resultado) 