"""Reglas de coherencia de un plan: qué combinaciones de paradas tienen sentido.

Cada lugar se clasifica en uno o más ROLES (comer, cafe, postre, bebida,
actividad, paseo) mirando el nombre de sus Tipos en la base, y como
respaldo el nombre del propio lugar. Después se limita cuántas paradas de
cada rol puede tener un plan (MAX_POR_ROL): así el bot no puede armar una
salida con dos restaurantes.

PARA AJUSTARLO (no hay que tocar nada más):
  * ROLES: palabras que identifican cada rol. "pizzer*" con asterisco
    significa "empieza con" (pizzería, pizzerías); sin asterisco tiene que
    ser la palabra exacta ("bar" no matchea "barrio").
  * MAX_POR_ROL: cuántas paradas de ese rol se permiten. Los roles que no
    están acá no tienen límite.

Para ver cómo quedan clasificados los Tipos de TU base y qué falta:
    python -m services.plan_reglas
"""
import re
import unicodedata

ROLES = {
    "comer": [
        "restaurant*", "restoran*", "parrilla*", "pizzer*", "pizza*", "comida*", "hamburgues*",
        "burger", "sushi", "pasta*", "cantina*", "bodegon*", "rotiser*", "asador*", "asado*",
        "marisqu*", "chiviter*", "chivito*", "cena", "almuerzo", "gastronomi*", "food",
        "trattoria", "bistro", "wok", "taqueria*", "empanad*", "milanesa*", "cocina",
    ],
    "cafe": ["cafe", "cafes", "cafeter*", "confiter*", "panader*", "brunch", "merienda"],
    "postre": ["helader*", "postre*", "pasteler*", "chocolater*"],
    "bebida": [
        "bar", "bares", "pub", "pubs", "cervecer*", "coctel*", "cocktail*", "vinoteca*",
        "whisker*", "tragos",
    ],
    "actividad": [
        "cine", "teatro", "museo*", "pool", "billar", "bowling", "karaoke", "escape",
        "arcade", "juegos", "paintball", "casino", "galeria*", "concierto*", "recital*",
        "boliche*", "club", "show*", "gimnasio*", "climbing", "trampolin*",
    ],
    "paseo": ["plaza*", "rambla", "parque*", "playa*", "mirador*", "feria*", "peatonal"],
}

MAX_POR_ROL = {"comer": 1, "cafe": 1, "postre": 1, "bebida": 2}

_ETIQUETA = {
    "comer": "para comer (restaurante, parrilla, pizzería...)",
    "cafe": "de café",
    "postre": "de postre o heladería",
    "bebida": "de bar o para tomar algo",
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _roles_de_texto(texto):
    palabras = re.findall(r"[a-z0-9]+", _normalizar(texto))
    encontrados = []
    for rol, claves in ROLES.items():
        for clave in claves:
            if clave.endswith("*"):
                coincide = any(p.startswith(clave[:-1]) for p in palabras)
            else:
                coincide = clave in palabras
            if coincide:
                encontrados.append(rol)
                break
    return encontrados


def roles_de(nombre_lugar, tipos):
    """Roles de un lugar: primero por los nombres de sus Tipos; si ninguno
    dice nada, por el nombre del lugar (ej: 'Pizzería Real')."""
    roles = []
    for tipo in tipos or []:
        for rol in _roles_de_texto(tipo):
            if rol not in roles:
                roles.append(rol)
    if not roles:
        roles = _roles_de_texto(nombre_lugar)
    return roles


def _se_puede_repartir(lugares):
    """True si cada lugar puede contarse en UN solo rol sin pasarse de
    MAX_POR_ROL. Un "Bar y restaurante" tiene dos roles pero es una sola
    parada: cuenta como comer o como bebida, el que deje el plan válido.
    Un lugar que además es actividad o paseo (rol sin límite) no se cuenta."""
    cupos = dict(MAX_POR_ROL)
    opciones = []
    for lugar in lugares:
        roles = lugar.get("roles", [])
        if any(r not in MAX_POR_ROL for r in roles):
            continue  # tiene un rol sin límite: no ocupa cupo
        con_limite = [r for r in roles if r in MAX_POR_ROL]
        if con_limite:
            opciones.append(con_limite)
    # Primero los que tienen una sola opción (menos margen).
    opciones.sort(key=len)

    def colocar(k):
        if k == len(opciones):
            return True
        for rol in opciones[k]:
            if cupos[rol] > 0:
                cupos[rol] -= 1
                if colocar(k + 1):
                    return True
                cupos[rol] += 1
        return False

    return colocar(0)


def validar(lugares):
    """lugares: [{"nombre": str, "roles": [str]}] en orden del recorrido.
    Devuelve una lista de errores en texto (vacía = plan coherente). El
    texto está pensado para que el modelo lo lea y corrija el borrador."""
    if _se_puede_repartir(lugares):
        return []

    errores = []
    for rol, maximo in MAX_POR_ROL.items():
        con_rol = [l["nombre"] for l in lugares if rol in l.get("roles", [])]
        if len(con_rol) > maximo:
            errores.append(
                f"Hay {len(con_rol)} lugares {_ETIQUETA[rol]} ({' y '.join(con_rol)}) y un plan "
                f"puede tener como máximo {maximo}."
            )
    errores.append(
        "Reemplazá la parada que sobra por otro tipo (paseo, actividad, postre o café) "
        "buscando con buscar_lugares, o proponé un plan con menos paradas (1 o 2 alcanzan)."
    )
    return errores


if __name__ == "__main__":
    # Diagnóstico: cómo se clasifica cada Tipo de la base.
    from database import get_db_connection, release_db_connection

    conexion = get_db_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute('SELECT "Nombre" FROM public."Tipo" ORDER BY "Nombre"')
            nombres = [fila[0] for fila in cursor.fetchall()]
    finally:
        release_db_connection(conexion)

    sin_rol = []
    for nombre in nombres:
        roles = _roles_de_texto(nombre)
        print(f"{nombre:<30} -> {', '.join(roles) if roles else '(sin rol)'}")
        if not roles:
            sin_rol.append(nombre)
    print(f"\n{len(nombres) - len(sin_rol)} de {len(nombres)} tipos con rol.")
    if sin_rol:
        print("Sin rol (agregá palabras en ROLES si alguno es de comida, bar, etc.):", ", ".join(sin_rol))