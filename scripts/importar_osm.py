"""Importa a la base los lugares de Montevideo desde OpenStreetMap.

Uso (desde la raíz del repo):

    python scripts/importar_osm.py --test                      # chequeos, sin red ni base
    python scripts/importar_osm.py --dry-run --bbox S,W,N,E    # solo cuenta, no escribe
    python scripts/importar_osm.py --dry-run                   # todo Montevideo, no escribe
    python scripts/importar_osm.py --dias domingo0             # importa de verdad

--dias dice cómo numera los días "horario_lugar" (lunes0: 0=lunes ... 6=domingo;
domingo0: 0=domingo ... 6=sábado). Si la tabla ya tiene horarios cargados a mano
con días 0..6 no hay forma de saberlo solo, y sin --dias el script no escribe.

Pocitos aprox.: --bbox -34.925,-56.165,-34.895,-56.130

Qué hace, en orden:
  1. Baja de Overpass (un pedido por grupo de tags) los lugares con nombre.
  2. Los convierte en filas de "Lugar" + sus Tipos + sus horarios.
  3. Baja los polígonos de barrios y le asigna Barrio a cada lugar.
  4. Escribe todo en UNA transacción, en lotes de 500. No pisa los lugares con
     Verificado = true (los corregidos a mano).

Los datos son de OpenStreetMap (licencia ODbL): Fuente = 'osm' los identifica.
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "AhoraQue-importador/1.0 (proyecto universitario; contacto: github.com/saprozapas/Ahora-Que)"
AREA_ISO = 'area["ISO3166-2"="UY-MO"]->.a;'
AREA_NOMBRE = 'area["name"="Montevideo"]["admin_level"="4"]->.a;'
# Caja que cubre el departamento: solo se usa para partir una consulta que falla.
BBOX_MONTEVIDEO = (-34.97, -56.45, -34.68, -55.95)

LOTE = 500
PAUSA_ENTRE_CONSULTAS = 5

# ---------------------------------------------------------------------------
# Tipos
#
# (tag, valor) de OSM -> nombre del Tipo. Cada nombre tiene que contener una
# palabra que reconozca ROLES en services/plan_reglas.py (así los lugares
# validan en los planes): el --test lo comprueba.
# ---------------------------------------------------------------------------

MAPEO = {
    ("amenity", "restaurant"): "Restaurante",
    ("amenity", "fast_food"): "Comida rápida",
    ("amenity", "cafe"): "Café",
    ("amenity", "bar"): "Bar",
    ("amenity", "pub"): "Pub",
    ("amenity", "ice_cream"): "Heladería",
    ("amenity", "nightclub"): "Boliche",
    ("amenity", "cinema"): "Cine",
    ("amenity", "theatre"): "Teatro",
    ("tourism", "museum"): "Museo",
    ("tourism", "gallery"): "Galería",
    ("leisure", "park"): "Parque",
    ("leisure", "garden"): "Parque",
    ("leisure", "playground"): "Plaza",
    ("leisure", "bowling_alley"): "Bowling",
    ("leisure", "escape_game"): "Escape room",
    ("leisure", "amusement_arcade"): "Arcade",
    ("place", "square"): "Plaza",
    ("natural", "beach"): "Playa",
}

NOMBRES_TIPO = sorted(set(MAPEO.values()))

# Un pedido a Overpass por grupo: si uno da timeout, no se pierde el resto.
GRUPOS = {
    "comida": [("amenity", "restaurant"), ("amenity", "fast_food"), ("amenity", "cafe"),
               ("amenity", "ice_cream")],
    "bares": [("amenity", "bar"), ("amenity", "pub"), ("amenity", "nightclub")],
    "cultura": [("amenity", "cinema"), ("amenity", "theatre"), ("tourism", "museum"),
                ("tourism", "gallery"), ("leisure", "bowling_alley"),
                ("leisure", "escape_game"), ("leisure", "amusement_arcade")],
    "parques": [("leisure", "park"), ("leisure", "garden"), ("leisure", "playground"),
                ("place", "square"), ("natural", "beach")],
}

TIPOS_APTOS = {"Restaurante", "Comida rápida", "Café", "Heladería", "Parque", "Plaza",
               "Playa", "Museo", "Cine", "Teatro", "Bowling", "Arcade"}
TIPOS_GRATIS = {"Parque", "Plaza", "Playa"}


# ---------------------------------------------------------------------------
# Overpass
# ---------------------------------------------------------------------------

class OverpassError(Exception):
    pass


def _overpass(consulta, espera_http=240):
    """POST a Overpass con reintentos (429/5xx y cortes de red)."""
    cuerpo = urllib.parse.urlencode({"data": consulta}).encode()
    ultimo = None
    for intento in range(1, 4):
        try:
            pedido = urllib.request.Request(
                OVERPASS_URL, data=cuerpo, headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(pedido, timeout=espera_http) as respuesta:
                return json.load(respuesta)
        except (OSError, json.JSONDecodeError) as e:   # URLError, timeouts y resets de conexión son OSError
            ultimo = e
            codigo = getattr(e, "code", None)
            # Un 400 es una consulta mal armada: reintentar no sirve.
            if codigo == 400:
                break
            if intento < 3:
                time.sleep(15 * intento)
    raise OverpassError(f"Overpass no respondió ({type(ultimo).__name__} {getattr(ultimo, 'code', '')})")


def _selectores(claves, filtro):
    """Una línea nwr por tag, juntando los valores: nwr["amenity"~"^(a|b)$"]["name"](...)."""
    por_tag = {}
    for tag, valor in claves:
        por_tag.setdefault(tag, []).append(valor)
    return "".join(
        f'  nwr["{tag}"~"^({"|".join(valores)})$"]["name"]{filtro};\n'
        for tag, valores in por_tag.items()
    )


def _filtro_espacial(bbox):
    if bbox:
        return "({},{},{},{})".format(*bbox)
    return "(area.a)"


def _area_para(bbox):
    """Con bbox no hace falta área. Sin bbox: UY-MO y, si no devuelve nada, el nombre."""
    if bbox:
        return ""
    for definicion in (AREA_ISO, AREA_NOMBRE):
        consulta = (f'[out:json][timeout:60];{definicion}'
                    'nwr["amenity"="cinema"](area.a);out count;')
        try:
            total = int(_overpass(consulta, 90)["elements"][0]["tags"]["total"])
        except (OverpassError, KeyError, IndexError, ValueError):
            total = 0
        if total > 0:
            return definicion
        time.sleep(PAUSA_ENTRE_CONSULTAS)
    raise OverpassError("No encontré el área de Montevideo en Overpass.")


def descargar_lugares(bbox, area):
    """Devuelve {Osm_Id: elemento} sin repetidos."""
    encontrados = {}
    for grupo, claves in GRUPOS.items():
        consulta = (f'[out:json][timeout:180];{area}(\n'
                    f'{_selectores(claves, _filtro_espacial(bbox))});\nout center tags;')
        try:
            elementos = _overpass(consulta)["elements"]
        except OverpassError:
            # ponytail: si el pedido grande falla se parte en 4 cuadrantes. Si
            # alguno también falla, el grupo queda incompleto y se avisa.
            print(f"  {grupo}: falló el pedido completo, pruebo por cuadrantes")
            elementos = []
            for cuadrante in _cuadrantes(bbox or BBOX_MONTEVIDEO):
                filtro = ("(area.a)" if not bbox else "") + "({},{},{},{})".format(*cuadrante)
                consulta = (f'[out:json][timeout:180];{area}(\n'
                            f'{_selectores(claves, filtro)});\nout center tags;')
                try:
                    elementos += _overpass(consulta)["elements"]
                except OverpassError as e:
                    print(f"  {grupo}: un cuadrante falló ({e}); el grupo queda incompleto")
                time.sleep(PAUSA_ENTRE_CONSULTAS)
        for el in elementos:
            encontrados[f"{el['type']}/{el['id']}"] = el
        print(f"  {grupo}: {len(elementos)} elementos")
        time.sleep(PAUSA_ENTRE_CONSULTAS)
    return encontrados


def _cuadrantes(bbox):
    s, w, n, e = bbox
    ms, mw = (s + n) / 2, (w + e) / 2
    return [(s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e)]


# ---------------------------------------------------------------------------
# Barrios
#
# Montevideo tiene ~62 barrios, pero OSM no los marca con un solo tag: algunos
# son boundary=neighborhood (relaciones), otros place=suburb o
# place=neighbourhood (relaciones y ways). Se bajan los tres niveles y, si un
# punto cae en varios, gana el nivel más "oficial" y, dentro del mismo nivel,
# el polígono más chico.
# ---------------------------------------------------------------------------

NIVELES_BARRIO = [
    ("boundary", "^neighborhood$"),
    ("place", "^suburb$"),
    ("place", "^(neighbourhood|quarter)$"),
]


def _anillos(vias):
    """Une ways (listas de (lon, lat)) por sus extremos en anillos cerrados.
    Devuelve (anillos, ok): ok es False si alguna vía quedó abierta."""
    vias = [list(v) for v in vias if len(v) >= 2]
    anillos = []
    ok = True
    while vias:
        actual = vias.pop()
        while actual[0] != actual[-1]:
            for i, v in enumerate(vias):
                if v[0] == actual[-1]:
                    actual = actual + v[1:]
                elif v[-1] == actual[-1]:
                    actual = actual + v[-2::-1]
                elif v[-1] == actual[0]:
                    actual = v[:-1] + actual
                elif v[0] == actual[0]:
                    actual = v[:0:-1] + actual
                else:
                    continue
                del vias[i]
                break
            else:
                actual = None
                break
        if actual is None:
            ok = False
        else:
            anillos.append(actual)
    return anillos, ok


def _puntos(geometria):
    return [(p["lon"], p["lat"]) for p in geometria]


def _poligono(el, nivel):
    """Elemento (way o relation con out geom) -> dict de barrio, o None."""
    nombre = (el.get("tags") or {}).get("name", "").strip()
    if not nombre:
        return None
    if el["type"] == "way":
        externas, internas = [_puntos(el.get("geometry") or [])], []
    else:
        externas, internas = [], []
        for m in el.get("members", []):
            if m.get("type") == "way" and m.get("geometry"):
                (internas if m.get("role") == "inner" else externas).append(_puntos(m["geometry"]))
    externas, ok = _anillos(externas)
    internas, _ = _anillos(internas)
    if not externas:
        return None
    xs = [x for anillo in externas for x, _ in anillo]
    ys = [y for anillo in externas for _, y in anillo]
    caja = (min(xs), min(ys), max(xs), max(ys))
    return {
        "nombre": nombre,
        "nivel": nivel,
        "caja": caja,
        "area_caja": (caja[2] - caja[0]) * (caja[3] - caja[1]),
        "externas": externas,
        "internas": internas,
        "completo": ok,
    }


def descargar_barrios(bbox, area):
    """Polígonos de barrios, ordenados por (nivel, tamaño). Devuelve (lista, conteos por nivel)."""
    poligonos, conteos = [], []
    filtro = _filtro_espacial(bbox)
    for nivel, (tag, patron) in enumerate(NIVELES_BARRIO):
        consulta = (f'[out:json][timeout:180];{area}(\n'
                    f'  rel["{tag}"~"{patron}"]["name"]{filtro};\n'
                    f'  way["{tag}"~"{patron}"]["name"]{filtro};\n'
                    f');\nout geom;')
        try:
            elementos = _overpass(consulta)["elements"]
        except OverpassError as e:
            print(f"  barrios nivel {nivel}: falló ({e}); se sigue sin ese nivel")
            elementos = []
        propios = [p for p in (_poligono(el, nivel) for el in elementos) if p]
        conteos.append(len(propios))
        poligonos += propios
        time.sleep(PAUSA_ENTRE_CONSULTAS)
    poligonos.sort(key=lambda p: (p["nivel"], p["area_caja"]))
    return poligonos, conteos


def punto_en_poligono(x, y, anillo):
    """Ray casting: el punto (x=lon, y=lat) ¿está dentro del anillo?"""
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i]
        xj, yj = anillo[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def barrio_de(lat, lon, poligonos):
    """Nombre del primer barrio (por prioridad) que contiene el punto, o None."""
    for p in poligonos:
        x0, y0, x1, y1 = p["caja"]
        if lon < x0 or lon > x1 or lat < y0 or lat > y1:
            continue
        if any(punto_en_poligono(lon, lat, a) for a in p["externas"]) and not any(
            punto_en_poligono(lon, lat, a) for a in p["internas"]
        ):
            return p["nombre"]
    return None


# ---------------------------------------------------------------------------
# Horarios (solo el formato simple: "Mo-Fr 09:00-18:00; Sa 10:00-14:00")
# ---------------------------------------------------------------------------

DIAS = {"Mo": 0, "Tu": 1, "We": 2, "Th": 3, "Fr": 4, "Sa": 5, "Su": 6}
_DIA = r"[A-Z][a-z]"
_HORA = r"\d{1,2}:\d{2}-\d{1,2}:\d{2}"
_REGLA = re.compile(
    rf"^(?P<dias>{_DIA}(?:-{_DIA})?(?:,{_DIA}(?:-{_DIA})?)*)\s+"
    rf"(?P<horas>{_HORA}(?:,\s*{_HORA})*)$"
)


def _hora_valida(texto):
    h, m = (int(x) for x in texto.split(":"))
    if m > 59 or h > 24 or (h == 24 and m != 0):
        return None
    return f"{h:02d}:{m:02d}"


def parsear_horario(texto):
    """"Mo-Fr 09:00-18:00; Sa 10:00-14:00" -> [(dia, "09:00", "18:00"), ...].

    Devuelve None si no se entiende completo (PH, sunrise, off, 24/7,
    comentarios...): mejor no guardar nada que guardar algo mal.
    Una regla posterior pisa a la anterior para los mismos días, como en OSM.
    """
    if not texto:
        return None
    por_dia = {}
    reglas = [r.strip() for r in texto.split(";") if r.strip()]
    if not reglas:
        return None
    for regla in reglas:
        m = _REGLA.match(regla)
        if not m:
            return None
        dias = []
        for trozo in m.group("dias").split(","):
            if "-" in trozo:
                a, b = trozo.split("-")
                if a not in DIAS or b not in DIAS:
                    return None
                i = DIAS[a]
                while True:  # "Fr-Mo" da la vuelta a la semana
                    dias.append(i)
                    if i == DIAS[b]:
                        break
                    i = (i + 1) % 7
            else:
                if trozo not in DIAS:
                    return None
                dias.append(DIAS[trozo])
        intervalos = []
        for par in re.split(r",\s*", m.group("horas")):
            ini, fin = par.split("-")
            ini, fin = _hora_valida(ini), _hora_valida(fin)
            if ini is None or fin is None:
                return None
            intervalos.append((ini, fin))
        for d in dias:
            por_dia[d] = intervalos
    # ponytail: si cierre < apertura el local pasa la medianoche; se guarda
    # tal cual y quien lea "horario_lugar" tiene que manejarlo.
    return [(d, a, c) for d in sorted(por_dia) for (a, c) in por_dia[d]]


# ---------------------------------------------------------------------------
# Tags -> fila de "Lugar"
# ---------------------------------------------------------------------------

def _coordenadas(el):
    if el["type"] == "node":
        return el.get("lat"), el.get("lon")
    centro = el.get("center") or {}
    return centro.get("lat"), centro.get("lon")


def fila_de(el):
    """Elemento de Overpass -> dict con los campos de "Lugar", o None si no sirve."""
    tags = el.get("tags") or {}
    nombre = (tags.get("name") or "").strip()
    if not nombre:
        return None
    lat, lon = _coordenadas(el)
    if lat is None or lon is None:
        return None
    tipos = sorted({t for (k, v), t in MAPEO.items() if tags.get(k) == v})
    if not tipos:
        return None

    calle = (tags.get("addr:street") or "").strip()
    numero = (tags.get("addr:housenumber") or "").strip()
    direccion = " ".join(x for x in (calle, numero) if x) if calle else None

    # Boliche nunca es apto; si no, un tipo "apto" gana sobre Bar/Pub (un
    # restaurante con barra no deja de ser apto); un Bar/Pub solo es false.
    conjunto = set(tipos)
    if "Boliche" in conjunto:
        apto = False
    elif conjunto & TIPOS_APTOS:
        apto = True
    elif conjunto & {"Bar", "Pub"}:
        apto = False
    else:
        apto = None

    return {
        "osm_id": f"{el['type']}/{el['id']}",
        "nombre": nombre,
        "lat": lat,
        "lon": lon,
        "direccion": direccion,
        "tipos": tipos,
        "apto": apto,
        "nivel": 0 if conjunto <= TIPOS_GRATIS else None,
        "vegano": True if tags.get("diet:vegan") in ("yes", "only") else None,
        "celiaco": True if tags.get("diet:gluten_free") == "yes" else None,
        "barrio": None,
        "horario": parsear_horario(tags.get("opening_hours")),
        "_addr_barrio": (tags.get("addr:suburb") or tags.get("addr:neighbourhood") or "").strip() or None,
    }


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def _norm(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower().strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _conectar():
    from dotenv import load_dotenv

    load_dotenv(os.path.join(RAIZ, ".env"))
    from database import get_db_connection

    return get_db_connection()


def _liberar(conexion):
    from database import release_db_connection

    release_db_connection(conexion)


def chequear_precondicion(cur):
    """Devuelve la lista de problemas (vacía = todo en orden)."""
    cur.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'Lugar'"""
    )
    columnas = {f[0] for f in cur.fetchall()}
    problemas = [f'a "Lugar" le falta la columna {c}'
                 for c in ("Osm_Id", "Fuente", "Verificado", "Barrio") if c not in columnas]
    if "Osm_Id" in columnas:
        cur.execute(
            """SELECT 1
               FROM pg_index i
               JOIN pg_class c ON c.oid = i.indrelid
               JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (i.indkey)
               WHERE c.oid = 'public."Lugar"'::regclass AND a.attname = 'Osm_Id'
                 AND i.indisunique AND i.indnkeyatts = 1 AND i.indpred IS NULL"""
        )
        if cur.fetchone() is None:
            problemas.append('"Osm_Id" no tiene un UNIQUE (hace falta para ON CONFLICT)')
    return problemas


