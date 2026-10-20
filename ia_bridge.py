"""Puente entre Flask, la base de datos y el cifrado del chatbot.

Todo lo que el chatbot persiste pasa por acá: conversaciones, mensajes
cifrados y la verificación de lugares. No toca database_bridge ni los
services existentes.

Cifrado (ver services/crypto_service.py):
  - Cada conversación tiene su DEK, guardada envuelta con la KEK en
    "Conversacion"."Dek_Cifrada". AAD de la DEK: "dek|<Id_Conversacion>",
    así una DEK no se puede copiar a otra conversación.
  - Cada mensaje se cifra con la DEK. AAD del mensaje:
    "<Id_Conversacion>|<Id_Mensaje>|<Rol>|<Tipo_Mensaje>", así no se
    puede mover un mensaje de conversación ni cambiarle el rol o el tipo
    en la base sin que falle el descifrado.
"""
import json
import uuid

import psycopg2

from database import get_db_connection, release_db_connection
from services.crypto_service import cifrar, descifrar, desenvolver_dek, envolver_dek, nueva_dek


def _aad_dek(conv_id):
    return f"dek|{conv_id}".encode("utf-8")


def _aad_mensaje(conv_id, mensaje_id, rol, tipo):
    return f"{conv_id}|{mensaje_id}|{rol}|{tipo}".encode("utf-8")


def _es_uuid(valor):
    try:
        uuid.UUID(str(valor))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


# --- Conversaciones ----------------------------------------------------------

def _buscar_conversacion_bot(cursor, user_id):
    cursor.execute(
        """
        SELECT c."Id_Conversacion", c."Dek_Cifrada"
        FROM public."Conversacion" c
        JOIN public."Conversacion_Miembro" cm ON c."Id_Conversacion" = cm."Id_Conversacion"
        WHERE cm."Id_Usuario" = %s AND c."Tipo" = 'bot'
        ORDER BY c."Created_At"
        LIMIT 1
        """,
        (user_id,),
    )
    fila = cursor.fetchone()
    if fila is None:
        return None
    conv_id = str(fila[0])
    return conv_id, desenvolver_dek(bytes(fila[1]), _aad_dek(conv_id))


def obtener_conversacion_bot(user_id):
    """(conv_id, dek) de la conversación con el bot, o None si no hay."""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            return _buscar_conversacion_bot(cursor, user_id)
    except psycopg2.Error:
        raise
    finally:
        release_db_connection(connection)


def obtener_o_crear_conversacion_bot(user_id):
    """(conv_id, dek) de la conversación con el bot; la crea si no existe."""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Lock por usuario hasta el fin de la transacción: evita que dos
            # requests simultáneos creen dos conversaciones para el mismo usuario.
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"chatbot:{user_id}",),
            )
            existente = _buscar_conversacion_bot(cursor, user_id)
            if existente:
                connection.commit()
                return existente

            conv_id = str(uuid.uuid4())
            dek = nueva_dek()
            cursor.execute(
                """
                INSERT INTO public."Conversacion" ("Id_Conversacion", "Tipo", "Dek_Cifrada")
                VALUES (%s, 'bot', %s)
                """,
                (conv_id, psycopg2.Binary(envolver_dek(dek, _aad_dek(conv_id)))),
            )
            cursor.execute(
                """
                INSERT INTO public."Conversacion_Miembro" ("Id_Conversacion", "Id_Usuario")
                VALUES (%s, %s)
                """,
                (conv_id, user_id),
            )
        connection.commit()
        return conv_id, dek
    except psycopg2.Error:
        connection.rollback()
        raise
    finally:
        release_db_connection(connection)


