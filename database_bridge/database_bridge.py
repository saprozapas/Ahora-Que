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
                    "Password_Hash",
                    "Descripcion"
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
                result[5],  # Password_Hash
                result[6]   # Descripcion
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

def getUsersInGroup(group_id):
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u."Id_Usuario", u."Nombre", u."Fecha_Nac", u."Username", u."Mail", u."Password_Hash"
                FROM public."Usuarios" u
                JOIN public."Usuario-Grupo" ug ON u."Id_Usuario" = ug."Id_Usuario"
                WHERE ug."Id_Grupo" = %s
                """,
                (group_id,)
            )

            results = cursor.fetchall()

            users = []
            for result in results:
                users.append(User(result[1], result[2], result[3], result[4], result[5]))
            return users

    except psycopg2.Error:
        raise

    finally:
        connection.close()

def getUsersInGroupWithIds(group_id):
    """Como getUsersInGroup, pero devuelve también el Id_Usuario de cada
    integrante (necesario para linkear a su perfil) y su Descripcion."""
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u."Id_Usuario", u."Nombre", u."Fecha_Nac", u."Username", u."Mail", u."Password_Hash", u."Descripcion"
                FROM public."Usuarios" u
                JOIN public."Usuario-Grupo" ug ON u."Id_Usuario" = ug."Id_Usuario"
                WHERE ug."Id_Grupo" = %s
                ORDER BY u."Nombre"
                """,
                (group_id,)
            )

            results = cursor.fetchall()

            users = []
            for result in results:
                users.append({
                    "id": result[0],
                    "user": User(result[1], result[2], result[3], result[4], result[5], result[6]),
                })
            return users

    except psycopg2.Error:
        raise

    finally:
        connection.close()

def getFriendsForUser(uid):
    """Amigos ya confirmados de un usuario, con su Id_Usuario incluido
    (necesario para linkear a su perfil, invitarlo a un grupo, etc)."""
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u."Id_Usuario", u."Nombre", u."Fecha_Nac", u."Username", u."Mail", u."Password_Hash", u."Descripcion"
                FROM public."Usuarios" u
                JOIN public."Amistades" a
                    ON u."Id_Usuario" = CASE
                        WHEN a."Id_Usuario1" = %s THEN a."Id_Usuario2"
                        ELSE a."Id_Usuario1"
                    END
                WHERE a."Id_Usuario1" = %s OR a."Id_Usuario2" = %s
                ORDER BY u."Nombre"
                """,
                (uid, uid, uid)
            )

            results = cursor.fetchall()

            amigos = []
            for result in results:
                amigos.append({
                    "id": result[0],
                    "user": User(result[1], result[2], result[3], result[4], result[5], result[6]),
                })
            return amigos

    except psycopg2.Error:
        raise

    finally:
        connection.close()


def buscarUsuarios(query, uid_actual, limite=8):
    """Busca usuarios por nombre o username para agregar como amigos,
    excluyendo al propio usuario. Para cada resultado indica si ya son
    amigos o si ya existe una solicitud pendiente en algún sentido, así
    el frontend puede mostrar el botón correcto (Agregar / Ya son amigos /
    Solicitud enviada / Te invitó)."""
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            patron = f"%{query}%"
            cursor.execute(
                """
                SELECT
                    u."Id_Usuario",
                    u."Nombre",
                    u."Username",
                    EXISTS (
                        SELECT 1 FROM public."Amistades" a
                        WHERE a."Id_Usuario1" = LEAST(u."Id_Usuario", %s)
                          AND a."Id_Usuario2" = GREATEST(u."Id_Usuario", %s)
                    ) AS ya_amigos,
                    EXISTS (
                        SELECT 1 FROM public."Solicitudes_Amistad" s
                        WHERE s."Id_Solicitante" = %s AND s."Id_Destinatario" = u."Id_Usuario"
                    ) AS solicitud_enviada,
                    EXISTS (
                        SELECT 1 FROM public."Solicitudes_Amistad" s
                        WHERE s."Id_Solicitante" = u."Id_Usuario" AND s."Id_Destinatario" = %s
                    ) AS solicitud_recibida
                FROM public."Usuarios" u
                WHERE u."Id_Usuario" != %s
                    AND (u."Nombre" ILIKE %s OR u."Username" ILIKE %s)
                ORDER BY u."Nombre"
                LIMIT %s
                """,
                (uid_actual, uid_actual, uid_actual, uid_actual, uid_actual, patron, patron, limite)
            )

            results = cursor.fetchall()

            usuarios = []
            for result in results:
                usuarios.append({
                    "id": result[0],
                    "nombre": result[1],
                    "username": result[2],
                    "ya_amigos": result[3],
                    "solicitud_enviada": result[4],
                    "solicitud_recibida": result[5],
                })
            return usuarios

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
        