MODOS_DIAS = ("lunes0", "domingo0", "iso")


def numero_dia(dia, modo):
    """dia: 0=lunes ... 6=domingo (como lo parsea parsear_horario)."""
    return {"lunes0": dia, "domingo0": (dia + 1) % 7, "iso": dia + 1}[modo]


def convencion_dias(cur, forzado=None):
    """(modo, descripción). modo es None si no se puede saber.

    Sin filas ajenas a esta importación: lunes0. Con días 1..7: iso (1=lunes).
    Con días 0..6 es ambiguo (¿0=lunes o 0=domingo?): hay que pasar --dias.
    """
    if forzado:
        return forzado, f"forzado con --dias {forzado}"
    cur.execute(
        """SELECT h.dia_semana, COUNT(*)
           FROM public.horario_lugar h
           JOIN public."Lugar" l ON l."Id_Lugar" = h.lugar_id
           WHERE l."Fuente" IS DISTINCT FROM 'osm'
           GROUP BY 1 ORDER BY 1"""
    )
    filas = cur.fetchall()
    if not filas:
        return "lunes0", "horario_lugar sin filas previas: 0=lunes ... 6=domingo"
    valores = [f[0] for f in filas]
    resumen_filas = ", ".join(f"{v}:{n}" for v, n in filas)
    if min(valores) >= 1 and max(valores) == 7:
        return "iso", f"filas previas con días 1..7 ({resumen_filas}): 1=lunes ... 7=domingo"
    return None, (f"filas previas con días {min(valores)}..{max(valores)} ({resumen_filas}): "
                  "no se sabe si 0=lunes o 0=domingo; pasá --dias lunes0 o --dias domingo0")


