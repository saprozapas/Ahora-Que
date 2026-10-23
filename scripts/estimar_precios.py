"""Estima la categoría de precio (0 a 5) de los lugares que todavía no la tienen.

Categorías (por persona, en una salida típica):

    0  Gratis        1  $  100 a 300     2  $$  300 a 600
    3  $$$  600 a 1000                   4  $$$$  1000 a 2000
    5  $$$$$  más de 2000

IMPORTANTE: son ESTIMACIONES. No hay una fuente pública que dé el precio de
cada lugar de Montevideo (se probó con búsquedas web y fichas de reseñas: casi
nunca traen precios). Por eso cada estimación guarda DE DÓNDE SALIÓ en
"Lugar"."Precio_Origen" para poder corregirla o recalcularla:

    marca    cadena o lugar conocido (McDonald's, Grido, Nippon...)    confianza alta
    cocina   etiqueta "cuisine" de OpenStreetMap (sushi, steak_house...)  media
    nombre   palabras del nombre (parrilla, pizzería, cervecería...)     media
    tipo     lo normal para ese tipo de lugar (restaurante = 3, etc.)     baja
    manual   lo puso una persona: este script NUNCA lo toca

Uso (desde la raíz del repo):

    python scripts/estimar_precios.py --revisar      # genera datos/revision_precios.html y .csv, no escribe en la base
    python scripts/estimar_precios.py --aplicar      # guarda las estimaciones (respaldo previo, una transacción)

Solo completa lugares SIN categoría, o recalcula los que ya tenían una estimación
de este script. Nunca pisa un precio "manual", uno de un lugar verificado ni los
gratis (0) que ya estaban.
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

import importar_osm as osm  # noqa: E402  (usa su cliente de Overpass)

DATOS = os.path.join(RAIZ, "datos")

# ---------------------------------------------------------------------------
# Referencias de precios (pesos uruguayos, por persona). Salen de precios
# típicos de Montevideo y de lo poco que dan las guías públicas:
#   * Big Mac solo: ~$310 (Índice Big Mac, julio 2025) -> combo de $500 a $600.
#   * Chivito completo en La Pasiva: $320 a $500 en una guía vieja; hoy más.
#   * Una comida completa con asado en Pocitos o Cordón: $800 a $1400.
#   * Parrilla del Mercado del Puerto: más cara que la de barrio.
# ---------------------------------------------------------------------------

# nombre (sin tildes ni mayúsculas, "contiene") -> (categoría, por qué)
CADENAS = {
    "mcdonald": (2, "combo de $500 a $600"),
    "mccafe": (2, "café y algo dulce, $300 a $500"),
    "burger king": (2, "combo de $500 a $650"),
    "subway": (2, "sándwich con combo, $450 a $600"),
    "mostaza": (2, "hamburguesa con papas, $450 a $600"),
    "kfc": (2, "combo de $500 a $650"),
    "domino": (2, "pizza individual o porciones"),
    "sbarro": (2, "porciones y combos, $350 a $550"),
    "papa fritas": (2, "comida rápida"),
    "club de la papa frita": (2, "porciones de papas, $350 a $550"),
    "bocatti": (2, "sándwiches, $400 a $600"),
    "donut city": (1, "donuts y café, $150 a $300"),
    "grido": (1, "helado, $150 a $300"),
    "freddo": (1, "helado, $200 a $300"),
    "chentola": (1, "helado artesanal, $150 a $300"),
    "la cigale": (1, "helado, $150 a $300"),
    "lucciano": (1, "helado, $200 a $300"),
    "starbucks": (2, "bebida y snack, $400 a $550"),
    "the lab coffee": (2, "café de especialidad, $300 a $500"),
    "cafe martinez": (3, "café y comida, $600 a $800"),
    "le pain quotidien": (3, "brunch o almuerzo, $700 a $1000"),
    "porto vanila": (2, "pastelería y café, $300 a $550"),
    "oro del rhin": (2, "confitería, café y pasteles, $300 a $550"),
    "la pasiva": (3, "chivito o plato con bebida, $600 a $800"),
    "il mondo della pizza": (2, "pizza, $400 a $600"),
    "pizza piedra": (2, "pizza, $400 a $600"),
    "la fabrica empanadas": (1, "empanadas, $150 a $300"),
    "movie": (2, "entrada de cine, $330 a $450"),
    "life cinemas": (2, "entrada de cine, $300 a $450"),
    "cinemateca": (1, "entrada de cine, $250 a $300"),
    "teatro solis": (3, "entradas de $500 a $1800"),
    "pizzeria chiviteria parrillada": (3, "minutas y parrilla, $600 a $900"),
    "chivipizza": (2, "pizza y chivito, $400 a $600"),
    "1000 grados": (2, "pizza, $450 a $650"),
    "rodelu": (3, "pizzería y parrilla familiar, $600 a $900"),
    "el pony pisador": (3, "pub, $700 a $1000"),
    "montevideo beer company": (3, "cerveza artesanal, $700 a $1000"),
}

# Lugares conocidos de Montevideo, por categoría (nombre completo, sin tildes ni mayúsculas).
# Salen del conocimiento de la ciudad: precios típicos de cada lugar, no de una fuente oficial.
CONOCIDOS = {
    5: [],
    4: [
        "alquimista restaurante", "araza cocina nativa", "bisiesto", "city winery", "don koto", "nippon",
        "opiparus", "rara avis", "restaurant at the hilton", "rustica & mar", "tartufo", "ventus",
        "marisqueria el italiano solymar", "hard rock cafe", "verne eventos", "chez pyneiro", "el palenque",
        "polo bamba skybar", "artesana winery", "bracco bosca winery", "de lucca wines", "vina varela zarranz",
        "vinedos de la tahona", "establecimiento barras de mahoma", "establecimiento valle maria",
        "brava club", "cloud 7", "rio", "plaza mateo", "wooow! boliche",
    ],
    3: [
        "la barra", "havanna", "tea connection", "philomene", "compass marina cafe", "versailles", "fun fun",
        "la melaza candombe", "sensei bar", "la vaca azul", "dona marta", "el comedy", "sala zitarrosa",
        "la trastienda", "teatro solis", "auditorio nacional \"adela reta\"", "teatro sala verdi",
        "teatro de verano ramon collazo", "teatro astral", "teatro victoria", "teatro comedia", "teatro circular",
        "el galpon", "casa degli italiani", "hong kong", "donatello's", "il buon mangiare", "mamma nostra",
        "francesco", "negroni", "namaste", "quinterio", "temaki", "minzhine", "mercado del inmigrante",
        "puesta del sol", "patio euskadi", "the well", "romulo beer", "grot",
    ],
    2: [
        "alarabi", "alarabi cocina inclusiva", "andale taqueria vegana", "bar 17", "bar americano", "bar bass",
        "bar cristal", "bar gula", "bar los 4", "bar madison", "bar nuevo imperial", "bar rodo", "bar rover",
        "bar san martin", "bar san pedro", "club nueva palmira", "club social y deportivo chulo",
        "cocina y cafe", "coffeelado", "comi.k", "danubio azul", "de morondanga", "dilema cafe",
        "don peperone", "don pepperone", "el arabito", "el club de la milanesa", "el rey del sabor",
        "fabrica de pastas colon", "focaccia prado", "gran sportman", "greko's food",
        "guernika - la vermuteria del cordon", "la guera taqueria", "la panera rosa", "mc.pac-man",
        "papichulo", "vicentino cafe restaurant", "yaguaron bar", "casa de comida vegetariana",
        "sabores comida casera", "mi plato", "mi cocina", "la cocina de mama", "dona coxinha", "ecogranjas",
        "bar mercantil", "bar michigan", "gato tuerto garage", "pinup pub-pool", "pool 2000", "cerveza punto rojo",
        "brot haus", "healthyway", "tropical smoothie", "telizzia cat cafe", "spazio moka", "bowling center",
        "auditorio nelly goitino", "cultural mad", "alejandria cafe de las artes", "recreo ciudad vieja",
        "sala camacua", "sala la experimental", "el tinglado", "cine opera", "complejo cultural plaza",
        "grupo cine", "grupocine", "grupocine punta carretas", "grupocine las piedras", "life cinema", "life films uy",
        "museo castillo pittamiglio",
    ],
    1: [
        "cine universitario", "salla jorge lazaroff", "centro cultural florencio sanchez", "auditorio vaz ferreira",
        "independencia bochas club",
    ],
    0: [
        "cabildo", "museo nacional de antropologia", "museo de la memoria",
        "museo municipal de bellas artes juan manuel blanes", "museo historico nacional quinta de batlle",
        "casa de juan francisco giro", "casa de manuel ximenez y gomez", "casa de carlos vaz ferreira",
        "casa quinta de batlle y ordonez", "casa quinta de luis alberto de herrera", "fundacion mario benedetti",
        "observatorio astronomico de montevideo", "museo del observatorio meteorologico y astronomico",
        "centro de fotografia de montevideo", "fotogaleria parque rodo", "auditorio mario benedetti",
        "anfiteatro complejo torre de las comunicaciones",
    ],
}
CONOCIDOS_POR_NOMBRE = {_n: nivel for nivel, nombres in CONOCIDOS.items() for _n in nombres}

# Entradas que no son un lugar para hacer un plan (supermercados, oficinas, una fábrica, un diario...):
# no se les inventa precio.
NO_ES_PLAN = re.compile(
    r"hipermercado|\bgeant\b|redpagos|super totis|super megustan|centro del burlete|aeropuerto|paseo de compras|"
    r"\bpropios\b|^jbo\b|distribuidora|drogueria|^caif\b|la diaria|fnc pepsi|pilsen uruguay|mccain|"
    r"escuela esquinera|puerto chico$|montevideo, uruguay|pinamar|^colon$|^la sede$|barraca olivieri"
)

# Cocina de OpenStreetMap -> categoría. Si trae varias ("pizza;regional"), se toma la primera.
COCINAS = {
    "steak_house": (4, "parrilla/steakhouse"), "barbecue": (4, "parrilla"), "grill": (4, "parrilla"),
    "sushi": (4, "sushi"), "japanese": (4, "cocina japonesa"), "korean": (3, "cocina coreana"),
    "thai": (3, "cocina thai"), "indian": (3, "cocina india"), "peruvian": (4, "cocina peruana"),
    "seafood": (4, "pescados y mariscos"), "fish": (3, "pescados"), "french": (4, "cocina francesa"),
    "italian": (3, "cocina italiana"), "pasta": (3, "pastas"), "spanish": (3, "cocina española"),
    "mexican": (3, "cocina mexicana"), "regional": (3, "cocina uruguaya"), "uruguayan": (3, "cocina uruguaya"),
    "argentinian": (3, "cocina argentina"), "armenian": (3, "cocina armenia"), "german": (3, "cocina alemana"),
    "mediterranean": (3, "cocina mediterránea"), "international": (3, "cocina internacional"),
    "chinese": (3, "cocina china"), "vegetarian": (3, "vegetariano"), "vegan": (3, "vegano"),
    "pizza": (2, "pizzería"), "burger": (2, "hamburguesas"), "sandwich": (2, "sándwiches"),
    "chicken": (2, "pollo"), "kebab": (2, "kebab"), "arab": (2, "comida árabe"), "fast_food": (2, "comida rápida"),
    "breakfast": (2, "desayunos"), "coffee_shop": (2, "café"), "cafe": (2, "café"), "coffee": (2, "café"),
    "bakery": (1, "panadería"), "empanada": (1, "empanadas"), "juice": (1, "jugos"), "ice_cream": (1, "helado"),
    "dessert": (1, "postres"), "crepe": (2, "crepes"),
}

# Tipo -> prioridad para elegir cuál mirar cuando un lugar tiene varios.
PRIORIDAD_TIPO = ["Boliche", "Teatro", "Escape room", "bowling", "cine", "Museo", "Galería",
                  "Restaurante", "Comida rápida", "Pub", "bar", "cafe", "Heladería"]

# Categoría "normal" de cada tipo.
POR_TIPO = {
    "Restaurante": (3, "plato y bebida: $600 a $1000"),
    "Comida rápida": (2, "combo o minuta al paso: $350 a $600"),
    "cafe": (2, "café con algo para comer: $300 a $550"),
    "Heladería": (1, "helado: $150 a $300"),
    "bar": (2, "dos o tres tragos: $400 a $600"),
    "Pub": (3, "pintas y algo de picada: $600 a $1000"),
    "Boliche": (4, "entrada y tragos: $1000 a $1800"),
    "cine": (2, "entrada: $300 a $450"),
    "Teatro": (3, "entrada: $600 a $1200"),
    "Museo": (1, "entrada: $100 a $300"),
    "Galería": (0, "las galerías de arte suelen ser de entrada libre"),
    "Escape room": (3, "juego por persona: $550 a $750"),
    "bowling": (2, "partida y zapatos: $300 a $500"),
}


def _norm(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower().strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _principal(tipos):
    """El tipo que manda (por prioridad) entre los que tiene el lugar."""
    reales = {t: t for t in tipos}
    for t in PRIORIDAD_TIPO:
        for propio in reales:
            if _norm(propio) == _norm(t):
                return t
    return None


def por_nombre(n, tipo):
    """(categoría, motivo) a partir de palabras del nombre, o None. n ya viene normalizado."""
    if tipo in ("Restaurante", "Comida rápida"):
        if re.search(r"steak|entrecot|angus|cortes premium|rooftop|sky ", n):
            return 4, "steakhouse o lugar de alta gama"
        if re.search(r"sushi|ramen|nikkei|omakase|teppanyaki|izakaya", n):
            return (4 if tipo == "Restaurante" else 3), "sushi"
        if re.search(r"parrill|asador|brasa|grill|churrasc|\basado\b", n):
            if re.search(r"pizz|chiviter|minuta|rotiser|al paso", n):
                return 3, "parrilla y minutas de barrio"
            return (4 if tipo == "Restaurante" else 3), "parrilla"
        if re.search(r"viandas?|rotiser|delivery", n):
            return 2, "viandas o comida para llevar"
        if re.search(r"gourmet|bistr|chef|trattoria|ristorante|osteria|brasserie|cocina de autor|restaurant & |hotel|resort", n):
            return 4 if tipo == "Restaurante" else 3, "propuesta de restaurante de mayor categoría"
        if re.search(r"\bwok\b|oriental|china|chino|tenedor libre|buffet|libre\b", n):
            return 3, "tenedor libre / comida oriental"
        if re.search(r"panader|confiter|pasteler|bakery|boulangerie|croissant|brioche|galletas|postres|tartas|churreri|medialuna|masa madre|dulces", n):
            return 1, "panadería, confitería o postres"
        if re.search(r"empanada|choripan|panchos?\b|hot dog|churro|kiosco|carrito|food truck", n):
            return 1, "comida al paso"
        if re.search(r"pizz|fainá|faina|chiviter|chivito|minuta|rotiser|casa de comidas|comedor|cantina|bodegon|almacen|express|take ?away|al paso|lomitos?|hambur|burger|sandwich|sándwich", n):
            return 2, "pizzería, minutas o comida al paso"
    if tipo in ("cafe",):
        if re.search(r"panader|confiter|pasteler|bakery|kiosco|churro|medialuna|alfajor", n):
            return 1, "panadería o confitería"
        if re.search(r"roaster|specialty|especialidad|brunch|coffee lab|bistr", n):
            return 3, "café de especialidad o brunch"
    if tipo in ("bar", "Pub"):
        if re.search(r"winery|\bwines?\b|vinedo|vina |bodega|establecimiento", n):
            return 4, "bodega o visita con degustación"
        if re.search(r"cerveceri|taproom|brewery|craft|artesanal|beer|irish|bodega|vinoteca|\bwine\b|vino|cocktail|coctel|lounge|rooftop|speakeasy|whisk", n):
            return 3, "cervecería, vinoteca o coctelería"
        if re.search(r"restaurante|parrill|resto\b|cantina", n):
            return 3, "bar con cocina"
        if re.search(r"almacen|club social|bar de barrio|despacho|kiosco", n):
            return 1 if tipo == "bar" else 2, "bar de barrio"
    if tipo == "Heladería" and re.search(r"cafe|cafeteria|confiter|pasteler|chocolat", n):
        return 2, "heladería con café o pastelería"
    return None


def estimar(lugar, tags):
    """(categoría, origen, motivo) o None si no hay tipo reconocible."""
    nombre = _norm(lugar["nombre"])
    tipo = _principal(lugar["tipos"])

    # 0) lo que no es un lugar para un plan: sin precio
    if NO_ES_PLAN.search(nombre):
        return None

    # 1) lugar conocido de Montevideo (nombre exacto)
    if nombre in CONOCIDOS_POR_NOMBRE:
        return CONOCIDOS_POR_NOMBRE[nombre], "marca", "lugar conocido: precio típico según lo que se sabe de la ciudad"

    # 1b) cadena conocida
    marca = _norm(tags.get("brand") or "")
    for clave, (nivel, motivo) in CADENAS.items():
        if clave in nombre or (marca and clave in marca):
            return nivel, "marca", motivo

    if tipo is None:
        return None

    # 2) cocina de OpenStreetMap (solo para lugares de comida)
    cocina = (tags.get("cuisine") or "").split(";")[0].strip().lower()
    if cocina in COCINAS and tipo in ("Restaurante", "Comida rápida", "cafe", "Pub", "bar"):
        nivel, motivo = COCINAS[cocina]
        # Un restaurante nunca baja de 2 por una cocina "rápida"; un café no sube de 3 por cocina.
        if tipo == "cafe":
            nivel = min(nivel, 3)
        if tipo == "Comida rápida":
            nivel = min(nivel, 3)
        return nivel, "cocina", f"OpenStreetMap indica cocina {cocina}: {motivo}"

    # 3) palabras del nombre
    hallado = por_nombre(nombre, tipo)
    if hallado:
        return hallado[0], "nombre", hallado[1]

    # 4) lo normal para el tipo
    nivel, motivo = POR_TIPO[tipo]
    return nivel, "tipo", f"{tipo}: {motivo}"


# ---------------------------------------------------------------------------

def _tags_osm(lugares, ruta_cache):
    """Etiquetas de OpenStreetMap de los lugares con id (cuisine, brand...). Se guardan en un archivo."""
    if os.path.exists(ruta_cache):
        return json.load(open(ruta_cache, encoding="utf-8"))
    por_tipo = {}
    for l in lugares:
        if l["osm"]:
            t, i = l["osm"].split("/")
            por_tipo.setdefault(t, []).append(i)
    tags = {}
    for tipo, ids in por_tipo.items():
        for k in range(0, len(ids), 250):
            consulta = f'[out:json][timeout:120];{tipo}(id:{",".join(ids[k:k + 250])});out tags;'
            for el in osm._overpass(consulta, 180)["elements"]:
                tags[f"{el['type']}/{el['id']}"] = el.get("tags", {})
            time.sleep(4)
    json.dump(tags, open(ruta_cache, "w", encoding="utf-8"), ensure_ascii=False)
    return tags


def _leer_lugares(cur):
    cur.execute(
        """SELECT l."Id_Lugar"::text, l."Nombre", l."Osm_Id", l."Barrio", l."Nivel_Precio", l."Precio_Origen", l."Verificado",
                  COALESCE((SELECT string_agg(t."Nombre", '|' ORDER BY t."Nombre")
                            FROM public."Lugar_Tipo" lt JOIN public."Tipo" t ON t."Id_Tipo" = lt."Tipo_id"
                            WHERE lt."Lugar_id" = l."Id_Lugar"), '')
           FROM public."Lugar" l"""
    )
    return [dict(id=f[0], nombre=f[1], osm=f[2], barrio=f[3], nivel=f[4], origen=f[5], verificado=f[6],
                 tipos=f[7].split("|") if f[7] else []) for f in cur.fetchall()]


def _para_estimar(l):
    """¿Este lugar entra? Sin categoría, o con una estimación de este script. Nunca manual/verificado/gratis."""
    if l["verificado"] or l["origen"] == "manual":
        return False
    return l["nivel"] is None or l["origen"] in ("marca", "cocina", "nombre", "tipo")


SIGNOS = {0: "Gratis", 1: "$", 2: "$$", 3: "$$$", 4: "$$$$", 5: "$$$$$"}


def _guardar_revision(filas):
    os.makedirs(DATOS, exist_ok=True)
    with open(os.path.join(DATOS, "revision_precios.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Nombre", "Tipos", "Barrio", "Categoría", "Origen", "Motivo"])
        for r in filas:
            w.writerow([r["nombre"], ", ".join(r["tipos"]), r["barrio"] or "", r["nivel"], r["origen"], r["motivo"]])

    datos = json.dumps(
        [{"n": r["nombre"], "t": ", ".join(r["tipos"]), "b": r["barrio"] or "", "c": r["nivel"], "o": r["origen"], "m": r["motivo"]}
         for r in filas], ensure_ascii=False).replace("</", "<\\/")
    pagina = """<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisión de precios estimados</title>
