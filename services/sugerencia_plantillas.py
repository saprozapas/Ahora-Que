"""Planes sugeridos armados SIN el modelo de lenguaje (no gastan tokens de Groq).

Hacen lo mismo que el modelo en `sugerencia_service`: combinan 1 a 3 lugares cercanos entre sí y que tengan
sentido juntos (nunca dos lugares para comer, por ejemplo), y les ponen un nombre corto (máximo 4 palabras)
y una frase de una línea (máximo 110 caracteres) en español rioplatense. Para que no suenen todas iguales
hay varias plantillas y se elige una según el usuario y la semana.
"""

import math
import random
import re

from services import plan_reglas

MAX_NOMBRE_PALABRAS = 4
MAX_DESCRIPCION = 110
DISTANCIA_MAXIMA_KM = 1.8
CENTRO_MONTEVIDEO = (-34.9058, -56.1913)  # Plaza Independencia

# Cómo se llama cada tipo de parada dentro del nombre del plan, y en qué orden se recorren.
_SUSTANTIVO = {
    "comer": "Comida", "cafe": "Café", "postre": "Postre", "bebida": "Tragos",
    "actividad": "Actividad", "paseo": "Paseo", "otro": "Salida",
}
_ORDEN = {"cafe": 0, "comer": 0, "paseo": 1, "otro": 1, "actividad": 1, "postre": 2, "bebida": 3}

_NOMBRES_DOS = ("{A} y {b}", "{A} y {b} cerca", "{A} y {b} en {barrio}", "Salida a {barrio}")
_NOMBRES_UNO = ("{A} en {barrio}", "{A} de la semana", "Salida a {barrio}")

# {p1}, {p2}, {p3}: nombres de los lugares; {barrio}: el barrio; {fav}: un tipo que la persona suele elegir.
_DESC_UNO = (
    "Un lugar nuevo para vos: {p1}, ideal para ir sin complicarse.",
    "Probá {p1}: un plan simple para sumar a tus salidas.",
    "{p1}, un plan tranquilo para esta semana.",
)
_DESC_DOS = (
    "Empezá en {p1} y seguí en {p2}: todo a pocas cuadras.",
    "{p1} y {p2}: dos paradas cerca entre sí para una salida sin vueltas.",
    "Ideal para ir sin apuro: {p1} y después {p2}, bien cerquita.",
    "Una salida por {barrio}: pasá por {p1} y terminá en {p2}.",
)
_DESC_TRES = (
    "{p1}, {p2} y {p3}: tres paradas cerca para recorrer con calma.",
    "Arrancá en {p1}, seguí por {p2} y cerrá en {p3}, todo cerquita.",
    "Una tarde completa por {barrio}: {p1}, {p2} y {p3}.",
)
_DESC_FAV = (
    "Va con lo que solés elegir ({fav}): {p1} y {p2}.",
    "Para tu lado de {fav}: {p1} y después {p2}, cerca entre sí.",
)
_DESC_FAV_UNO = ("Va con lo que solés elegir ({fav}): {p1}.",)


def _km(a, b):
    """Distancia aproximada entre dos puntos (lat, lon) en km."""
    f1, f2 = math.radians(a[0]), math.radians(b[0])
    df, dl = f2 - f1, math.radians(b[1] - a[1])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _corto(nombre, largo=26):
    nombre = re.sub(r"\s+", " ", str(nombre or "")).strip()
    if len(nombre) <= largo:
        return nombre
    return nombre[:largo].rsplit(" ", 1)[0].rstrip(",.-") + "…"


def _palabras(texto):
    return len(texto.split())


def _barrio_de(lugares):
    barrios = [l["barrio"] for l in lugares if l.get("barrio")]
    return max(set(barrios), key=barrios.count) if barrios else None


def _elegir(plantillas, valores, rnd, usadas, valida):
    """Primera plantilla (empezando por una al azar) que se puede completar y cumple `valida`."""
    inicio = rnd.randrange(len(plantillas))
    for k in range(len(plantillas)):
        plantilla = plantillas[(inicio + k) % len(plantillas)]
        try:
            texto = plantilla.format(**valores)
        except KeyError:
            continue
        if texto in usadas or not valida(texto):
            continue
        return texto
    return None