def asegurar_tipos(cur):
    """Crea los Tipos que falten (reusando los equivalentes sin tildes/mayúsculas)
    y devuelve {nombre: Id_Tipo}."""
    from psycopg2.extras import execute_values

    cur.execute('SELECT "Id_Tipo", "Nombre" FROM public."Tipo"')
    existentes = {_norm(n): i for i, n in cur.fetchall()}
    ids = {n: existentes[_norm(n)] for n in NOMBRES_TIPO if _norm(n) in existentes}
    faltan = [n for n in NOMBRES_TIPO if n not in ids]
    if faltan:
        cur.execute(
            """SELECT column_default FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'Tipo' AND column_name = 'Id_Tipo'"""
        )
        con_default = cur.fetchone()[0] is not None
        if con_default:
            execute_values(
                cur,
                'INSERT INTO public."Tipo" ("Nombre") VALUES %s ON CONFLICT ("Nombre") DO NOTHING',
                [(n,) for n in faltan],
            )
        else:
            cur.execute('SELECT COALESCE(MAX("Id_Tipo"), 0) FROM public."Tipo"')
            siguiente = cur.fetchone()[0] + 1
            execute_values(
                cur,
                'INSERT INTO public."Tipo" ("Id_Tipo", "Nombre") VALUES %s ON CONFLICT ("Nombre") DO NOTHING',
                [(siguiente + k, n) for k, n in enumerate(faltan)],
            )
        cur.execute('SELECT "Id_Tipo", "Nombre" FROM public."Tipo" WHERE "Nombre" = ANY(%s)', (faltan,))
        for i, n in cur.fetchall():
            ids[n] = i
    return ids


