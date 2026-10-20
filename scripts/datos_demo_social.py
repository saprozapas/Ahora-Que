"""Carga (y borra) publicaciones de ejemplo en Social, para ver cómo queda el feed.

Uso, desde la raíz del repo (escribe en la base del .env, que es la compartida):

    python scripts/datos_demo_social.py crear --mail tu@mail.com
    python scripts/datos_demo_social.py borrar --mail tu@mail.com

Qué crea:
  * 4 usuarios de ejemplo (nombre "... (demo)", usuario demo_*, sin contraseña:
    no se puede iniciar sesión con ellos).
  * Amistad entre tu usuario y 2 de ellos (para que el feed "Amigos" tenga
    contenido de otras personas).
  * 9 planes (ideas y planes ya vividos, enlazados a lugares reales de la base
    cuando existen) y su publicación: 2 a nombre de tu usuario y 7 de los
    usuarios de ejemplo, con fotos dibujadas en el momento, me gusta y comentarios.
  * Los avisos en tu Inbox (pestaña Publicaciones) por los me gusta y comentarios
    que recibieron tus 2 publicaciones.

Todo lleva ids fijos (derivados de un nombre), así que `crear` se puede repetir
y `borrar` quita exactamente lo creado: publicaciones, planes, amistades y los
usuarios de ejemplo. No toca nada más.

Las fotos se dibujan con Pillow (solo para este script):  pip install pillow
"""

import argparse
import io
import os
import random
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

NAMESPACE = uuid.UUID("5f0c2a54-1b7e-4a7a-9d52-0d6f3c1f6e11")


def _id(clave):
    return str(uuid.uuid5(NAMESPACE, clave))


# ---------------------------------------------------------------------------
# Datos de ejemplo
# ---------------------------------------------------------------------------

USUARIOS = {
    "vale": "Vale (demo)",
    "mateo": "Mateo (demo)",
    "lucia": "Lucía (demo)",
    "joaquin": "Joaquín (demo)",
}
AMIGOS_DEL_USUARIO = ("vale", "mateo")