def _nombre(lugares, rnd, usados):
    sustantivos = []
    for l in lugares:
        s = _SUSTANTIVO[l["rol"]]
        if s not in sustantivos:
            sustantivos.append(s)
    barrio = _barrio_de(lugares)
    valores = {"A": sustantivos[0], "b": (sustantivos[1] if len(sustantivos) > 1 else "").lower(), "barrio": barrio or ""}
    if barrio is None:
        plantillas = ("{A} y {b}", "{A} y {b} cerca") if len(sustantivos) > 1 else ("{A} de la semana",)
    else:
        plantillas = _NOMBRES_DOS if len(sustantivos) > 1 else _NOMBRES_UNO
    nombre = _elegir(plantillas, valores, rnd, usados, lambda t: _palabras(t) <= MAX_NOMBRE_PALABRAS)
    return nombre or "Salida de la semana"


def _descripcion(lugares, favoritos, tipos, rnd):
    # Primero con los nombres completos; si ninguna plantilla entra en 110 caracteres, con nombres recortados.
    for largo in (200, 30, 22):
        texto = _descripcion_con(lugares, favoritos, tipos, rnd, largo)
        if texto:
            return texto
    return "Una salida cerca entre sí para esta semana."


def _descripcion_con(lugares, favoritos, tipos, rnd, largo):
    nombres = {f"p{i + 1}": _corto(l["nombre"], largo) for i, l in enumerate(lugares)}
    barrio = _barrio_de(lugares)
    valores = {**nombres, "barrio": barrio or ""}
    fav = next((t for l in lugares for t in tipos.get(l["id"], []) if t in favoritos), None)
    if fav:
        valores["fav"] = fav.lower()
    if len(lugares) == 1:
        grupos = ((_DESC_FAV_UNO,) if fav else ()) + (_DESC_UNO,)
    elif len(lugares) == 2:
        grupos = ((_DESC_FAV,) if fav else ()) + (_DESC_DOS,)
    else:
        grupos = (_DESC_TRES,)
    # Si la persona tiene un tipo favorito en el plan, se usa una frase que lo nombre; si no, una general.
    for plantillas in grupos:
        if "{barrio}" in " ".join(plantillas) and not barrio:
            plantillas = tuple(p for p in plantillas if "{barrio}" not in p)
        if not plantillas:
            continue
        texto = _elegir(plantillas, valores, rnd, (), lambda t: len(t) <= MAX_DESCRIPCION)
        if texto:
            return texto
    return None


def armar_planes(candidatos, tipos, favoritos, barrios, semilla, cantidad=3):
    """candidatos: [(id, nombre, barrio, nivel_precio, lat, lon)]. Devuelve [{"nombre", "descripcion", "ids"}]."""
    rnd = random.Random(str(semilla))
    items = []
    for c in candidatos:
        roles = plan_reglas.roles_de(c[1], tipos.get(c[0], []))
        items.append({
            "id": c[0], "nombre": c[1], "barrio": c[2], "punto": (c[4], c[5]) if c[4] is not None and c[5] is not None else None,
            "roles": roles, "rol": roles[0] if roles else "otro",
            "favorito": any(t in favoritos for t in tipos.get(c[0], [])),
            "del_barrio": c[2] in barrios if c[2] else False,
        })
    # Lugares con coordenadas lejos de Montevideo (datos mal cargados) no se sugieren.
    items = [i for i in items if i["punto"] is None or _km(i["punto"], CENTRO_MONTEVIDEO) <= 25]
    # Primero lo que más se parece a lo que la persona suele elegir; el resto conserva el orden (ya mezclado).
    items.sort(key=lambda i: (not i["favorito"], not i["del_barrio"]))

    usados, planes, nombres_usados = set(), [], set()
    for _ in range(cantidad):
        libres = [i for i in items if i["id"] not in usados]
        if not libres:
            break
        ancla = libres[0]
        elegidos = [ancla]
        objetivo = rnd.choice((2, 2, 3))
        cerca = [i for i in libres[1:] if ancla["punto"] and i["punto"] and _km(ancla["punto"], i["punto"]) <= DISTANCIA_MAXIMA_KM]
        cerca.sort(key=lambda i: _km(ancla["punto"], i["punto"]))
        for otro in cerca:
            if len(elegidos) >= objetivo:
                break
            if otro["rol"] in {e["rol"] for e in elegidos} and otro["rol"] != "otro":
                continue
            if plan_reglas.validar([{"nombre": e["nombre"], "roles": e["roles"]} for e in elegidos + [otro]]):
                continue
            elegidos.append(otro)
        elegidos.sort(key=lambda i: _ORDEN[i["rol"]])
        usados.update(e["id"] for e in elegidos)
        nombre = _nombre(elegidos, rnd, nombres_usados)
        nombres_usados.add(nombre)
        planes.append({
            "nombre": nombre,
            "descripcion": _descripcion(elegidos, favoritos, tipos, rnd),
            "ids": [e["id"] for e in elegidos],
        })
    return planes
