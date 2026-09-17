"""Estimación del precio de un plan a partir del "Nivel_Precio" de cada
lugar (0 a 4 en la tabla "Lugar" — no hay un monto en pesos guardado).

Para ajustar los montos, solo hay que cambiar RANGOS_POR_NIVEL. Nada
más en el código depende de estos números.
"""

RANGOS_POR_NIVEL = {
    0: (0, 0),
    1: (100, 300),
    2: (300, 600),
    3: (600, 1000),
    4: (1000, 2000),
}


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