def escribir(filas, modo_dias, cur):
    """Todo el upsert, en lotes de LOTE. Devuelve contadores. No hace commit."""
    from psycopg2.extras import execute_values

    ids_tipo = asegurar_tipos(cur)
    por_osm = {f["osm_id"]: f for f in filas}
    devueltos = []   # (Id_Lugar, Osm_Id, insertado)

    sql_lugar = """
        INSERT INTO public."Lugar"
            ("Id_Lugar", "Nombre", "Lat", "Long", "Osm_Id", "Fuente", "Verificado",
             "Direccion", "Apto_Menores", "Nivel_Precio", "Opcion_Vegana", "Opcion_Celiacos", "Barrio")
        VALUES %s
        ON CONFLICT ("Osm_Id") DO UPDATE SET
            "Nombre" = EXCLUDED."Nombre", "Lat" = EXCLUDED."Lat", "Long" = EXCLUDED."Long",
            "Direccion" = EXCLUDED."Direccion", "Apto_Menores" = EXCLUDED."Apto_Menores",
            "Nivel_Precio" = EXCLUDED."Nivel_Precio", "Opcion_Vegana" = EXCLUDED."Opcion_Vegana",
            "Opcion_Celiacos" = EXCLUDED."Opcion_Celiacos", "Barrio" = EXCLUDED."Barrio"
        WHERE public."Lugar"."Verificado" = false
        RETURNING "Id_Lugar", "Osm_Id", (xmax = 0)"""
    plantilla = "(gen_random_uuid(), %s, %s, %s, %s, 'osm', false, %s, %s, %s, %s, %s, %s)"
    for i in range(0, len(filas), LOTE):
        lote = [
            (f["nombre"], f["lat"], f["lon"], f["osm_id"], f["direccion"], f["apto"],
             f["nivel"], f["vegano"], f["celiaco"], f["barrio"])
            for f in filas[i:i + LOTE]
        ]
        devueltos += execute_values(cur, sql_lugar, lote, template=plantilla,
                                    page_size=LOTE, fetch=True)

    insertados = sum(1 for _, _, nuevo in devueltos if nuevo)
    actualizados = len(devueltos) - insertados

    pares = [(str(id_lugar), ids_tipo[t]) for id_lugar, osm, _ in devueltos
             for t in por_osm[osm]["tipos"]]
    for i in range(0, len(pares), LOTE):
        execute_values(
            cur,
            'INSERT INTO public."Lugar_Tipo" ("Lugar_id", "Tipo_id") VALUES %s ON CONFLICT DO NOTHING',
            pares[i:i + LOTE], template="(%s::uuid, %s)", page_size=LOTE,
        )

    con_horario = [(str(id_lugar), por_osm[osm]["horario"]) for id_lugar, osm, _ in devueltos
                   if por_osm[osm]["horario"]]
    for i in range(0, len(con_horario), LOTE):
        trozo = con_horario[i:i + LOTE]
        cur.execute('DELETE FROM public.horario_lugar WHERE lugar_id = ANY(%s::uuid[])',
                    ([lid for lid, _ in trozo],))
        execute_values(
            cur,
            """INSERT INTO public.horario_lugar (id, lugar_id, dia_semana, hora_apertura, hora_cierre)
               VALUES %s""",
            [(lid, numero_dia(dia, modo_dias), ini, fin) for lid, hs in trozo for dia, ini, fin in hs],
            template="(gen_random_uuid(), %s::uuid, %s, %s::time, %s::time)", page_size=LOTE,
        )

    return {
        "insertados": insertados,
        "actualizados": actualizados,
        "saltados_verificados": len(filas) - len(devueltos),
        "horarios_guardados": len(con_horario),
    }


