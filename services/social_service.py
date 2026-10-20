"""Social: publicaciones de planes, me gusta, comentarios, guardados y reportes.

Una publicación es un plan que su autor decide compartir, con un texto y
una visibilidad:
  - 'amigos'  → lo ven el autor y sus amigos.
  - 'publico' → lo ve cualquier usuario.

Qué se puede publicar (ver listar_publicables):
  - Una idea propia (estado 'idea', creada por el usuario).
  - Un plan al que el usuario fue y ya pasó (confirmó asistencia y está
    archivado, o es un plan personal con fecha pasada).

Lo que NUNCA sale en una publicación: el nombre del grupo, el chat ni los
votos. Se muestra solo el plan.

Todas las reglas (quién ve qué, quién puede borrar qué) se deciden acá, en
el servidor. La pantalla solo muestra lo que este servicio devuelve.

Las tablas se crean con migraciones/social.sql.
"""

from datetime import datetime

import psycopg2
from psycopg2 import errors

from database import get_db_connection, release_db_connection
from services.plan_service import PlanService

MAX_TEXTO = 500
MAX_COMENTARIO = 300
MAX_MOTIVO = 300
MAX_FOTOS = 2
MAX_BYTES_FOTO = 400 * 1024
_JPEG_INICIO = bytes((0xFF, 0xD8, 0xFF))
_JPEG_FIN = bytes((0xFF, 0xD9))

LIMITE_FEED = 10
LIMITE_FEED_MAX = 20
MAX_COMENTARIOS_MOSTRADOS = 100

# Freno contra el spam: se cuenta en la base, así vale entre pestañas.
MAX_PUBLICACIONES_POR_HORA = 5
MAX_COMENTARIOS_POR_MINUTO = 10
MAX_REPORTES_POR_HORA = 20

VISIBILIDADES = ("amigos", "publico")
ASPECTOS = ("cuadrada", "vertical")
MAX_AVISOS = 60
PESTANAS = ("amigos", "descubrir")
TIPOS_REPORTE = ("publicacion", "comentario")