# autor: "yo" (el usuario del --mail) o una clave de USUARIOS.
# lugares: nombres exactos de "Lugar"; si no existe en la base queda solo el nombre.
# estado: "idea" o "archivado" (plan ya vivido: lleva fecha y puntajes).
PUBLICACIONES = [
    {
        "clave": "merienda", "autor": "yo", "estado": "idea",
        "nombre": "Merienda en Ciudad Vieja",
        "descripcion": "Café con medialunas en un clásico y caminata hasta la Plaza Independencia.",
        "lugares": ["Café Brasilero", "Plaza Independencia"], "precio": (400, 700),
        "texto": "Idea para el finde, ¿quién se suma?", "visibilidad": "amigos",
        "fotos": ["taza"], "hace_min": 25,
        "likes": ["vale", "mateo"],
        "comentarios": [("vale", "Yo voy! Hace rato que no voy al Brasilero", 20),
                        ("mateo", "Sumo, pero después de las 4", 12)],
    },
    {
        "clave": "cine-helado", "autor": "yo", "estado": "idea",
        "nombre": "Tarde de cine y helado",
        "descripcion": "Una película en Cinemateca y helado de postre.",
        "lugares": ["Cinemateca", "Heladería Del Abuelo"], "precio": (450, 800),
        "texto": "Para los días de lluvia.", "visibilidad": "publico",
        "fotos": ["cine"], "hace_min": 60 * 5,
        "likes": ["vale", "lucia", "joaquin"],
        "comentarios": [("lucia", "Qué buena combinación", 250)],
    },
    {
        "clave": "rambla", "autor": "vale", "estado": "archivado", "dias": 3, "hora": time(19, 30),
        "nombre": "Atardecer en la rambla de Pocitos",
        "descripcion": "Caminata por la rambla y helado mirando el sol caer.",
        "lugares": ["Playa Pocitos", "Heladería García"], "precio": (150, 350),
        "texto": "Fuimos justo para el atardecer. Imperdible.", "visibilidad": "publico",
        "fotos": ["atardecer", "playa"], "hace_min": 60 * 30,
        "puntajes": {"vale": 5, "mateo": 5, "lucia": 4},
        "likes": ["yo", "mateo", "lucia", "joaquin"],
        "comentarios": [("mateo", "Increíble tarde, repetimos", 1700), ("yo", "Qué fotos!", 1650),
                        ("lucia", "Me faltó ir, la próxima voy", 1500)],
    },
    {
        "clave": "picnic", "autor": "vale", "estado": "idea",
        "nombre": "Picnic en el Parque Rodó",
        "descripcion": "Manta, mate y algo rico para compartir bajo los árboles.",
        "lugares": ["Parque Rodó"], "precio": (0, 300),
        "texto": "Se viene la primavera.", "visibilidad": "amigos",
        "fotos": ["parque"], "hace_min": 60 * 8,
        "likes": ["yo", "mateo"], "comentarios": [("yo", "Llevo el mate", 400)],
    },
    {
        "clave": "cafes", "autor": "mateo", "estado": "idea",
        "nombre": "Ruta de cafés de especialidad",
        "descripcion": "Dos cafés en una tarde para comparar el mismo espresso.",
        "lugares": ["Escaramuza", "Café Brasilero"], "precio": (350, 600),
        "texto": "Para los que dicen que todo el café sabe igual.", "visibilidad": "publico",
        "fotos": [], "hace_min": 60 * 14,
        "likes": ["vale", "yo"], "comentarios": [("vale", "Esto lo hago el sábado", 800)],
    },
    {
        "clave": "pizza", "autor": "mateo", "estado": "idea",
        "nombre": "Noche de pizza",
        "descripcion": "Pizza y fugazzeta con los de siempre.",
        "lugares": ["Brandi Pizza"], "precio": (500, 900),
        "texto": "Quién se anota?", "visibilidad": "amigos",
        "fotos": ["pizza"], "hace_min": 60 * 22,
        "likes": ["yo"], "comentarios": [],
    },
    {
        "clave": "museos", "autor": "lucia", "estado": "archivado", "dias": 8, "hora": time(15, 0),
        "nombre": "Museos de Ciudad Vieja",
        "descripcion": "Una tarde recorriendo museos a pie, sin apuro.",
        "lugares": ["Cabildo", "Museo Andes 1972"], "precio": (0, 400),
        "texto": "El Museo Andes 1972 te deja pensando.", "visibilidad": "publico",
        "fotos": ["museo"], "hace_min": 60 * 40,
        "puntajes": {"lucia": 5, "joaquin": 4},
        "likes": ["yo", "vale"], "comentarios": [("vale", "Lo tengo pendiente", 2300)],
    },
    {
        "clave": "cerro", "autor": "joaquin", "estado": "archivado", "dias": 15, "hora": time(9, 0),
        "nombre": "Trekking al Cerro Pan de Azúcar",
        "descripcion": "Subida suave con una vista enorme de la sierra.",
        "lugares": ["Cerro Pan de Azúcar"], "precio": (100, 300),
        "texto": "Llevá agua de más y buen calzado. Valió cada escalón.", "visibilidad": "publico",
        "fotos": ["cerro", "cerro2"], "aspecto": "vertical", "hace_min": 60 * 72,
        "puntajes": {"joaquin": 5, "lucia": 5},
        "likes": ["yo", "vale", "mateo", "lucia"],
        "comentarios": [("lucia", "La mejor salida del año", 4200), ("yo", "Anotado para el finde largo", 4000)],
    },
    {
        "clave": "buceo", "autor": "joaquin", "estado": "idea",
        "nombre": "Tarde de playa en el Buceo",
        "descripcion": "Playa, mate y una pelota de fútbol.",
        "lugares": ["Playa del Buceo"], "precio": (0, 200),
        "texto": "", "visibilidad": "publico",
        "fotos": ["playa2"], "hace_min": 60 * 96,
        "likes": ["vale"], "comentarios": [],
    },
]


# ---------------------------------------------------------------------------
# Fotos: ilustraciones dibujadas con Pillow
# ---------------------------------------------------------------------------