def borrar_conversacion_bot(user_id):
    """Borra la conversación del usuario con el bot (y por CASCADE sus
    mensajes). Al perderse la DEK, lo que quedara en backups tampoco se
    puede descifrar."""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM public."Conversacion" c
                USING public."Conversacion_Miembro" cm
                WHERE cm."Id_Conversacion" = c."Id_Conversacion"
                  AND cm."Id_Usuario" = %s
                  AND c."Tipo" = 'bot'
                """,
                (user_id,),
            )
        connection.commit()
    except psycopg2.Error:
        connection.rollback()
        raise
    finally:
        release_db_connection(connection)


# --- Mensajes ----------------------------------------------------------------

def guardar_mensajes(conv_id, dek, mensajes):
    """Guarda varios mensajes cifrados en una sola transacción, en orden.

    mensajes: lista de dicts {"remitente": uuid o None (bot),
                              "rol": "user" | "assistant",
                              "texto": str,
                              "tipo": "texto" | "borrador"}
    Devuelve la lista de Id_Mensaje en el mismo orden.
    """
    ids = []
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            for mensaje in mensajes:
                mensaje_id = str(uuid.uuid4())
                rol = mensaje["rol"]
                tipo = mensaje.get("tipo", "texto")
                blob = cifrar(dek, mensaje["texto"], _aad_mensaje(conv_id, mensaje_id, rol, tipo))
                # clock_timestamp() (y no NOW(), que es fijo en toda la
                # transacción) para que los mensajes queden ordenados.
                cursor.execute(
                    """
                    INSERT INTO public."Mensaje"
                        ("Id_Mensaje", "Id_Conversacion", "Id_Remitente", "Rol",
                         "Tipo_Mensaje", "Contenido_Cifrado", "Created_At")
                    VALUES (%s, %s, %s, %s, %s, %s, clock_timestamp())
                    """,
                    (mensaje_id, conv_id, mensaje.get("remitente"), rol, tipo, psycopg2.Binary(blob)),
                )
                ids.append(mensaje_id)
        connection.commit()
        return ids
    except psycopg2.Error:
        connection.rollback()
        raise
    finally:
        release_db_connection(connection)


def obtener_historial_desencriptado(conv_id, dek, limite=20):
    """Los últimos `limite` mensajes, del más viejo al más nuevo:
    [{"id", "role", "content", "tipo"}]."""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT "Id_Mensaje", "Rol", "Tipo_Mensaje", "Contenido_Cifrado"
                FROM public."Mensaje"
                WHERE "Id_Conversacion" = %s
                ORDER BY "Created_At" DESC
                LIMIT %s
                """,
                (conv_id, limite),
            )
            filas = cursor.fetchall()
    except psycopg2.Error:
        raise
    finally:
        release_db_connection(connection)

    historial = []
    for mensaje_id, rol, tipo, blob in reversed(filas):
        mensaje_id = str(mensaje_id)
        texto = descifrar(dek, bytes(blob), _aad_mensaje(conv_id, mensaje_id, rol, tipo))
        historial.append({"id": mensaje_id, "role": rol, "content": texto, "tipo": tipo})
    return historial


def obtener_borrador(conv_id, dek, mensaje_id):
    """El borrador (dict) guardado en ese mensaje, solo si es de esta
    conversación y es de tipo 'borrador'. Si no, None."""
    if not _es_uuid(mensaje_id):
        return None
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT "Contenido_Cifrado"
                FROM public."Mensaje"
                WHERE "Id_Mensaje" = %s
                  AND "Id_Conversacion" = %s
                  AND "Rol" = 'assistant'
                  AND "Tipo_Mensaje" = 'borrador'
                """,
                (str(mensaje_id), conv_id),
            )
            fila = cursor.fetchone()
    except psycopg2.Error:
        raise
    finally:
        release_db_connection(connection)

    if fila is None:
        return None
    texto = descifrar(dek, bytes(fila[0]), _aad_mensaje(conv_id, str(mensaje_id), "assistant", "borrador"))
    return json.loads(texto)


# --- Lugares -----------------------------------------------------------------

def lugares_por_ids(ids):
    """Verifica contra la tabla "Lugar" que los ids existan.
    Devuelve {id: {"id", "nombre", "nivel_precio", "direccion"}} solo con
    los que existen (los ids inventados o mal formados quedan afuera)."""
    ids = [str(i) for i in ids if _es_uuid(i)]
    if not ids:
        return {}
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT "Id_Lugar", "Nombre", "Nivel_Precio", "Direccion"
                FROM public."Lugar"
                WHERE "Id_Lugar"::text = ANY(%s)
                """,
                (ids,),
            )
            return {
                str(fila[0]): {
                    "id": str(fila[0]),
                    "nombre": fila[1],
                    "nivel_precio": fila[2],
                    "direccion": fila[3],
                }
                for fila in cursor.fetchall()
            }
    except psycopg2.Error:
        raise
    finally:
        release_db_connection(connection)


def tipos_por_lugar(ids):
    """{id_lugar: [nombres de sus Tipos]} para los ids que existan."""
    ids = [str(i) for i in ids if _es_uuid(i)]
    if not ids:
        return {}
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT lt."Lugar_id", t."Nombre"
                FROM public."Lugar_Tipo" lt
                JOIN public."Tipo" t ON t."Id_Tipo" = lt."Tipo_id"
                WHERE lt."Lugar_id"::text = ANY(%s)
                """,
                (ids,),
            )
            tipos = {}
            for lugar_id, nombre in cursor.fetchall():
                tipos.setdefault(str(lugar_id), []).append(nombre)
            return tipos
    except psycopg2.Error:
        raise
    finally:
        release_db_connection(connection)


# --- Grupos ------------------------------------------------------------------

def contexto_grupo(user_id, group_id):
    """{"nombre", "integrantes"} del grupo, solo si el usuario es parte de
    él. Si el grupo no existe o no es miembro, devuelve None."""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT g."Nombre",
                       (SELECT COUNT(*) FROM public."Usuario-Grupo" u2
                        WHERE u2."Id_Grupo" = g."Id_Grupo")
                FROM public."Grupos" g
                WHERE g."Id_Grupo"::text = %s
                  AND EXISTS (
                      SELECT 1 FROM public."Usuario-Grupo" ug
                      WHERE ug."Id_Grupo" = g."Id_Grupo" AND ug."Id_Usuario"::text = %s
                  )
                """,
                (str(group_id), str(user_id)),
            )
            fila = cursor.fetchone()
    except psycopg2.Error:
        raise
    finally:
        release_db_connection(connection)
    if fila is None:
        return None
    return {"nombre": fila[0], "integrantes": int(fila[1])}