class SocialError(Exception):
    """Algo que el usuario puede arreglar o que no puede hacer. El mensaje
    se le muestra tal cual; estado es el código HTTP que corresponde."""

    def __init__(self, mensaje, estado=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.estado = estado


def _numero(valor):
    """Decimal de la base → int si es entero, float si no (JSON friendly)."""
    if valor is None:
        return None
    numero = float(valor)
    return int(numero) if numero.is_integer() else numero


def _unir_nombres(nombres, total):
    """"Beto", "Beto y Dani", "Beto, Dani y Fede" o "Beto, Dani y 3 más"."""
    if total <= 1 or len(nombres) <= 1:
        return nombres[0] if nombres else ""
    if total == 2:
        return f"{nombres[0]} y {nombres[1]}"
    if total == 3 and len(nombres) >= 3:
        return f"{nombres[0]}, {nombres[1]} y {nombres[2]}"
    return f"{nombres[0]}, {nombres[1]} y {total - 2} más"


def _hace(momento):
    """"hace 5 min", "hace 2 h", "hace 3 días" o la fecha, para los avisos."""
    segundos = (datetime.now(momento.tzinfo) - momento).total_seconds()
    minutos = int(segundos // 60)
    if minutos < 1:
        return "ahora"
    if minutos < 60:
        return f"hace {minutos} min"
    horas = minutos // 60
    if horas < 24:
        return f"hace {horas} h"
    dias = horas // 24
    if dias < 7:
        return f"hace {dias} {'día' if dias == 1 else 'días'}"
    return momento.strftime("%d/%m")


def _hora(valor):
    return valor.strftime("%H:%M") if valor is not None else None


class SocialService:

    def __init__(self):
        self._planes = PlanService()

    # --- Reglas de visibilidad ---------------------------------------------

    def _visible_sql(self):
        """Condición SQL: la publicación `pub` la puede ver %(uid)s."""
        return f"""(
            pub."Id_Autor" = %(uid)s
            OR pub."Visibilidad" = 'publico'
            OR pub."Id_Autor" IN ({self._planes._amigos_sql()})
        )"""

    def _publicacion_visible(self, cursor, user_id, publicacion_id):
        """Devuelve (id_autor, id_plan) si la publicación existe, no está
        borrada y el usuario la puede ver. Si no, 404: no se distingue
        "no existe" de "no la podés ver" para no filtrar que existe."""
        cursor.execute(
            f"""
            SELECT pub."Id_Autor", pub."Id_Plan"
            FROM public."Publicacion" pub
            WHERE pub."Id_Publicacion" = %(pid)s
              AND NOT pub."Eliminada"
              AND {self._visible_sql()}
            """,
            {"uid": user_id, "pid": publicacion_id},
        )
        fila = cursor.fetchone()
        if fila is None:
            raise SocialError("No encontramos esa publicación.", 404)
        return fila

    # --- Feed ---------------------------------------------------------------

    def _consultar(self, cursor, user_id, filtro, parametros, limite):
        """Arma publicaciones completas (con su plan y sus lugares).

        La primera parte de cada fila tiene la forma que espera
        PlanService._armar_planes (id, nombre, fecha, hora, precio, estado
        ... y al final Precio_Min, Precio_Max), así los lugares de TODAS las
        publicaciones se traen en 2 consultas en total, no 2 por publicación.
        """
        parametros = dict(parametros, uid=user_id, lim=limite)
        cursor.execute(
            f"""
            SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                   pub."Id_Publicacion", pub."Texto", pub."Visibilidad", pub."Creada_En",
                   u."Id_Usuario", u."Nombre", u."Username",
                   p."Descripcion",
                   (SELECT COUNT(*) FROM public."Publicacion_Like" l
                     WHERE l."Id_Publicacion" = pub."Id_Publicacion"),
                   EXISTS (SELECT 1 FROM public."Publicacion_Like" l
                            WHERE l."Id_Publicacion" = pub."Id_Publicacion"
                              AND l."Id_Usuario" = %(uid)s),
                   (SELECT COUNT(*) FROM public."Publicacion_Comentario" c
                     WHERE c."Id_Publicacion" = pub."Id_Publicacion" AND NOT c."Eliminado"),
                   COALESCE(mi."Guardado", false),
                   (SELECT ROUND(AVG(x."Puntaje")::numeric, 1) FROM public."Usuario-Plan" x
                     WHERE x."Plan_id" = p."id_Plan"),
                   (SELECT COUNT(x."Puntaje") FROM public."Usuario-Plan" x
                     WHERE x."Plan_id" = p."id_Plan"),
                   pub."Aspecto",
                   p."Precio_Min", p."Precio_Max"
            FROM public."Publicacion" pub
            JOIN public."Usuarios" u ON u."Id_Usuario" = pub."Id_Autor"
            JOIN public."Plan" p ON p."id_Plan" = pub."Id_Plan"
            LEFT JOIN public."Usuario-Plan" mi
                   ON mi."Plan_id" = p."id_Plan" AND mi."Usuario_id" = %(uid)s
            WHERE NOT pub."Eliminada" AND {filtro}
            ORDER BY pub."Creada_En" DESC
            LIMIT %(lim)s
            """,
            parametros,
        )
        planes = self._planes._armar_planes(
            cursor,
            cursor.fetchall(),
            lambda f: {"_pub": f},
        )
        publicaciones = [self._serializar(plan, user_id) for plan in planes]
        self._agregar_fotos(cursor, publicaciones)
        self._agregar_quien_dio_like(cursor, publicaciones, user_id)
        self._agregar_comentarios_previa(cursor, publicaciones)
        return publicaciones

    def _agregar_fotos(self, cursor, publicaciones):
        """Una sola consulta para las fotos de todas (sin traer los bytes)."""
        if not publicaciones:
            return
        cursor.execute(
            """
            SELECT "Id_Publicacion", "Id_Foto"
            FROM public."Publicacion_Foto"
            WHERE "Id_Publicacion" = ANY(%s::uuid[])
            ORDER BY "Orden"
            """,
            ([p["id"] for p in publicaciones],),
        )
        por_publicacion = {}
        for publicacion_id, foto_id in cursor.fetchall():
            por_publicacion.setdefault(str(publicacion_id), []).append(str(foto_id))
        for p in publicaciones:
            p["fotos"] = por_publicacion.get(p["id"], [])

    def _agregar_quien_dio_like(self, cursor, publicaciones, user_id):
        """Hasta 2 nombres de quienes dieron me gusta (sin contar al propio
        usuario), primero sus amigos y después los más recientes. Una sola
        consulta para toda la página."""
        if not publicaciones:
            return
        cursor.execute(
            f"""
            SELECT x."Id_Publicacion", x."Nombre"
            FROM (
                SELECT l."Id_Publicacion", u."Nombre",
                       ROW_NUMBER() OVER (
                           PARTITION BY l."Id_Publicacion"
                           ORDER BY (l."Id_Usuario" IN ({self._planes._amigos_sql()})) DESC,
                                    l."Fecha" DESC
                       ) AS n
                FROM public."Publicacion_Like" l
                JOIN public."Usuarios" u ON u."Id_Usuario" = l."Id_Usuario"
                WHERE l."Id_Publicacion" = ANY(%(ids)s::uuid[])
                  AND l."Id_Usuario" <> %(uid)s
            ) x
            WHERE x.n <= 2
            ORDER BY x."Id_Publicacion", x.n
            """,
            {"uid": user_id, "ids": [p["id"] for p in publicaciones]},
        )
        por_publicacion = {}
        for publicacion_id, nombre in cursor.fetchall():
            por_publicacion.setdefault(str(publicacion_id), []).append(nombre)
        for p in publicaciones:
            p["likes_nombres"] = por_publicacion.get(p["id"], [])

    def _agregar_comentarios_previa(self, cursor, publicaciones):
        """Los 2 últimos comentarios de cada publicación (del más viejo al más
        nuevo), para mostrar debajo de la descripción sin abrir el hilo."""
        if not publicaciones:
            return
        cursor.execute(
            """
            SELECT x."Id_Publicacion", x."Id_Comentario", x."Nombre", x."Contenido"
            FROM (
                SELECT c."Id_Publicacion", c."Id_Comentario", u."Nombre", c."Contenido",
                       c."Creado_En",
                       ROW_NUMBER() OVER (
                           PARTITION BY c."Id_Publicacion" ORDER BY c."Creado_En" DESC
                       ) AS n
                FROM public."Publicacion_Comentario" c
                JOIN public."Usuarios" u ON u."Id_Usuario" = c."Id_Usuario"
                WHERE c."Id_Publicacion" = ANY(%s::uuid[]) AND NOT c."Eliminado"
            ) x
            WHERE x.n <= 2
            ORDER BY x."Id_Publicacion", x."Creado_En"
            """,
            ([p["id"] for p in publicaciones],),
        )
        por_publicacion = {}
        for publicacion_id, comentario_id, nombre, texto in cursor.fetchall():
            por_publicacion.setdefault(str(publicacion_id), []).append(
                {"id": str(comentario_id), "autor": nombre, "texto": texto}
            )
        for p in publicaciones:
            p["comentarios_previa"] = por_publicacion.get(p["id"], [])

    def _serializar(self, plan, user_id):
        f = plan["_pub"]
        return {
            "id": str(f[6]),
            "texto": f[7],
            "visibilidad": f[8],
            "creada_en": f[9].isoformat(),
            "autor": {"id": str(f[10]), "nombre": f[11], "username": f[12]},
            "es_mio": str(f[10]) == str(user_id),
            "plan": {
                "id": str(plan["id"]),
                "nombre": plan["nombre"],
                "descripcion": f[13],
                "estado": plan["estado"],
                "estado_texto": plan["estado_texto"],
                "fecha": plan["fecha"].isoformat() if plan["fecha"] else None,
                "hora": _hora(plan["hora"]),
                "precio_min": _numero(plan["precio_min"]),
                "precio_max": _numero(plan["precio_max"]),
                "lugares": [
                    {
                        "nombre": lugar["nombre"],
                        "hora": _hora(lugar["hora"]),
                        "precio_min": _numero(lugar["precio_min"]),
                        "precio_max": _numero(lugar["precio_max"]),
                    }
                    for lugar in plan["lugares"]
                ],
                "promedio": float(f[18]) if f[18] is not None else None,
                "votos": f[19],
            },
            "fotos": [],
            "aspecto": f[20],
            "likes_nombres": [],
            "comentarios_previa": [],
            "likes": f[14],
            "yo_di_like": bool(f[15]),
            "comentarios": f[16],
            "guardado": bool(f[17]),
        }

    def _pagina(self, user_id, filtro, parametros, antes, limite, con_total=False):
        """Una página (de la más nueva a la más vieja) de las publicaciones que
        cumplen `filtro`. antes: fecha ISO de la última que ya tenés."""
        limite = max(1, min(int(limite), LIMITE_FEED_MAX))
        parametros = dict(parametros)
        total = None

        if antes:
            try:
                datetime.fromisoformat(antes)
            except ValueError:
                raise SocialError("La fecha de corte no es válida.")
        filtro_pagina = filtro
        if antes:
            filtro_pagina += ' AND pub."Creada_En" < %(antes)s::timestamptz'
            parametros["antes"] = antes

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                # Se pide una de más para saber si queda otra página.
                publicaciones = self._consultar(cursor, user_id, filtro_pagina, parametros, limite + 1)
                if con_total:
                    cursor.execute(
                        f"""SELECT COUNT(*) FROM public."Publicacion" pub
                            WHERE NOT pub."Eliminada" AND {filtro}""",
                        dict(parametros, uid=user_id),
                    )
                    total = cursor.fetchone()[0]
        finally:
            release_db_connection(connection)

        hay_mas = len(publicaciones) > limite
        publicaciones = publicaciones[:limite]
        respuesta = {
            "publicaciones": publicaciones,
            "hay_mas": hay_mas,
            "siguiente": publicaciones[-1]["creada_en"] if hay_mas else None,
        }
        if con_total:
            respuesta["total"] = total
        return respuesta

    def listar_feed(self, user_id, pestana="amigos", antes=None, limite=LIMITE_FEED):
        """pestana 'amigos':    lo de tus amigos y lo tuyo.
        pestana 'descubrir': lo público de otras personas."""
        if pestana not in PESTANAS:
            raise SocialError("Esa pestaña no existe.")

        if pestana == "amigos":
            filtro = f"""(pub."Id_Autor" = %(uid)s
                          OR pub."Id_Autor" IN ({self._planes._amigos_sql()}))"""
        else:
            filtro = """(pub."Visibilidad" = 'publico' AND pub."Id_Autor" <> %(uid)s)"""

        return self._pagina(user_id, filtro, {}, antes, limite)

    def listar_de_autor(self, user_id, autor_id, antes=None, limite=LIMITE_FEED):
        """Las publicaciones de una persona que el usuario puede ver (las
        propias se ven todas; las ajenas, según su visibilidad). Trae además
        el total, para el perfil."""
        filtro = f'(pub."Id_Autor" = %(autor)s AND {self._visible_sql()})'
        return self._pagina(user_id, filtro, {"autor": autor_id}, antes, limite, con_total=True)

    def obtener_publicacion(self, user_id, publicacion_id):
        """Una publicación por su id (la página /social/p/<id> y los avisos del
        Inbox). 404 si no existe, está eliminada o el usuario no la puede ver."""
        filtro = f'(pub."Id_Publicacion" = %(pid)s AND {self._visible_sql()})'
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                resultado = self._consultar(cursor, user_id, filtro, {"pid": publicacion_id}, 1)
        finally:
            release_db_connection(connection)
        if not resultado:
            raise SocialError("No encontramos esa publicación.", 404)
        return resultado[0]

    def _una(self, cursor, user_id, publicacion_id):
        filtro = 'pub."Id_Publicacion" = %(pid)s'
        resultado = self._consultar(cursor, user_id, filtro, {"pid": publicacion_id}, 1)
        return resultado[0] if resultado else None

    # --- Publicar -----------------------------------------------------------

    def listar_publicables(self, user_id):
        """Los planes que el usuario puede publicar ahora (sin los que ya
        publicó)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."id_Plan", p."Nombre", p."Fecha", p."Hora", p."Precio", p."Estado",
                           p."Descripcion",
                           p."Precio_Min", p."Precio_Max"
                    FROM public."Plan" p
                    LEFT JOIN public."Usuario-Plan" up
                           ON up."Plan_id" = p."id_Plan" AND up."Usuario_id" = %(uid)s
                    WHERE (
                            (p."Estado" = 'idea' AND p."Creado_Por" = %(uid)s)
                         OR (up."Confirmado" = true
                             AND (p."Estado" = 'archivado'
                                  OR (p."Grupo_id" IS NULL AND p."Fecha" < CURRENT_DATE)))
                          )
                      AND NOT EXISTS (
                            SELECT 1 FROM public."Publicacion" pub
                            WHERE pub."Id_Plan" = p."id_Plan"
                              AND pub."Id_Autor" = %(uid)s
                              AND NOT pub."Eliminada")
                    ORDER BY p."Fecha" DESC NULLS LAST, p."Nombre"
                    """,
                    {"uid": user_id},
                )
                planes = self._planes._armar_planes(
                    cursor, cursor.fetchall(),
                    lambda f: {"descripcion": f[6]},
                )
        finally:
            release_db_connection(connection)

        return [
            {
                "id": str(p["id"]),
                "nombre": p["nombre"],
                "descripcion": p["descripcion"],
                "estado": p["estado"],
                "estado_texto": p["estado_texto"],
                "fecha": p["fecha"].isoformat() if p["fecha"] else None,
                "resumen_lugares": p["resumen_lugares"],
                "precio_min": _numero(p["precio_min"]),
                "precio_max": _numero(p["precio_max"]),
            }
            for p in planes
        ]

    @staticmethod
    def _validar_fotos(fotos):
        fotos = list(fotos or [])
        if len(fotos) > MAX_FOTOS:
            raise SocialError(f"Podés subir hasta {MAX_FOTOS} fotos.")
        for datos in fotos:
            if len(datos) > MAX_BYTES_FOTO:
                raise SocialError("Una de las fotos pesa demasiado.", 413)
            # Solo JPEG (el navegador las convierte antes de subir): empieza
            # con FF D8 FF y termina con FF D9.
            if not (datos[:3] == _JPEG_INICIO and datos[-2:] == _JPEG_FIN):
                raise SocialError("Las fotos tienen que ser imágenes JPEG válidas.")
        return fotos

    def publicar(self, user_id, plan_id, texto, visibilidad, fotos=(), aspecto="cuadrada"):
        fotos = self._validar_fotos(fotos)
        if aspecto not in ASPECTOS:
            raise SocialError("Elegí si la foto es cuadrada o vertical.")
        texto = (texto or "").strip()
        if len(texto) > MAX_TEXTO:
            raise SocialError(f"El texto puede tener hasta {MAX_TEXTO} caracteres.")
        if visibilidad not in VISIBILIDADES:
            raise SocialError("Elegí quién puede ver la publicación.")

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p."Estado", p."Creado_Por", p."Grupo_id", p."Fecha",
                           COALESCE(up."Confirmado", false)
                    FROM public."Plan" p
                    LEFT JOIN public."Usuario-Plan" up
                           ON up."Plan_id" = p."id_Plan" AND up."Usuario_id" = %s
                    WHERE p."id_Plan" = %s
                    """,
                    (user_id, plan_id),
                )
                fila = cursor.fetchone()
                if fila is None:
                    raise SocialError("Ese plan no existe.", 404)
                estado, creado_por, grupo_id, fecha, confirmado = fila

                es_idea_propia = estado == "idea" and str(creado_por) == str(user_id)
                paso_y_fue = bool(confirmado) and (
                    estado == "archivado"
                    or (grupo_id is None and fecha is not None and fecha < datetime.now().date())
                )
                if not (es_idea_propia or paso_y_fue):
                    raise SocialError(
                        "Solo podés publicar tus ideas o planes a los que ya fuiste.", 403
                    )

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM public."Publicacion"
                    WHERE "Id_Autor" = %s AND "Creada_En" > now() - interval '1 hour'
                    """,
                    (user_id,),
                )
                if cursor.fetchone()[0] >= MAX_PUBLICACIONES_POR_HORA:
                    raise SocialError("Publicaste mucho en poco tiempo. Probá en un rato.", 429)

                cursor.execute(
                    """
                    INSERT INTO public."Publicacion"
                        ("Id_Autor", "Id_Plan", "Texto", "Visibilidad", "Aspecto")
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING "Id_Publicacion"
                    """,
                    (user_id, plan_id, texto or None, visibilidad, aspecto),
                )
                publicacion_id = cursor.fetchone()[0]
                for orden, datos in enumerate(fotos):
                    cursor.execute(
                        """
                        INSERT INTO public."Publicacion_Foto" ("Id_Publicacion", "Orden", "Datos")
                        VALUES (%s, %s, %s)
                        """,
                        (publicacion_id, orden, psycopg2.Binary(datos)),
                    )
                publicacion = self._una(cursor, user_id, publicacion_id)
            connection.commit()
            return publicacion
        except errors.UniqueViolation:
            connection.rollback()
            raise SocialError("Ya publicaste ese plan.", 409)
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def eliminar_publicacion(self, user_id, publicacion_id):
        """Solo su autor. Se marca como eliminada (no se borra la fila)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public."Publicacion" SET "Eliminada" = true
                    WHERE "Id_Publicacion" = %s AND "Id_Autor" = %s AND NOT "Eliminada"
                    """,
                    (publicacion_id, user_id),
                )
                if cursor.rowcount == 0:
                    raise SocialError("No encontramos esa publicación.", 404)
                # Las fotos no se conservan: liberan lugar en la base.
                cursor.execute(
                    'DELETE FROM public."Publicacion_Foto" WHERE "Id_Publicacion" = %s',
                    (publicacion_id,),
                )
                cursor.execute(
                    'DELETE FROM public."Publicacion_Notificacion" WHERE "Id_Publicacion" = %s',
                    (publicacion_id,),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def obtener_foto(self, user_id, foto_id):
        """Los bytes de una foto, si el usuario puede ver su publicación."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT f."Datos"
                    FROM public."Publicacion_Foto" f
                    JOIN public."Publicacion" pub ON pub."Id_Publicacion" = f."Id_Publicacion"
                    WHERE f."Id_Foto" = %(fid)s
                      AND NOT pub."Eliminada"
                      AND {self._visible_sql()}
                    """,
                    {"fid": foto_id, "uid": user_id},
                )
                fila = cursor.fetchone()
        finally:
            release_db_connection(connection)
        if fila is None:
            raise SocialError("No encontramos esa foto.", 404)
        return bytes(fila[0])

    # --- Me gusta y guardar -------------------------------------------------

    def set_me_gusta(self, user_id, publicacion_id, me_gusta):
        """Pone o saca el me gusta. Es idempotente: pedir lo mismo dos veces
        deja el mismo resultado (un doble clic no lo invierte)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                autor_id, _ = self._publicacion_visible(cursor, user_id, publicacion_id)
                if me_gusta:
                    cursor.execute(
                        """
                        INSERT INTO public."Publicacion_Like" ("Id_Publicacion", "Id_Usuario")
                        VALUES (%s, %s) ON CONFLICT DO NOTHING
                        """,
                        (publicacion_id, user_id),
                    )
                    self._avisar(cursor, autor_id, user_id, "like", publicacion_id)
                else:
                    cursor.execute(
                        """
                        DELETE FROM public."Publicacion_Like"
                        WHERE "Id_Publicacion" = %s AND "Id_Usuario" = %s
                        """,
                        (publicacion_id, user_id),
                    )
                    cursor.execute(
                        """
                        DELETE FROM public."Publicacion_Notificacion"
                        WHERE "Tipo" = 'like' AND "Id_Publicacion" = %s AND "Id_Actor" = %s
                        """,
                        (publicacion_id, user_id),
                    )
                cursor.execute(
                    'SELECT COUNT(*) FROM public."Publicacion_Like" WHERE "Id_Publicacion" = %s',
                    (publicacion_id,),
                )
                likes = cursor.fetchone()[0]
            connection.commit()
            return {"yo_di_like": bool(me_gusta), "likes": likes}
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def set_guardado(self, user_id, publicacion_id, guardado):
        """Guarda el plan de la publicación como idea del usuario (o lo
        saca de guardados). Queda en "Ideas guardadas" y desde ahí se puede
        postular a un grupo (postular copia la idea, no la modifica)."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                _, plan_id = self._publicacion_visible(cursor, user_id, publicacion_id)
                cursor.execute(
                    """
                    INSERT INTO public."Usuario-Plan" ("Usuario_id", "Plan_id", "Confirmado", "Guardado")
                    VALUES (%s, %s, false, %s)
                    ON CONFLICT ("Usuario_id", "Plan_id")
                    DO UPDATE SET "Guardado" = EXCLUDED."Guardado"
                    """,
                    (user_id, plan_id, bool(guardado)),
                )
            connection.commit()
            return {"guardado": bool(guardado)}
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Comentarios --------------------------------------------------------

    def listar_comentarios(self, user_id, publicacion_id):
        """Los últimos comentarios, del más viejo al más nuevo."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                _, _ = self._publicacion_visible(cursor, user_id, publicacion_id)
                cursor.execute(
                    """
                    SELECT c."Id_Comentario", c."Contenido", c."Creado_En",
                           u."Id_Usuario", u."Nombre", u."Username",
                           pub."Id_Autor"
                    FROM public."Publicacion_Comentario" c
                    JOIN public."Usuarios" u ON u."Id_Usuario" = c."Id_Usuario"
                    JOIN public."Publicacion" pub ON pub."Id_Publicacion" = c."Id_Publicacion"
                    WHERE c."Id_Publicacion" = %s AND NOT c."Eliminado"
                    ORDER BY c."Creado_En" DESC
                    LIMIT %s
                    """,
                    (publicacion_id, MAX_COMENTARIOS_MOSTRADOS),
                )
                filas = cursor.fetchall()
        finally:
            release_db_connection(connection)

        return [self._comentario(f, user_id) for f in reversed(filas)]

    def _comentario(self, fila, user_id):
        return {
            "id": str(fila[0]),
            "texto": fila[1],
            "creado_en": fila[2].isoformat(),
            "autor": {"id": str(fila[3]), "nombre": fila[4], "username": fila[5]},
            # Borra el autor del comentario o el autor de la publicación.
            "puedo_borrar": str(user_id) in (str(fila[3]), str(fila[6])),
        }

    def comentar(self, user_id, publicacion_id, texto):
        texto = (texto or "").strip()
        if not texto:
            raise SocialError("El comentario está vacío.")
        if len(texto) > MAX_COMENTARIO:
            raise SocialError(f"El comentario puede tener hasta {MAX_COMENTARIO} caracteres.")

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                autor_id, _ = self._publicacion_visible(cursor, user_id, publicacion_id)

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM public."Publicacion_Comentario"
                    WHERE "Id_Usuario" = %s AND "Creado_En" > now() - interval '1 minute'
                    """,
                    (user_id,),
                )
                if cursor.fetchone()[0] >= MAX_COMENTARIOS_POR_MINUTO:
                    raise SocialError("Estás comentando muy rápido. Esperá un momento.", 429)

                cursor.execute(
                    """
                    WITH nuevo AS (
                        INSERT INTO public."Publicacion_Comentario"
                            ("Id_Publicacion", "Id_Usuario", "Contenido")
                        VALUES (%s, %s, %s)
                        RETURNING "Id_Comentario", "Contenido", "Creado_En", "Id_Usuario"
                    )
                    SELECT n."Id_Comentario", n."Contenido", n."Creado_En",
                           u."Id_Usuario", u."Nombre", u."Username",
                           pub."Id_Autor"
                    FROM nuevo n
                    JOIN public."Usuarios" u ON u."Id_Usuario" = n."Id_Usuario"
                    JOIN public."Publicacion" pub ON pub."Id_Publicacion" = %s
                    """,
                    (publicacion_id, user_id, texto, publicacion_id),
                )
                fila = cursor.fetchone()
                comentario = self._comentario(fila, user_id)
                self._avisar(cursor, autor_id, user_id, "comentario", publicacion_id, fila[0])
            connection.commit()
            return comentario
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def eliminar_comentario(self, user_id, comentario_id):
        """Lo puede borrar quien lo escribió o el autor de la publicación."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public."Publicacion_Comentario" c
                    SET "Eliminado" = true
                    FROM public."Publicacion" pub
                    WHERE c."Id_Comentario" = %s
                      AND pub."Id_Publicacion" = c."Id_Publicacion"
                      AND NOT c."Eliminado"
                      AND (c."Id_Usuario" = %s OR pub."Id_Autor" = %s)
                    """,
                    (comentario_id, user_id, user_id),
                )
                if cursor.rowcount == 0:
                    raise SocialError("No encontramos ese comentario.", 404)
                cursor.execute(
                    'DELETE FROM public."Publicacion_Notificacion" WHERE "Id_Comentario" = %s',
                    (comentario_id,),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Reportes -----------------------------------------------------------

    def reportar(self, user_id, tipo, objetivo_id, motivo):
        """Guarda la denuncia para que el equipo la revise en la base
        (tabla "Publicacion_Reporte"). Reportar dos veces lo mismo no suma."""
        if tipo not in TIPOS_REPORTE:
            raise SocialError("No se puede reportar eso.")
        motivo = (motivo or "").strip()
        if len(motivo) > MAX_MOTIVO:
            raise SocialError(f"El motivo puede tener hasta {MAX_MOTIVO} caracteres.")

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                if tipo == "publicacion":
                    self._publicacion_visible(cursor, user_id, objetivo_id)
                else:
                    cursor.execute(
                        """
                        SELECT c."Id_Publicacion"
                        FROM public."Publicacion_Comentario" c
                        WHERE c."Id_Comentario" = %s AND NOT c."Eliminado"
                        """,
                        (objetivo_id,),
                    )
                    fila = cursor.fetchone()
                    if fila is None:
                        raise SocialError("No encontramos ese comentario.", 404)
                    self._publicacion_visible(cursor, user_id, fila[0])

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM public."Publicacion_Reporte"
                    WHERE "Id_Reportante" = %s AND "Creado_En" > now() - interval '1 hour'
                    """,
                    (user_id,),
                )
                if cursor.fetchone()[0] >= MAX_REPORTES_POR_HORA:
                    raise SocialError("Mandaste muchos reportes seguidos. Probá en un rato.", 429)

                cursor.execute(
                    """
                    INSERT INTO public."Publicacion_Reporte"
                        ("Tipo", "Id_Objetivo", "Id_Reportante", "Motivo")
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT ("Id_Reportante", "Tipo", "Id_Objetivo") DO NOTHING
                    """,
                    (tipo, objetivo_id, user_id, motivo or None),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Avisos del Inbox ---------------------------------------------------

    def _avisar(self, cursor, receptor_id, actor_id, tipo, publicacion_id, comentario_id=None):
        """Crea el aviso de un me gusta o un comentario para el autor de la
        publicación. Nadie se avisa a sí mismo."""
        if str(receptor_id) == str(actor_id):
            return
        if tipo == "like":
            cursor.execute(
                """
                INSERT INTO public."Publicacion_Notificacion"
                    ("Id_Usuario", "Id_Actor", "Tipo", "Id_Publicacion")
                VALUES (%s, %s, 'like', %s)
                ON CONFLICT ("Id_Usuario", "Id_Publicacion", "Id_Actor") WHERE "Tipo" = 'like'
                DO NOTHING
                """,
                (receptor_id, actor_id, publicacion_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO public."Publicacion_Notificacion"
                    ("Id_Usuario", "Id_Actor", "Tipo", "Id_Publicacion", "Id_Comentario")
                VALUES (%s, %s, 'comentario', %s, %s)
                """,
                (receptor_id, actor_id, publicacion_id, comentario_id),
            )

    # Los avisos que valen: de una publicación que sigue ahí y, si es de un
    # comentario, de uno que no se borró.
    _AVISOS_VIGENTES = """
        JOIN public."Publicacion" pub
               ON pub."Id_Publicacion" = n."Id_Publicacion" AND NOT pub."Eliminada"
        LEFT JOIN public."Publicacion_Comentario" c ON c."Id_Comentario" = n."Id_Comentario"
        WHERE n."Id_Usuario" = %(uid)s
          AND (n."Tipo" = 'like' OR (c."Id_Comentario" IS NOT NULL AND NOT c."Eliminado"))
    """

    def listar_avisos(self, user_id, limite=MAX_AVISOS):
        """Los avisos de me gusta y comentarios, del más reciente al más viejo.

        Los me gusta de una misma publicación se juntan en un solo aviso
        ("Beto y Dani"); cada comentario es su propio aviso."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT n."Tipo", n."Creada_En", n."Leida", n."Id_Publicacion",
                           a."Nombre", p."Nombre", c."Contenido",
                           (SELECT f."Id_Foto" FROM public."Publicacion_Foto" f
                             WHERE f."Id_Publicacion" = n."Id_Publicacion"
                             ORDER BY f."Orden" LIMIT 1)
                    FROM public."Publicacion_Notificacion" n
                    JOIN public."Usuarios" a ON a."Id_Usuario" = n."Id_Actor"
                    JOIN public."Publicacion" pub
                           ON pub."Id_Publicacion" = n."Id_Publicacion" AND NOT pub."Eliminada"
                    JOIN public."Plan" p ON p."id_Plan" = pub."Id_Plan"
                    LEFT JOIN public."Publicacion_Comentario" c ON c."Id_Comentario" = n."Id_Comentario"
                    WHERE n."Id_Usuario" = %(uid)s
                      AND (n."Tipo" = 'like' OR (c."Id_Comentario" IS NOT NULL AND NOT c."Eliminado"))
                    ORDER BY n."Creada_En" DESC
                    LIMIT 300
                    """,
                    {"uid": user_id},
                )
                filas = cursor.fetchall()
        finally:
            release_db_connection(connection)

        avisos = []
        de_likes = {}   # publicación -> aviso de me gusta ya creado
        for tipo, momento, leida, publicacion_id, actor, plan, texto, foto in filas:
            publicacion_id = str(publicacion_id)
            if tipo == "like":
                aviso = de_likes.get(publicacion_id)
                if aviso is None:
                    aviso = {
                        "tipo": "like", "publicacion_id": publicacion_id, "plan": plan,
                        "foto": str(foto) if foto else None, "actores": [], "total": 0,
                        "creada_en": momento.isoformat(), "hace": _hace(momento), "no_leida": False,
                    }
                    de_likes[publicacion_id] = aviso
                    avisos.append(aviso)
                aviso["total"] += 1
                if len(aviso["actores"]) < 3:
                    aviso["actores"].append(actor)
                aviso["no_leida"] = aviso["no_leida"] or not leida
            else:
                avisos.append({
                    "tipo": "comentario", "publicacion_id": publicacion_id, "plan": plan,
                    "foto": str(foto) if foto else None, "actor": actor,
                    "texto": texto if len(texto) <= 140 else texto[:139] + "…",
                    "creada_en": momento.isoformat(), "hace": _hace(momento), "no_leida": not leida,
                })
        for aviso in avisos:
            if aviso["tipo"] == "like":
                aviso["texto_actores"] = _unir_nombres(aviso["actores"], aviso["total"])
        return avisos[:limite]

    def contar_avisos_no_leidos(self, user_id):
        """Cuántos avisos nuevos hay (los me gusta de una publicación cuentan
        como uno). Es lo que suma al número de la barra lateral."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(DISTINCT CASE WHEN n."Tipo" = 'like'
                                               THEN n."Id_Publicacion"::text
                                               ELSE n."Id_Notificacion"::text END)
                    FROM public."Publicacion_Notificacion" n
                    """ + self._AVISOS_VIGENTES + """
                      AND NOT n."Leida"
                    """,
                    {"uid": user_id},
                )
                return cursor.fetchone()[0]
        finally:
            release_db_connection(connection)

    def marcar_avisos_leidos(self, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE public."Publicacion_Notificacion" SET "Leida" = true '
                    'WHERE "Id_Usuario" = %s AND NOT "Leida"',
                    (user_id,),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Moderación ---------------------------------------------------------

    def listar_reportes(self):
        """Los reportes sin revisar, juntando los de un mismo contenido (con
        cuántas personas lo reportaron y por qué). El más reciente primero."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT r."Tipo", r."Id_Objetivo", r."Motivo", r."Creado_En", rep."Nombre"
                    FROM public."Publicacion_Reporte" r
                    JOIN public."Usuarios" rep ON rep."Id_Usuario" = r."Id_Reportante"
                    WHERE NOT r."Revisado"
                    ORDER BY r."Creado_En" DESC
                    """
                )
                filas = cursor.fetchall()

                grupos = {}
                for tipo, objetivo, motivo, momento, quien in filas:
                    g = grupos.setdefault((tipo, str(objetivo)), {
                        "tipo": tipo, "id": str(objetivo), "total": 0, "motivos": [],
                        "ultimo": momento,
                    })
                    g["total"] += 1
                    if motivo and len(g["motivos"]) < 5:
                        g["motivos"].append(f"{quien}: {motivo}")

                reportes = []
                for g in grupos.values():
                    if g["tipo"] == "publicacion":
                        cursor.execute(
                            """
                            SELECT u."Nombre", p."Nombre", pub."Texto", pub."Eliminada", pub."Id_Publicacion",
                                   (SELECT f."Id_Foto" FROM public."Publicacion_Foto" f
                                     WHERE f."Id_Publicacion" = pub."Id_Publicacion"
                                     ORDER BY f."Orden" LIMIT 1)
                            FROM public."Publicacion" pub
                            JOIN public."Usuarios" u ON u."Id_Usuario" = pub."Id_Autor"
                            JOIN public."Plan" p ON p."id_Plan" = pub."Id_Plan"
                            WHERE pub."Id_Publicacion" = %s
                            """,
                            (g["id"],),
                        )
                        fila = cursor.fetchone()
                        if fila:
                            g.update(autor=fila[0], plan=fila[1], texto=fila[2] or "",
                                     eliminado=fila[3], publicacion_id=str(fila[4]),
                                     foto=str(fila[5]) if fila[5] else None)
                    else:
                        cursor.execute(
                            """
                            SELECT u."Nombre", p."Nombre", c."Contenido", c."Eliminado", c."Id_Publicacion"
                            FROM public."Publicacion_Comentario" c
                            JOIN public."Usuarios" u ON u."Id_Usuario" = c."Id_Usuario"
                            JOIN public."Publicacion" pub ON pub."Id_Publicacion" = c."Id_Publicacion"
                            JOIN public."Plan" p ON p."id_Plan" = pub."Id_Plan"
                            WHERE c."Id_Comentario" = %s
                            """,
                            (g["id"],),
                        )
                        fila = cursor.fetchone()
                        if fila:
                            g.update(autor=fila[0], plan=fila[1], texto=fila[2],
                                     eliminado=fila[3], publicacion_id=str(fila[4]), foto=None)
                    # Si el contenido ya no existe (se borró el plan), no hay nada que revisar.
                    if "autor" in g:
                        g["hace"] = _hace(g["ultimo"])
                        reportes.append(g)
                reportes.sort(key=lambda r: r["ultimo"], reverse=True)
                return reportes
        finally:
            release_db_connection(connection)

    def resolver_reportes(self, tipo, objetivo_id, accion):
        """accion 'eliminar': borra el contenido reportado (y deja de mostrarse).
        accion 'descartar': el contenido queda como está.
        En los dos casos todos los reportes de ese contenido pasan a revisados."""
        if tipo not in TIPOS_REPORTE:
            raise SocialError("Tipo de reporte inválido.")
        if accion not in ("eliminar", "descartar"):
            raise SocialError("Acción inválida.")

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                if accion == "eliminar":
                    if tipo == "publicacion":
                        cursor.execute(
                            'UPDATE public."Publicacion" SET "Eliminada" = true WHERE "Id_Publicacion" = %s',
                            (objetivo_id,),
                        )
                        cursor.execute(
                            'DELETE FROM public."Publicacion_Foto" WHERE "Id_Publicacion" = %s',
                            (objetivo_id,),
                        )
                        cursor.execute(
                            'DELETE FROM public."Publicacion_Notificacion" WHERE "Id_Publicacion" = %s',
                            (objetivo_id,),
                        )
                    else:
                        cursor.execute(
                            'UPDATE public."Publicacion_Comentario" SET "Eliminado" = true WHERE "Id_Comentario" = %s',
                            (objetivo_id,),
                        )
                        cursor.execute(
                            'DELETE FROM public."Publicacion_Notificacion" WHERE "Id_Comentario" = %s',
                            (objetivo_id,),
                        )
                cursor.execute(
                    """
                    UPDATE public."Publicacion_Reporte" SET "Revisado" = true
                    WHERE "Tipo" = %s AND "Id_Objetivo" = %s
                    """,
                    (tipo, objetivo_id),
                )
                if cursor.rowcount == 0:
                    raise SocialError("No encontramos ese reporte.", 404)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