# ---------------------------------------------------------------------------
# Resumen (solo conteos: nunca se imprimen filas)
# ---------------------------------------------------------------------------

def resumen(filas):
    por_tipo = Counter(t for f in filas for t in f["tipos"])
    print(f"\nLugares a importar: {len(filas)}")
    print("Por Tipo:", ", ".join(f"{t} {n}" for t, n in por_tipo.most_common()))
    total = max(len(filas), 1)

    def pct(n):
        return f"{n} ({100 * n // total}%)"

    print("Con dirección:", pct(sum(1 for f in filas if f["direccion"])))
    print("Con horario:  ", pct(sum(1 for f in filas if f["horario"])))
    print("Con barrio:   ", pct(sum(1 for f in filas if f["barrio"])))
    print("Veganos:", sum(1 for f in filas if f["vegano"]),
          "| Celíacos:", sum(1 for f in filas if f["celiaco"]))
    barrios = Counter(f["barrio"] for f in filas if f["barrio"])
    print("Top 10 barrios:", ", ".join(f"{b} {n}" for b, n in barrios.most_common(10)) or "(ninguno)")


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def _parsear_bbox(texto):
    try:
        s, w, n, e = (float(x) for x in texto.split(","))
    except ValueError:
        raise SystemExit("--bbox tiene que ser S,W,N,E (cuatro números separados por coma).")
    if not (s < n and w < e):
        raise SystemExit("--bbox: hace falta S < N y W < E.")
    return (s, w, n, e)


