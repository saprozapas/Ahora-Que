"""Carga a la base los lugares de un JSON (el que sale de revisar la tabla de
lugares: lugares_barrios_precios.json).

Cada elemento tiene: nombre, tipos, barrio, direccion, apto, precio, vegano,
celiaco, horario, osm, lat, lon.

Uso (desde la raíz del repo; escribe en la base del .env, que es la compartida):

    python scripts/cargar_lugares_json.py RUTA.json --dry-run    # solo cuenta
    python scripts/cargar_lugares_json.py RUTA.json              # carga de verdad

Qué hace:
  * Lugares que YA están en la base (se reconocen por su id de OpenStreetMap):
    solo se completan los campos que están VACÍOS (barrio, dirección y precio
    "Gratis" = categoría 0). Nunca se pisa un dato que ya existe ni un lugar
    verificado a mano.
  * Lugares NUEVOS (sin id de OpenStreetMap): se insertan con Fuente = 'manual' y
    Verificado = false, con sus tipos y su horario si lo tienen. Se saltea el que
    ya está en la base (mismo nombre a menos de 150 metros).
  * Precio: solo se carga lo que el JSON dice con certeza ("Gratis" = 0, y los
    parques, plazas y playas, que son gratis). Las categorías 1 a 5 no se
    inventan: el lugar queda sin dato (NULL) hasta que se sepa.
  * Antes de escribir copia la tabla "Lugar" al esquema backup (para poder
    volver atrás) y todo va en UNA transacción, con rollback si algo falla.
"""

import argparse
import json
import math
import os
import sys
import time
import unicodedata
import uuid
from collections import Counter, defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

import importar_osm as osm  # reutiliza las reglas de tipos, apto menores y horarios  # noqa: E402

LOTE = 500
METROS_DUPLICADO = 150

DIAS_ES_A_EN = {"Lun": "Mo", "Mar": "Tu", "Mié": "We", "Jue": "Th", "Vie": "Fr", "Sáb": "Sa", "Dom": "Su"}


