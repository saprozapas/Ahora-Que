import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.group import Group
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

def getGroupsForUser(uid):
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    g."Id_Grupo",
                    g."Nombre",
                    g."Descripcion"
                FROM public."Grupos" g
                JOIN public."Usuario-Grupo" ug ON g."Id_Grupo" = ug."Id_Grupo"
                WHERE ug."Id_Usuario" = %s
                """,
                (uid,)
            )

            results = cursor.fetchall()

            groups = []
            for result in results:
                groups.append(Group(None, result[1], result[2], result[0]))
            return groups

    except psycopg2.Error:
        raise

    finally:
        connection.close()

def getGroupById(group_id):
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    "Id_Grupo",
                    "Nombre",
                    "Descripcion"
                FROM public."Grupos"
                WHERE "Id_Grupo" = %s
                """,
                (group_id,)
            )

            result = cursor.fetchone()

            if result is None:
                return None

            return Group(
                None,      # lo que corresponda al primer atributo
                result[1], # Nombre
                result[2], # Descripcion
                result[0]  # Id_Grupo
            )

    except psycopg2.Error:
        raise

    finally:
        connection.close()

def isUserInGroup(uid, group_id):
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM public."Usuario-Grupo"
                    WHERE "Id_Usuario" = %s
                    AND "Id_Grupo" = %s
                )
                """,
                (uid, group_id)
            )

            result = cursor.fetchone()

            return result[0]

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