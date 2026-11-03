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
    contexto = {"nombre": fila[0], "integrantes": int(fila[1])}
    contexto.update(_detalles_grupo(group_id))
    return contexto


# Cuánto se le cuenta al modelo de cada cosa (el prompt viaja en cada pedido: se cuida el tamaño).
_MAX_FECHAS_OCUPADAS = 6
_MAX_VOTACIONES = 5
_MAX_PUNTUADOS = 3
_MAX_RECHAZADOS = 5
_DIAS_VISTA_CALENDARIO = 14


def _detalles_grupo(group_id):
    """Lo que el grupo ya dijo sin que nadie se lo repita al bot, todo agregado (cantidades, nunca
    quién): presupuesto, días en que hay integrantes ocupados, los \"no puedo\" de las votaciones
    abiertas, ideas que el grupo rechazó y los planes mejor y peor puntuados.

    Es contexto de ayuda: si alguna consulta falla se devuelve lo que se pudo armar (o nada),
    y el chat sigue funcionando como antes."""
    detalles = {}
    gid = str(group_id)
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            consultas = (
                ("presupuesto_nivel", _consulta_presupuesto),
                ("ocupados", _consulta_ocupados),
                ("votaciones", _consulta_votaciones),
                ("horarios", _consulta_horarios),
                ("rechazados", _consulta_rechazados),
                ("puntajes", _consulta_puntajes),
            )
            for clave, consulta in consultas:
                try:
                    valor = consulta(cursor, gid)
                except psycopg2.Error as e:
                    # Una consulta rota deja la transacción abortada: se limpia para seguir con las demás.
                    connection.rollback()
                    print(f"[ia_bridge] contexto del grupo: falló {clave}: {e}", flush=True)
                    continue
                if valor:
                    detalles[clave] = valor
    finally:
        release_db_connection(connection)
    return detalles


def _consulta_presupuesto(cursor, gid):
    """Nivel de precio máximo de la última encuesta del grupo que lo pidió (el más restrictivo si
    respondieron varios). None si el grupo nunca marcó uno."""
    cursor.execute(
        """
        WITH ultima AS (
            SELECT e."Id_Encuesta" FROM public."Grupo_Encuesta" e
            WHERE e."Id_Grupo" = %s
              AND EXISTS (SELECT 1 FROM public."Grupo_Encuesta_Respuesta" r
                          WHERE r."Id_Encuesta" = e."Id_Encuesta" AND r."Nivel_Precio_Max" IS NOT NULL)
            ORDER BY e."Creada_En" DESC LIMIT 1
        )
        SELECT MIN(r."Nivel_Precio_Max")
        FROM public."Grupo_Encuesta_Respuesta" r JOIN ultima u ON u."Id_Encuesta" = r."Id_Encuesta"
        """,
        (gid,),
    )
    fila = cursor.fetchone()
    return int(fila[0]) if fila and fila[0] is not None else None


def _consulta_ocupados(cursor, gid):
    """[(fecha, hora, cuántos integrantes ya tienen un plan confirmado a esa hora)] en los próximos días."""
    cursor.execute(
        """
        SELECT p."Fecha", p."Hora", COUNT(DISTINCT up."Usuario_id")
        FROM public."Usuario-Grupo" ug
        JOIN public."Usuario-Plan" up ON up."Usuario_id" = ug."Id_Usuario" AND up."Confirmado"
        JOIN public."Plan" p ON p."id_Plan" = up."Plan_id" AND p."Estado" = 'confirmado'
        WHERE ug."Id_Grupo" = %s
          AND p."Fecha" BETWEEN CURRENT_DATE AND CURRENT_DATE + %s
        GROUP BY p."Fecha", p."Hora"
        ORDER BY p."Fecha", p."Hora"
        LIMIT %s
        """,
        (gid, _DIAS_VISTA_CALENDARIO, _MAX_FECHAS_OCUPADAS),
    )
    return [(f[0], f[1], int(f[2])) for f in cursor.fetchall()]