def construir(bbox):
    area = _area_para(bbox)
    print("Bajando lugares de Overpass...")
    elementos = descargar_lugares(bbox, area)
    filas, sin_nombre = [], 0
    for el in elementos.values():
        fila = fila_de(el)
        if fila:
            filas.append(fila)
        else:
            sin_nombre += 1
    print(f"Elementos: {len(elementos)} | descartados (sin nombre, sin coordenadas o sin tipo): {sin_nombre}")

    print("Bajando polígonos de barrios...")
    poligonos, conteos = descargar_barrios(bbox, area)
    incompletos = sum(1 for p in poligonos if not p["completo"])
    print(f"Polígonos de barrio: {len(poligonos)} "
          f"(boundary=neighborhood {conteos[0]}, place=suburb {conteos[1]}, "
          f"place=neighbourhood/quarter {conteos[2]}; anillos incompletos {incompletos})")
    for f in filas:
        f["barrio"] = barrio_de(f["lat"], f["lon"], poligonos) if poligonos else f["_addr_barrio"]
    return filas, sin_nombre


def main(argv=None):
    ap = argparse.ArgumentParser(description="Importa lugares de Montevideo desde OpenStreetMap.")
    ap.add_argument("--dry-run", action="store_true", help="no escribe: solo cuenta")
    ap.add_argument("--bbox", help="S,W,N,E: limita la descarga a una zona (para probar)")
    ap.add_argument("--dias", choices=("lunes0", "domingo0"),
                    help="cómo numera los días horario_lugar (ver arriba); obligatorio si la tabla ya tiene días 0..6")
    ap.add_argument("--test", action="store_true", help="corre los chequeos internos (sin red ni base)")
    args = ap.parse_args(argv)

    if args.test:
        _autotest()
        print("Autotest OK")
        return 0

    inicio = time.time()
    bbox = _parsear_bbox(args.bbox) if args.bbox else None
    filas, sin_nombre = construir(bbox)   # se baja TODO antes de abrir la base
    resumen(filas)

    if args.dry_run:
        try:
            conexion = _conectar()
        except Exception as e:
            print(f"\n[dry-run] sin conexión a la base ({type(e).__name__}): "
                  "se saltean los chequeos de tablas y de días.")
        else:
            try:
                cur = conexion.cursor()
                problemas = chequear_precondicion(cur)
                print("\n[dry-run] precondición:", "OK" if not problemas else "; ".join(problemas))
                if not problemas:
                    print("[dry-run] días:", convencion_dias(cur, args.dias)[1])
            finally:
                _liberar(conexion)
        print(f"\nDry-run: no se escribió nada. Tardó {time.time() - inicio:.0f} s.")
        return 0

    conexion = _conectar()
    try:
        cur = conexion.cursor()
        problemas = chequear_precondicion(cur)
        if problemas:
            raise SystemExit("Falta preparar la base: " + "; ".join(problemas))
        modo, descripcion = convencion_dias(cur, args.dias)
        print("Días:", descripcion)
        if modo is None:
            raise SystemExit("No escribo nada: falta --dias.")
        contadores = escribir(filas, modo, cur)
        conexion.commit()
    except BaseException:
        conexion.rollback()
        print("Algo falló: se hizo rollback, la base quedó como estaba.")
        raise
    finally:
        _liberar(conexion)

    print(f"\nInsertados {contadores['insertados']} | actualizados {contadores['actualizados']} | "
          f"saltados: {sin_nombre} sin nombre/coordenadas/tipo + {contadores['saltados_verificados']} "
          f"verificados | horarios guardados {contadores['horarios_guardados']} | "
          f"tardó {time.time() - inicio:.0f} s")
    return 0


