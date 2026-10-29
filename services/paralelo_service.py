"""Lecturas independientes a la vez: la página tarda lo de la más lenta y no la suma de todas."""
from concurrent.futures import ThreadPoolExecutor


def correr_en_paralelo(*funciones):
    """Corre funciones sin argumentos en hilos y devuelve sus resultados en el mismo orden.
    Si una falla, la excepción sale acá igual que si se hubiera llamado en serie."""
    with ThreadPoolExecutor(max_workers=len(funciones)) as pool:
        return list(pool.map(lambda funcion: funcion(), funciones))