def _norm(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower().strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _metros(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _si(valor):
    return True if valor == "Sí" else None


def _tipos(texto):
    return [t.strip() for t in (texto or "").split(",") if t.strip()]


def _apto(tipos):
    """Mismas reglas que scripts/importar_osm.py."""
    conjunto = set(tipos)
    if "Boliche" in conjunto:
        return False
    if conjunto & osm.TIPOS_APTOS:
        return True
    if conjunto & {"Bar", "Pub"}:
        return False
    return None


def _horario(texto):
    """"Lun-Vie 09:00-18:00; Sáb 10:00-14:00" -> [(dia, "09:00", "18:00")] o None.
    Si algún día tiene más de un tramo (horario cortado) no se guarda ninguno:
    la tabla admite un solo intervalo por día."""
    if not texto:
        return None
    ingles = texto
    for es, en in DIAS_ES_A_EN.items():
        ingles = ingles.replace(es, en)
    parseado = osm.parsear_horario(ingles)
    if not parseado or len({d for d, _, _ in parseado}) != len(parseado):
        return None
    return parseado


def _nivel(elemento, tipos):
    """Solo lo seguro: "Gratis" en el JSON, o un lugar que es solo parque/plaza/playa."""
    if elemento.get("precio") == "Gratis":
        return 0
    if tipos and set(_norm(t) for t in tipos) <= {_norm(t) for t in osm.TIPOS_GRATIS}:
        return 0
    return None


def planear(lista, db):
    """Decide qué hacer con cada elemento. db: {id: dict} con los lugares de la base."""
    por_osm = {d["osm"]: d for d in db.values() if d["osm"]}
    por_nombre = defaultdict(list)
    for d in db.values():
        por_nombre[_norm(d["nombre"])].append((d["lat"], d["lon"]))

    completar, nuevos, saltados = [], [], []
    for e in lista:
        tipos = _tipos(e["tipos"])
        osm_id = (e.get("osm") or "").strip()
        if osm_id and osm_id in por_osm:
            actual = por_osm[osm_id]
            if actual["verificado"]:
                continue
            cambios = {}
            if e["barrio"] and actual["barrio"] is None:
                cambios["barrio"] = e["barrio"]
            if e["direccion"] and actual["direccion"] is None:
                cambios["direccion"] = e["direccion"]
            nivel = _nivel(e, tipos)
            if nivel is not None and actual["nivel"] is None:
                cambios["nivel"] = nivel
            if cambios:
                completar.append((actual["id"], cambios))
            continue

        # Nuevo. ¿Ya está (mismo nombre a menos de 150 m)?
        clave = _norm(e["nombre"])
        lat, lon = float(e["lat"]), float(e["lon"])
        if any(_metros(lat, lon, la, lo) < METROS_DUPLICADO for la, lo in por_nombre.get(clave, [])):
            saltados.append(e)
            continue
        por_nombre[clave].append((lat, lon))
        nuevos.append(e)
    return completar, nuevos, saltados


def main(argv=None):
    ap = argparse.ArgumentParser(description="Carga lugares desde un JSON.")
    ap.add_argument("json")
    ap.add_argument("--dry-run", action="store_true", help="no escribe: solo cuenta")
    args = ap.parse_args(argv)

    inicio = time.time()
    lista = json.load(open(args.json, encoding="utf-8"))
    print(f"JSON: {len(lista)} lugares")

    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
    from database import get_db_connection, release_db_connection
    from psycopg2.extras import execute_values

    conexion = get_db_connection()
    try:
        cur = conexion.cursor()
        problemas = osm.chequear_precondicion(cur)
        if problemas:
            raise SystemExit("Falta preparar la base: " + "; ".join(problemas))

        cur.execute(
            'SELECT "Id_Lugar", "Osm_Id", "Nombre", "Lat", "Long", "Barrio", "Direccion", "Nivel_Precio", "Verificado" '
            'FROM public."Lugar"'
        )
        db = {
            str(f[0]): {"id": str(f[0]), "osm": f[1], "nombre": f[2], "lat": float(f[3] or 0), "lon": float(f[4] or 0),
                        "barrio": f[5], "direccion": f[6], "nivel": f[7], "verificado": f[8]}
            for f in cur.fetchall()
        }
        print(f"Base: {len(db)} lugares")

        completar, nuevos, saltados = planear(lista, db)

        campos = Counter(k for _, c in completar for k in c)
        print(f"\nYa estaban: se completan vacíos en {len(completar)} lugares "
              f"(barrio {campos['barrio']}, dirección {campos['direccion']}, precio gratis {campos['nivel']}).")
        print(f"Nuevos para cargar: {len(nuevos)} | saltados por duplicados: {len(saltados)}")
        print("Nuevos por tipo:", dict(Counter(e["tipos"] for e in nuevos).most_common(15)))
        print("Nuevos con barrio:", sum(1 for e in nuevos if e["barrio"]),
              "| con horario:", sum(1 for e in nuevos if _horario(e["horario"])),
              "| con precio gratis (0):", sum(1 for e in nuevos if _nivel(e, _tipos(e["tipos"])) == 0),
              "| sin precio (NULL):", sum(1 for e in nuevos if _nivel(e, _tipos(e["tipos"])) is None))
        if saltados:
            print("Ejemplos de saltados:", [(e["nombre"], e["barrio"]) for e in saltados[:5]])

        if args.dry_run:
            print(f"\nDry-run: no se escribió nada. Tardó {time.time() - inicio:.0f} s.")
            return 0

        # --- Respaldo y carga, en una sola transacción ---------------------------------
        sufijo = time.strftime("%Y%m%d")
        cur.execute(f'CREATE TABLE IF NOT EXISTS backup."Lugar_antes_carga_json_{sufijo}" AS TABLE public."Lugar"')

        # Los tipos se reconocen sin importar mayúsculas ni tildes ("cafe" = "Café").
        cur.execute('SELECT "Id_Tipo", "Nombre" FROM public."Tipo"')
        ids_tipo = {_norm(n): i for i, n in cur.fetchall()}
        faltan = sorted({t for e in nuevos for t in _tipos(e["tipos"]) if _norm(t) not in ids_tipo})
        if faltan:
            execute_values(cur, 'INSERT INTO public."Tipo" ("Nombre") VALUES %s ON CONFLICT ("Nombre") DO NOTHING',
                           [(t,) for t in faltan])
            cur.execute('SELECT "Id_Tipo", "Nombre" FROM public."Tipo"')
            ids_tipo = {_norm(n): i for i, n in cur.fetchall()}

        # 1) completar vacíos de los que ya estaban
        for i in range(0, len(completar), LOTE):
            lote = [(uid, c.get("barrio"), c.get("direccion"), c.get("nivel")) for uid, c in completar[i:i + LOTE]]
            execute_values(
                cur,
                """UPDATE public."Lugar" l
                   SET "Barrio" = COALESCE(l."Barrio", v.barrio),
                       "Direccion" = COALESCE(l."Direccion", v.direccion),
                       "Nivel_Precio" = COALESCE(l."Nivel_Precio", v.nivel)
                   FROM (VALUES %s) AS v(id, barrio, direccion, nivel)
                   WHERE l."Id_Lugar" = v.id::uuid AND NOT l."Verificado" """,
                lote, template="(%s, %s, %s, %s::int)", page_size=LOTE,
            )

        # 2) insertar los nuevos
        filas, pares, horarios = [], [], []
        for e in nuevos:
            lid = str(uuid.uuid4())
            tipos = _tipos(e["tipos"])
            filas.append((
                lid, e["nombre"], float(e["lat"]), float(e["lon"]), (e.get("osm") or None),
                "osm" if e.get("osm") else "manual", e["direccion"] or None, _apto(tipos),
                _nivel(e, tipos), _si(e["vegano"]), _si(e["celiaco"]), e["barrio"] or None,
            ))
            pares += [(lid, ids_tipo[_norm(t)]) for t in tipos]
            h = _horario(e["horario"])
            if h:
                horarios += [(lid, osm.numero_dia(d, "domingo0"), a, c) for d, a, c in h]

        for i in range(0, len(filas), LOTE):
            execute_values(
                cur,
                """INSERT INTO public."Lugar"
                       ("Id_Lugar", "Nombre", "Lat", "Long", "Osm_Id", "Fuente", "Verificado",
                        "Direccion", "Apto_Menores", "Nivel_Precio", "Opcion_Vegana", "Opcion_Celiacos", "Barrio")
                   VALUES %s""",
                [f[:6] + (False,) + f[6:] for f in filas[i:i + LOTE]],
                template="(%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", page_size=LOTE,
            )
        for i in range(0, len(pares), LOTE):
            execute_values(cur, 'INSERT INTO public."Lugar_Tipo" ("Lugar_id", "Tipo_id") VALUES %s ON CONFLICT DO NOTHING',
                           pares[i:i + LOTE], template="(%s::uuid, %s)", page_size=LOTE)
        for i in range(0, len(horarios), LOTE):
            execute_values(
                cur,
                """INSERT INTO public.horario_lugar (id, lugar_id, dia_semana, hora_apertura, hora_cierre) VALUES %s""",
                horarios[i:i + LOTE], template="(gen_random_uuid(), %s::uuid, %s, %s::time, %s::time)", page_size=LOTE,
            )
        conexion.commit()
        print(f"\nListo: {len(filas)} lugares nuevos, {len(pares)} tipos, {len(horarios)} horarios, "
              f"{len(completar)} lugares completados. Respaldo: backup.\"Lugar_antes_carga_json_{sufijo}\". "
              f"Tardó {time.time() - inicio:.0f} s.")
    except BaseException:
        conexion.rollback()
        print("Algo falló: se hizo rollback, la base quedó como estaba.")
        raise
    finally:
        release_db_connection(conexion)
    return 0


if __name__ == "__main__":
    sys.exit(main())
