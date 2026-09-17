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


FILTROS_LUGAR = [
    {
        "id": "apto_menores",
        "etiqueta": "Apto menores",
        "tipo": "checkbox",
        "sql": 'l."Apto_Menores" = true',
    },
    {
        "id": "opcion_celiacos",
        "etiqueta": "Opción celíaca",
        "tipo": "checkbox",
        "sql": 'l."Opcion_Celiacos" = true',
    },
    {
        "id": "opcion_vegana",
        "etiqueta": "Opción vegana",
        "tipo": "checkbox",
        "sql": 'l."Opcion_Vegana" = true',
    },
    {
        "id": "nivel_precio",
        "etiqueta": "Precio máximo",
        "tipo": "select",
        "opciones": [
            ("", "Cualquiera"),
            ("1", "$"),
            ("2", "$$"),
            ("3", "$$$"),
            ("4", "$$$$"),
        ],
        "sql": 'l."Nivel_Precio" <= %s',
    },
    {
        "id": "ambiente",
        "etiqueta": "Ambiente",
        "tipo": "texto",
        "sql": 'l."Ambiente" ILIKE %s',
        "transformar": lambda valor: f"%{valor}%",
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

        transformar = filtro.get("transformar")
        if transformar:
            valor = transformar(valor)

        condiciones.append(filtro["sql"])
        if "%s" in filtro["sql"]:
            parametros.append(valor)

    return condiciones, parametros