def _fotos():
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        raise SystemExit("Hace falta Pillow para dibujar las fotos de ejemplo:  pip install pillow")

    T = 900

    def degradado(c1, c2):
        img = Image.new("RGB", (T, T), c1)
        d = ImageDraw.Draw(img)
        for y in range(T):
            t = y / T
            d.line([(0, y), (T, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
        return img, d

    def terminar(img, semilla):
        # Un poco de grano para que no se vea tan "plano".
        grano = Image.effect_noise((T, T), 14).convert("RGB")
        img = Image.blend(img, grano, 0.05)
        img = img.filter(ImageFilter.GaussianBlur(0.6))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82)
        datos = buf.getvalue()
        assert len(datos) <= 400 * 1024, "foto demasiado pesada"
        return datos

    def atardecer():
        img, d = degradado((250, 170, 100), (90, 50, 110))
        d.ellipse([290, 340, 610, 660], fill=(255, 224, 140))
        d.rectangle([0, 600, T, T], fill=(38, 54, 78))
        for y in range(620, T, 22):
            d.line([(220, y), (680, y)], fill=(255, 200, 120), width=3)
        return terminar(img, 1)

    def playa(colores, semilla):
        img, d = degradado(*colores)
        d.rectangle([0, 520, T, 700], fill=(70, 140, 190))
        for y in range(540, 700, 26):
            d.arc([-200, y, 520, y + 40], 0, 180, fill=(220, 240, 250), width=3)
            d.arc([380, y + 10, 1100, y + 50], 0, 180, fill=(220, 240, 250), width=3)
        d.rectangle([0, 700, T, T], fill=(236, 214, 160))
        d.ellipse([650, 130, 770, 250], fill=(255, 238, 190))
        return terminar(img, semilla)

    def parque():
        img, d = degradado((170, 214, 240), (225, 240, 225))
        d.rectangle([0, 560, T, T], fill=(108, 160, 96))
        for x, h in ((140, 330), (380, 420), (650, 360), (800, 280)):
            d.rectangle([x - 18, 560 - h // 3, x + 18, 600], fill=(98, 70, 48))
            d.ellipse([x - 120, 560 - h, x + 120, 560 - h + 240], fill=(58, 118, 70))
        d.polygon([(300, 760), (600, 760), (660, 880), (240, 880)], fill=(228, 80, 70))   # manta
        d.rectangle([360, 740, 520, 770], fill=(250, 240, 220))
        return terminar(img, 3)

    def taza():
        img, d = degradado((240, 224, 204), (192, 152, 120))
        d.ellipse([180, 700, 720, 780], fill=(176, 138, 106))
        d.rounded_rectangle([230, 380, 600, 720], 60, fill=(247, 242, 232))
        d.arc([540, 440, 740, 650], -90, 90, fill=(247, 242, 232), width=36)
        d.ellipse([245, 392, 585, 480], fill=(102, 66, 44))
        for x in (330, 410, 490):
            d.arc([x - 20, 250, x + 20, 370], 90, 270, fill=(255, 255, 255), width=6)
        return terminar(img, 4)

    def cine():
        img, d = degradado((22, 20, 50), (80, 52, 110))
        d.rectangle([110, 190, 790, 560], fill=(16, 16, 24), outline=(235, 235, 235), width=8)
        d.polygon([(410, 300), (410, 450), (540, 375)], fill=(245, 245, 245))
        for x in range(150, 760, 90):
            d.rounded_rectangle([x, 640, x + 70, 760], 18, fill=(150, 40, 54))
        return terminar(img, 5)

    def pizza():
        img, d = degradado((236, 214, 170), (190, 140, 96))
        d.ellipse([140, 160, 760, 780], fill=(214, 160, 84))
        d.ellipse([175, 195, 725, 745], fill=(236, 176, 74))
        d.ellipse([205, 225, 695, 715], fill=(214, 76, 56))
        rnd = random.Random(6)
        for _ in range(26):
            x, y = rnd.randint(250, 640), rnd.randint(280, 640)
            d.ellipse([x - 26, y - 26, x + 26, y + 26], fill=(250, 232, 190))
        for _ in range(10):
            x, y = rnd.randint(260, 630), rnd.randint(290, 630)
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(64, 130, 62))
        return terminar(img, 6)

    def museo():
        img, d = degradado((206, 224, 240), (240, 232, 214))
        d.polygon([(130, 330), (450, 170), (770, 330)], fill=(176, 160, 146))
        d.rectangle([130, 330, 770, 370], fill=(196, 182, 166))
        for x in range(170, 760, 100):
            d.rectangle([x, 380, x + 50, 690], fill=(236, 228, 214))
        d.rectangle([110, 690, 790, 740], fill=(176, 160, 146))
        d.rectangle([90, 740, 810, 790], fill=(150, 136, 124))
        return terminar(img, 7)

    def cerro(colores, semilla):
        img, d = degradado(*colores)
        d.ellipse([650, 110, 760, 220], fill=(255, 240, 200))
        d.polygon([(0, 700), (260, 340), (500, 700)], fill=(72, 112, 84))
        d.polygon([(300, 700), (620, 230), (930, 700)], fill=(48, 86, 64))
        d.polygon([(560, 330), (620, 230), (680, 330), (640, 320), (600, 345)], fill=(240, 244, 248))
        d.rectangle([0, 700, T, T], fill=(34, 58, 42))
        return terminar(img, semilla)

    return {
        "atardecer": atardecer(),
        "playa": playa(((150, 200, 240), (236, 244, 250)), 2),
        "playa2": playa(((250, 214, 150), (252, 238, 220)), 8),
        "parque": parque(),
        "taza": taza(),
        "cine": cine(),
        "pizza": pizza(),
        "museo": museo(),
        "cerro": cerro(((140, 190, 230), (230, 236, 242)), 9),
        "cerro2": cerro(((250, 200, 140), (120, 90, 120)), 10),
    }


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def _conectar():
    from dotenv import load_dotenv

    load_dotenv(os.path.join(RAIZ, ".env"))
    from database import get_db_connection

    return get_db_connection()


def _ids_demo():
    usuarios = [_id(f"usuario:{k}") for k in USUARIOS]
    planes = [_id(f"plan:{p['clave']}") for p in PUBLICACIONES]
    return usuarios, planes


def _borrar(cur, uid_yo):
    usuarios, planes = _ids_demo()
    cur.execute('DELETE FROM public."Amistades" WHERE "Id_Usuario1" = ANY(%s::uuid[]) OR "Id_Usuario2" = ANY(%s::uuid[])',
                (usuarios, usuarios))
    amistades = cur.rowcount
    # Borrar el plan se lleva su publicación, lugares y asistencias (ON DELETE CASCADE).
    cur.execute('DELETE FROM public."Plan" WHERE "id_Plan" = ANY(%s::uuid[])', (planes,))
    borrados_planes = cur.rowcount
    # Los usuarios de ejemplo se llevan sus likes y comentarios.
    cur.execute('DELETE FROM public."Usuarios" WHERE "Id_Usuario" = ANY(%s::uuid[])', (usuarios,))
    return {"planes": borrados_planes, "usuarios": cur.rowcount, "amistades": amistades}


def _crear(cur, uid_yo):
    from psycopg2 import Binary

    fotos = _fotos()
    ahora = datetime.now(timezone.utc)
    quien = {"yo": uid_yo, **{k: _id(f"usuario:{k}") for k in USUARIOS}}

    for k, nombre in USUARIOS.items():
        cur.execute(
            'INSERT INTO public."Usuarios" ("Id_Usuario", "Nombre", "Username", "Mail") VALUES (%s, %s, %s, %s)',
            (quien[k], nombre, f"demo_{k}", f"demo.{k}@ahoraque.demo"),
        )
    for k in AMIGOS_DEL_USUARIO:
        # La tabla exige Id_Usuario1 < Id_Usuario2 (una sola fila por pareja).
        menor, mayor = sorted((uid_yo, quien[k]))
        cur.execute('INSERT INTO public."Amistades" ("Id_Usuario1", "Id_Usuario2") VALUES (%s, %s)',
                    (menor, mayor))

    contadores = {"planes": 0, "publicaciones": 0, "fotos": 0, "likes": 0, "comentarios": 0, "avisos": 0, "lugares_reales": 0}
    for p in PUBLICACIONES:
        plan_id, pub_id = _id(f"plan:{p['clave']}"), _id(f"publicacion:{p['clave']}")
        autor = quien[p["autor"]]
        fecha = (date.today() - timedelta(days=p["dias"])) if p["estado"] == "archivado" else None
        pmin, pmax = p["precio"]

        cur.execute(
            """INSERT INTO public."Plan"
                   ("id_Plan", "Nombre", "Estado", "Creado_Por", "Descripcion", "Fecha", "Hora", "Precio_Min", "Precio_Max")
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (plan_id, p["nombre"], p["estado"], autor, p["descripcion"], fecha, p.get("hora"), pmin, pmax),
        )
        contadores["planes"] += 1

        for orden, nombre_lugar in enumerate(p["lugares"], start=1):
            cur.execute('SELECT "Id_Lugar" FROM public."Lugar" WHERE "Nombre" = %s ORDER BY "Id_Lugar" LIMIT 1',
                        (nombre_lugar,))
            fila = cur.fetchone()
            contadores["lugares_reales"] += 1 if fila else 0
            cur.execute(
                """INSERT INTO public."Plan_Lugar" ("Id_Plan", "Id_Lugar", "Nombre", "Orden", "Precio_Min", "Precio_Max")
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (plan_id, fila[0] if fila else None, nombre_lugar, orden,
                 pmin // len(p["lugares"]), pmax // len(p["lugares"])),
            )

        for k, puntaje in p.get("puntajes", {}).items():
            cur.execute(
                'INSERT INTO public."Usuario-Plan" ("Usuario_id", "Plan_id", "Confirmado", "Puntaje") VALUES (%s, %s, true, %s)',
                (quien[k], plan_id, puntaje),
            )

        cur.execute(
            """INSERT INTO public."Publicacion"
                   ("Id_Publicacion", "Id_Autor", "Id_Plan", "Texto", "Visibilidad", "Creada_En", "Aspecto")
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (pub_id, autor, plan_id, p["texto"] or None, p["visibilidad"],
             ahora - timedelta(minutes=p["hace_min"]), p.get("aspecto", "cuadrada")),
        )
        contadores["publicaciones"] += 1

        for orden, clave in enumerate(p["fotos"]):
            cur.execute(
                'INSERT INTO public."Publicacion_Foto" ("Id_Publicacion", "Orden", "Datos") VALUES (%s, %s, %s)',
                (pub_id, orden, Binary(fotos[clave])),
            )
            contadores["fotos"] += 1

        # Si la publicación es tuya, cada me gusta y comentario de otra persona
        # también deja su aviso en tu Inbox (como pasaría de verdad).
        es_mia = p["autor"] == "yo"

        for k in p["likes"]:
            momento = ahora - timedelta(minutes=max(1, p["hace_min"] - 5))
            cur.execute(
                'INSERT INTO public."Publicacion_Like" ("Id_Publicacion", "Id_Usuario", "Fecha") VALUES (%s, %s, %s)',
                (pub_id, quien[k], momento),
            )
            contadores["likes"] += 1
            if es_mia and k != "yo":
                cur.execute(
                    """INSERT INTO public."Publicacion_Notificacion"
                           ("Id_Usuario", "Id_Actor", "Tipo", "Id_Publicacion", "Creada_En")
                       VALUES (%s, %s, 'like', %s, %s)""",
                    (uid_yo, quien[k], pub_id, momento),
                )
                contadores["avisos"] += 1

        for k, texto, hace in p["comentarios"]:
            momento = ahora - timedelta(minutes=hace)
            cur.execute(
                """INSERT INTO public."Publicacion_Comentario" ("Id_Publicacion", "Id_Usuario", "Contenido", "Creado_En")
                   VALUES (%s, %s, %s, %s) RETURNING "Id_Comentario" """,
                (pub_id, quien[k], texto, momento),
            )
            comentario_id = cur.fetchone()[0]
            contadores["comentarios"] += 1
            if es_mia and k != "yo":
                cur.execute(
                    """INSERT INTO public."Publicacion_Notificacion"
                           ("Id_Usuario", "Id_Actor", "Tipo", "Id_Publicacion", "Id_Comentario", "Creada_En")
                       VALUES (%s, %s, 'comentario', %s, %s, %s)""",
                    (uid_yo, quien[k], pub_id, comentario_id, momento),
                )
                contadores["avisos"] += 1
    return contadores


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publicaciones de ejemplo para el feed de Social.")
    ap.add_argument("accion", choices=("crear", "borrar"))
    ap.add_argument("--mail", required=True, help="mail de TU usuario (recibe 2 publicaciones y 2 amistades)")
    args = ap.parse_args(argv)

    conexion = _conectar()
    try:
        cur = conexion.cursor()
        cur.execute('SELECT "Id_Usuario", "Nombre" FROM public."Usuarios" WHERE "Mail" = %s', (args.mail,))
        fila = cur.fetchone()
        if fila is None:
            raise SystemExit(f"No hay ningún usuario con el mail {args.mail}.")
        uid_yo = str(fila[0])

        # `crear` siempre empieza limpiando lo anterior: se puede repetir sin duplicar.
        antes = _borrar(cur, uid_yo)
        if args.accion == "borrar":
            conexion.commit()
            print(f"Borrado: {antes['planes']} planes (con sus publicaciones), "
                  f"{antes['usuarios']} usuarios de ejemplo, {antes['amistades']} amistades.")
            return 0

        contadores = _crear(cur, uid_yo)
        conexion.commit()
        print("Creado para", fila[1])
        print(", ".join(f"{k}: {v}" for k, v in contadores.items()))
        print("Para quitarlo:  python scripts/datos_demo_social.py borrar --mail", args.mail)
    except BaseException:
        conexion.rollback()
        print("Algo falló: se hizo rollback, la base quedó como estaba.")
        raise
    finally:
        from database import release_db_connection

        release_db_connection(conexion)
    return 0


if __name__ == "__main__":
    sys.exit(main())