# ---------------------------------------------------------------------------
# Autotest: sin red ni base
# ---------------------------------------------------------------------------

def _autotest():
    # Tags -> fila
    vegano = fila_de({
        "type": "node", "id": 1, "lat": -34.9, "lon": -56.15,
        "tags": {"name": "Verde", "amenity": "restaurant", "diet:vegan": "yes",
                 "addr:street": "Benito Blanco", "addr:housenumber": "1234",
                 "opening_hours": "Mo-Fr 09:00-18:00; Sa 10:00-14:00"},
    })
    assert vegano["osm_id"] == "node/1" and vegano["tipos"] == ["Restaurante"]
    assert vegano["vegano"] is True and vegano["celiaco"] is None
    assert vegano["apto"] is True and vegano["nivel"] is None
    assert vegano["direccion"] == "Benito Blanco 1234"
    assert len(vegano["horario"]) == 6

    boliche = fila_de({"type": "way", "id": 2, "center": {"lat": -34.91, "lon": -56.16},
                       "tags": {"name": "Noche", "amenity": "nightclub"}})
    assert boliche["osm_id"] == "way/2" and boliche["apto"] is False
    assert boliche["direccion"] is None and boliche["vegano"] is None and boliche["nivel"] is None

    plaza = fila_de({"type": "relation", "id": 3, "center": {"lat": -34.9, "lon": -56.2},
                     "tags": {"name": "Plaza Uno", "place": "square"}})
    assert plaza["tipos"] == ["Plaza"] and plaza["nivel"] == 0 and plaza["apto"] is True

    bar = fila_de({"type": "node", "id": 4, "lat": -34.9, "lon": -56.1,
                   "tags": {"name": "El Bar", "amenity": "bar"}})
    assert bar["apto"] is False                     # solo Bar/Pub: false
    resto_bar = fila_de({"type": "node", "id": 5, "lat": -34.9, "lon": -56.1,
                         "tags": {"name": "Mixto", "amenity": "restaurant", "leisure": "garden"}})
    assert resto_bar["apto"] is True and resto_bar["nivel"] is None   # Restaurante + Parque
    discoteca_resto = fila_de({"type": "node", "id": 6, "lat": -34.9, "lon": -56.1,
                               "tags": {"name": "Ambos", "amenity": "nightclub", "tourism": "gallery"}})
    assert discoteca_resto["apto"] is False         # Boliche gana siempre
    assert fila_de({"type": "node", "id": 7, "lat": 1, "lon": 1, "tags": {"amenity": "cafe"}}) is None
    assert fila_de({"type": "node", "id": 8, "lat": 1, "lon": 1,
                    "tags": {"name": "X", "shop": "bakery"}}) is None
    celiaco = fila_de({"type": "node", "id": 9, "lat": 1, "lon": 1,
                       "tags": {"name": "Sin TACC", "amenity": "cafe", "diet:gluten_free": "yes"}})
    assert celiaco["celiaco"] is True and celiaco["vegano"] is None

    # Todos los nombres de Tipo tienen rol en plan_reglas, y todo el mapeo está en algún grupo
    from services.plan_reglas import _roles_de_texto

    for nombre in NOMBRES_TIPO:
        assert _roles_de_texto(nombre), f"el Tipo {nombre!r} no tiene rol en plan_reglas.ROLES"
    en_grupos = {c for claves in GRUPOS.values() for c in claves}
    assert en_grupos == set(MAPEO), "GRUPOS y MAPEO no coinciden"

    # Horarios
    assert parsear_horario("Mo-Fr 09:00-18:00; Sa 10:00-14:00") == (
        [(d, "09:00", "18:00") for d in range(5)] + [(5, "10:00", "14:00")]
    )
    assert parsear_horario("Mo,We 09:00-12:00,14:00-18:00") == [
        (0, "09:00", "12:00"), (0, "14:00", "18:00"), (2, "09:00", "12:00"), (2, "14:00", "18:00")]
    assert parsear_horario("Fr-Mo 10:00-02:00") == [      # da la vuelta a la semana y cruza medianoche
        (0, "10:00", "02:00"), (4, "10:00", "02:00"), (5, "10:00", "02:00"), (6, "10:00", "02:00")]
    assert parsear_horario("Mo-Fr 09:00-18:00; Mo 10:00-12:00")[0] == (0, "10:00", "12:00")  # pisa
    for malo in ("Mo-Fr 09:00-18:00; PH off", "24/7", "sunrise-sunset", "Mo off",
                 "Mo-Fr 09:00-18:00 \"con cita\"", "09:00-18:00", "Xx 09:00-18:00", "", None,
                 "Mo 25:00-26:00"):
        assert parsear_horario(malo) is None, malo

    # Punto en polígono
    cuadrado = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    agujero = [(4, 4), (6, 4), (6, 6), (4, 6), (4, 4)]
    assert punto_en_poligono(5, 5, cuadrado) and not punto_en_poligono(15, 5, cuadrado)
    barrio = {"nombre": "Q", "nivel": 0, "caja": (0, 0, 10, 10), "area_caja": 100,
              "externas": [cuadrado], "internas": [agujero], "completo": True}
    assert barrio_de(2, 2, [barrio]) == "Q"
    assert barrio_de(5, 5, [barrio]) is None       # dentro del agujero
    assert barrio_de(20, 20, [barrio]) is None     # afuera
    chico = dict(barrio, nombre="chico", nivel=0, area_caja=10)
    assert barrio_de(2, 2, sorted([barrio, chico], key=lambda p: (p["nivel"], p["area_caja"]))) == "chico"

    # Unir ways en un anillo (una de ellas dada vuelta)
    anillos, ok = _anillos([[(0, 0), (10, 0), (10, 10)], [(0, 0), (0, 10), (10, 10)]])
    assert ok and len(anillos) == 1 and anillos[0][0] == anillos[0][-1] and len(anillos[0]) == 5
    assert punto_en_poligono(5, 5, anillos[0])
    _, ok = _anillos([[(0, 0), (10, 0), (10, 10)]])
    assert not ok                                   # no cierra

    # Consultas y parámetros
    assert '["amenity"~"^(restaurant|cafe)$"]["name"](area.a);' in _selectores(
        [("amenity", "restaurant"), ("amenity", "cafe")], "(area.a)")
    assert _parsear_bbox("-34.925,-56.165,-34.895,-56.130") == (-34.925, -56.165, -34.895, -56.13)
    assert _norm("Heladería") == _norm("heladeria")

    # Numeración de días: lunes=0 en el parser; cada modo lo traduce
    assert [numero_dia(d, "lunes0") for d in (0, 6)] == [0, 6]
    assert [numero_dia(d, "domingo0") for d in (0, 5, 6)] == [1, 6, 0]   # lunes=1, sábado=6, domingo=0
    assert [numero_dia(d, "iso") for d in (0, 6)] == [1, 7]


if __name__ == "__main__":
    sys.exit(main())
