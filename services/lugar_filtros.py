"""Filtros para la búsqueda de lugares.

TODO lo que hay que tocar para agregar o sacar un filtro está en la
lista FILTROS_LUGAR de abajo: se agrega (o se borra) un diccionario y
listo. El formulario HTML y la consulta SQL se arman solos a partir de
esta lista, así que no hay que tocar ni el template ni el JavaScript ni
el service.

Cada filtro es un diccionario con:

  id        nombre del campo en el formulario (tiene que ser único)
  etiqueta  lo que ve el usuario
  tipo      "checkbox" | "select" | "texto" | "numero"
  sql       condición SQL. Si lleva %s, el valor se pasa como parámetro.
            Los checkbox normalmente no llevan %s (la condición es fija).
  opciones  solo para tipo "select": lista de (valor, etiqueta)
  transformar  opcional: función que ajusta el valor antes de mandarlo
               a SQL (por ejemplo para envolverlo en % de un ILIKE)

Las columnas se escriben entre comillas dobles porque el esquema usa
mayúsculas (ver "Plan_Lugar", "Nivel_Precio", etc).
"""

import unicodedata


def quitar_tildes(texto):
    """Minúsculas y sin tildes: es lo mismo que hace la parte de SQL con translate()
    (no se usa la extensión unaccent porque no está en todas las bases)."""
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return unicodedata.normalize("NFC", "".join(c for c in texto if unicodedata.category(c) != "Mn"))


FILTROS_LUGAR = [
    {
        "id": "nivel_precio",
        "etiqueta": "Precio máximo",
        "tipo": "select",
        "opciones": [
            ("", "Cualquiera"),
            ("0", "Gratis"),
            ("1", "$ (100 a 300)"),
            ("2", "$$ (300 a 600)"),
            ("3", "$$$ (600 a 1000)"),
            ("4", "$$$$ (1000 a 2000)"),
            ("5", "$$$$$ (más de 2000)"),
        ],
        "sql": '(l."Nivel_Precio" IS NULL OR l."Nivel_Precio" <= %s)',  # sin dato: no se descarta
    },
    {
        "id": "ambiente",
        "etiqueta": "Ambiente",
        "tipo": "texto",
        "sql": 'translate(lower(l."Ambiente"), \'áéíóúüñ\', \'aeiouun\') LIKE %s',
        "transformar": lambda valor: f"%{quitar_tildes(valor)}%",
    },
    {
        "id": "barrio",
        "etiqueta": "Barrio",
        "tipo": "texto",
        "sql": 'translate(lower(l."Barrio"), \'áéíóúüñ\', \'aeiouun\') LIKE %s',
        "transformar": lambda valor: f"%{quitar_tildes(valor)}%",
    },
]


def construir_condiciones(valores):
    """Arma las condiciones SQL a partir de los valores del formulario.

    valores: dict tipo request.args (id_del_filtro -> valor)

    Devuelve (condiciones, parametros), donde condiciones es una lista de
    strings para pegar con AND, y parametros la lista de valores para
    psycopg2 en el mismo orden.
    """
    condiciones = []
    parametros = []

    for filtro in FILTROS_LUGAR:
        valor = valores.get(filtro["id"], "")

        if filtro["tipo"] == "checkbox":
            # Solo aplica si el usuario lo tildó.
            if valor in ("1", "true", "on", "sí", "si"):
                condiciones.append(filtro["sql"])
            continue

        # Para los demás tipos, un valor vacío significa "sin filtrar".
        if valor is None or str(valor).strip() == "":
            continue

        valor = str(valor).strip()

        # Un select solo acepta los valores de su lista: así un valor
        # inventado en la URL (?nivel_precio=abc) no llega a la consulta.
        if filtro["tipo"] == "select" and valor not in {v for v, _ in filtro["opciones"]}:
            continue

        transformar = filtro.get("transformar")
        if transformar:
            valor = transformar(valor)

        condiciones.append(filtro["sql"])
        if "%s" in filtro["sql"]:
            parametros.append(valor)

    return condiciones, parametros