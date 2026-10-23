"""Estimación del precio de un plan a partir del "Nivel_Precio" de cada
lugar (0 a 5 en la tabla "Lugar" — no hay un monto en pesos guardado).

Las categorías de la app:

    0  Gratis
    1  $      de 100 a 300 pesos
    2  $$     de 300 a 600 pesos
    3  $$$    de 600 a 1000 pesos
    4  $$$$   de 1000 a 2000 pesos
    5  $$$$$  más de 2000 pesos

Para ajustar los montos, solo hay que cambiar RANGOS_POR_NIVEL. Nada
más en el código depende de estos números (la base acepta 0 a 5: ver
migraciones/nivel_precio_5.sql; si se agrega otra categoría hay que
ampliar esa regla).
"""

RANGOS_POR_NIVEL = {
    0: (0, 0),
    1: (100, 300),
    2: (300, 600),
    3: (600, 1000),
    4: (1000, 2000),
    # "Más de 2000": no tiene tope. Para sumar el costo de un plan se usa 4000
    # como estimación del máximo; el mínimo (2000) es el dato firme.
    5: (2000, 4000),
}

# La última categoría no tiene máximo: en pantalla se muestra "Más de $2000".
NIVEL_SIN_TOPE = max(RANGOS_POR_NIVEL)


def etiqueta_de_nivel(nivel):
    """"Gratis", "$100 - $300", ..., "Más de $2000": el texto de una categoría."""
    minimo, maximo = RANGOS_POR_NIVEL[nivel]
    if nivel == 0:
        return "Gratis"
    if nivel == NIVEL_SIN_TOPE:
        return f"Más de ${minimo:g}"
    return f"${minimo:g} - ${maximo:g}"


def rango_de_nivel(nivel_precio):
    """(min, max) para un nivel de precio, o None si no hay dato."""
    if nivel_precio is None:
        return None
    try:
        nivel = int(nivel_precio)
    except (TypeError, ValueError):
        return None
    return RANGOS_POR_NIVEL.get(nivel)


def sumar_rangos(rangos):
    """Suma una lista de (min, max) ignorando los None.

    Devuelve (min_total, max_total), o None si ninguno tenía rango.
    """
    validos = [r for r in rangos if r is not None]
    if not validos:
        return None
    return sum(r[0] for r in validos), sum(r[1] for r in validos)