<style>
:root{--bg:#f6f1e6;--card:#ebe2cf;--ink:#18140f;--muted:#55605c;--line:rgba(24,20,15,.16);--ac:#31533f;--on:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#141119;--card:#1b1724;--ink:#ece9f2;--muted:#a49fb2;--line:rgba(236,233,242,.16);--ac:#8fb59b;--on:#141119}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}
header{padding:18px 16px 8px}h1{margin:0 0 4px;font-size:21px}p{margin:0;color:var(--muted)}
.barra{display:flex;flex-wrap:wrap;gap:8px;padding:8px 16px 12px;position:sticky;top:0;background:var(--bg);z-index:2}
.barra input,.barra select{min-height:40px;padding:0 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font:inherit}
.barra input{flex:1 1 220px}.tabla{overflow:auto;max-height:calc(100vh - 160px);margin:0 16px 24px;border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;min-width:900px}th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{position:sticky;top:0;background:var(--ac);color:var(--on);cursor:pointer;white-space:nowrap}tbody tr:nth-child(even){background:color-mix(in srgb,var(--card) 55%,transparent)}
.c{font-weight:700;white-space:nowrap}.o{display:inline-block;padding:0 8px;border:1px solid var(--line);border-radius:999px;font-size:13px}
</style></head><body>
<header><h1>Revisión de precios estimados</h1><p>Categorías: Gratis · $ (100-300) · $$ (300-600) · $$$ (600-1000) · $$$$ (1000-2000) · $$$$$ (más de 2000). "Origen" dice de dónde salió cada estimación: marca (cadena conocida), cocina (OpenStreetMap), nombre (palabras del nombre) o tipo (lo normal para ese tipo: la menos confiable).</p></header>
<div class="barra"><input id="q" type="search" placeholder="Buscar por nombre, tipo o barrio…"><select id="cat"><option value="">Todas las categorías</option></select>
<select id="ori"><option value="">Todos los orígenes</option><option>marca</option><option>cocina</option><option>nombre</option><option>tipo</option></select>
<select id="tip"><option value="">Todos los tipos</option></select><span id="cuenta" style="align-self:center;color:var(--muted)"></span></div>
<div class="tabla"><table><thead><tr id="cab"></tr></thead><tbody id="cuerpo"></tbody></table></div>
<script id="d" type="application/json">__DATOS__</script>
<script>
const F=JSON.parse(document.getElementById("d").textContent),S=["Gratis","$","$$","$$$","$$$$","$$$$$"],$=i=>document.getElementById(i);
const norm=s=>String(s||"").normalize("NFD").replace(/[\\u0300-\\u036f]/g,"").toLowerCase();let ord={k:"n",a:true};
const COL=[["n","Nombre"],["t","Tipos"],["b","Barrio"],["c","Categoría"],["o","Origen"],["m","Por qué"]];
$("cab").append(...COL.map(([k,t])=>{const th=document.createElement("th");th.textContent=t;th.onclick=()=>{ord={k,a:ord.k===k?!ord.a:true};pintar()};return th}));
for(let i=0;i<6;i++)$("cat").append(new Option(S[i],i));
[...new Set(F.flatMap(f=>f.t.split(", ")))].sort().forEach(t=>$("tip").append(new Option(t,t)));
function pintar(){const q=norm($("q").value),c=$("cat").value,o=$("ori").value,t=$("tip").value;
const L=F.filter(f=>(!q||norm(f.n+" "+f.t+" "+f.b).includes(q))&&(c===""||String(f.c)===c)&&(!o||f.o===o)&&(!t||f.t.split(", ").includes(t)));
L.sort((a,b)=>(typeof a[ord.k]==="number"?a[ord.k]-b[ord.k]:String(a[ord.k]).localeCompare(String(b[ord.k]),"es"))*(ord.a?1:-1));
$("cuenta").textContent=L.length+" de "+F.length;
$("cuerpo").replaceChildren(...L.map(f=>{const tr=document.createElement("tr");
const td=(x,cl)=>{const e=document.createElement("td");e.textContent=x;if(cl)e.className=cl;return e};
const eo=document.createElement("td"),sp=document.createElement("span");sp.className="o";sp.textContent=f.o;eo.append(sp);
tr.append(td(f.n),td(f.t),td(f.b),td(S[f.c],"c"),eo,td(f.m));return tr}));}
["q","cat","ori","tip"].forEach(i=>$(i).addEventListener("input",pintar));pintar();
</script></body></html>""".replace("__DATOS__", datos)
    with open(os.path.join(DATOS, "revision_precios.html"), "w", encoding="utf-8") as f:
        f.write(pagina)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Estima categorías de precio de los lugares.")
    ap.add_argument("--revisar", action="store_true", help="genera la tabla de revisión; no escribe en la base")
    ap.add_argument("--aplicar", action="store_true", help="guarda las estimaciones en la base")
    ap.add_argument("--tags", default=os.path.join(DATOS, "osm_tags.json"), help="archivo con las etiquetas de OSM (se baja si no existe)")
    args = ap.parse_args(argv)
    if not (args.revisar or args.aplicar):
        ap.error("elegí --revisar o --aplicar")

    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
    from database import get_db_connection, release_db_connection
    from psycopg2.extras import execute_values

    os.makedirs(DATOS, exist_ok=True)
    conexion = get_db_connection()
    try:
        cur = conexion.cursor()
        lugares = _leer_lugares(cur)
        candidatos = [l for l in lugares if _para_estimar(l)]
        tags = _tags_osm(lugares, args.tags)

        filas, sin_tipo = [], []
        for l in candidatos:
            r = estimar(l, tags.get(l["osm"], {}) if l["osm"] else {})
            if r is None:
                sin_tipo.append(l)
                continue
            filas.append({**l, "nivel": r[0], "origen": r[1], "motivo": r[2]})

        print(f"Lugares: {len(lugares)} | a estimar: {len(candidatos)} | estimados: {len(filas)} | sin estimar: {len(sin_tipo)}")
        if sin_tipo:
            print("  sin estimar (no parecen un lugar para un plan):", ", ".join(l["nombre"] for l in sin_tipo[:12]))
        print("Por origen:", dict(Counter(f["origen"] for f in filas)))
        print("Por categoría:", {SIGNOS[k]: v for k, v in sorted(Counter(f["nivel"] for f in filas).items())})
        _guardar_revision(filas)
        print("Escribí datos/revision_precios.html y .csv")

        if not args.aplicar:
            return 0

        sufijo = time.strftime("%Y%m%d")
        cur.execute(f'CREATE TABLE IF NOT EXISTS backup."Lugar_antes_precios_{sufijo}" AS TABLE public."Lugar"')
        for i in range(0, len(filas), 500):
            lote = [(f["id"], f["nivel"], f["origen"]) for f in filas[i:i + 500]]
            execute_values(
                cur,
                """UPDATE public."Lugar" l SET "Nivel_Precio" = v.nivel, "Precio_Origen" = v.origen
                   FROM (VALUES %s) AS v(id, nivel, origen)
                   WHERE l."Id_Lugar" = v.id::uuid AND NOT l."Verificado" AND l."Precio_Origen" IS DISTINCT FROM 'manual'""",
                lote, template="(%s, %s::int, %s)", page_size=500,
            )
        conexion.commit()
        print(f'Guardado. Respaldo: backup."Lugar_antes_precios_{sufijo}".')
    except BaseException:
        conexion.rollback()
        raise
    finally:
        release_db_connection(conexion)
    return 0


if __name__ == "__main__":
    sys.exit(main())