def _consulta_votaciones(cursor, gid):
    """Planes en votación con fecha: [(nombre, fecha, hora, pueden, no_pueden, no_les_gusta)]."""
    cursor.execute(
        """
        SELECT p."Nombre", p."Fecha", p."Hora",
               COUNT(*) FILTER (WHERE v."Puedo"),
               COUNT(*) FILTER (WHERE NOT v."Puedo"),
               COUNT(*) FILTER (WHERE NOT v."Me_Gusta")
        FROM public."Plan" p JOIN public."Plan_Voto" v ON v."Id_Plan" = p."id_Plan"
        WHERE p."Grupo_id" = %s AND p."Estado" = 'votacion' AND p."Fecha" IS NOT NULL
        GROUP BY p."id_Plan", p."Nombre", p."Fecha", p."Hora"
        ORDER BY p."Fecha", p."Hora"
        LIMIT %s
        """,
        (gid, _MAX_VOTACIONES),
    )
    return [(f[0], f[1], f[2], int(f[3]), int(f[4]), int(f[5])) for f in cursor.fetchall()]


def _consulta_horarios(cursor, gid):
    """Horarios propuestos que se están votando: [(nombre del plan, fecha, hora, pueden, no_pueden)]."""
    cursor.execute(
        """
        SELECT p."Nombre", h."Fecha", h."Hora",
               COUNT(hv."Id_Usuario") FILTER (WHERE hv."Puedo"),
               COUNT(hv."Id_Usuario") FILTER (WHERE NOT hv."Puedo")
        FROM public."Plan_Horario" h
        JOIN public."Plan" p ON p."id_Plan" = h."Id_Plan"
        LEFT JOIN public."Plan_Horario_Voto" hv ON hv."Id_Horario" = h."Id_Horario"
        WHERE p."Grupo_id" = %s AND h."Estado" = 'votacion'
        GROUP BY h."Id_Horario", p."Nombre", h."Fecha", h."Hora"
        ORDER BY h."Fecha", h."Hora"
        LIMIT %s
        """,
        (gid, _MAX_VOTACIONES),
    )
    return [(f[0], f[1], f[2], int(f[3]), int(f[4])) for f in cursor.fetchall()]


def _consulta_rechazados(cursor, gid):
    """Nombres de los planes que el grupo rechazó en el último mes (para no volver a proponerlos)."""
    cursor.execute(
        """
        SELECT p."Nombre" FROM public."Plan" p
        WHERE p."Grupo_id" = %s AND p."Estado" = 'rechazado'
          AND EXISTS (SELECT 1 FROM public."Plan_Voto" v
                      WHERE v."Id_Plan" = p."id_Plan" AND v."Fecha" >= now() - INTERVAL '30 days')
        ORDER BY (SELECT MAX(v."Fecha") FROM public."Plan_Voto" v WHERE v."Id_Plan" = p."id_Plan") DESC
        LIMIT %s
        """,
        (gid, _MAX_RECHAZADOS),
    )
    return [f[0] for f in cursor.fetchall()]


def _consulta_puntajes(cursor, gid):
    """Historial de puntajes del grupo: {"mejores": [...], "peores": [...]}, cada uno
    (nombre del plan, promedio, lugares). Mejores: promedio 4 o más; peores: 2 o menos."""
    cursor.execute(
        """
        SELECT p."Nombre", ROUND(AVG(up."Puntaje")::numeric, 1),
               (SELECT string_agg(pl."Nombre", ', ' ORDER BY pl."Orden")
                  FROM public."Plan_Lugar" pl WHERE pl."Id_Plan" = p."id_Plan")
        FROM public."Plan" p
        JOIN public."Usuario-Plan" up ON up."Plan_id" = p."id_Plan" AND up."Puntaje" IS NOT NULL
        WHERE p."Grupo_id" = %s AND p."Estado" = 'archivado'
        GROUP BY p."id_Plan", p."Nombre", p."Fecha"
        ORDER BY p."Fecha" DESC NULLS LAST
        LIMIT 20
        """,
        (gid,),
    )
    planes = [(f[0], float(f[1]), f[2] or "") for f in cursor.fetchall()]
    mejores = sorted((p for p in planes if p[1] >= 4), key=lambda p: -p[1])[:_MAX_PUNTUADOS]
    peores = sorted((p for p in planes if p[1] <= 2), key=lambda p: p[1])[:_MAX_PUNTUADOS]
    if not mejores and not peores:
        return None
    return {"mejores": mejores, "peores": peores}
