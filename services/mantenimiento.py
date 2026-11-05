"""Limpieza programada de registros temporales (Ley 18.331, art. 8: no guardar los datos más de lo necesario)."""

import threading
import time

from database import get_db_connection, release_db_connection

_CADA_SEGUNDOS = 24 * 60 * 60
_lock = threading.Lock()
_ultima = 0.0


def _limpiar():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('DELETE FROM public."Confirmaciones_Registro" WHERE "Expira_En" <= NOW()')
            cur.execute("""DELETE FROM public."Intentos_Login" WHERE "Creado_En" < NOW() - INTERVAL '1 day'""")
        conn.commit()
    except Exception as e:
        if conn is not None:
            conn.rollback()
        print(f"No se pudo hacer la limpieza programada: {e}")
    finally:
        if conn is not None:
            release_db_connection(conn)


def programar_limpieza():
    """Se llama en cada pedido: una vez por día y por proceso lanza la limpieza en segundo plano."""
    global _ultima
    with _lock:
        if time.monotonic() - _ultima < _CADA_SEGUNDOS:
            return
        _ultima = time.monotonic()
    threading.Thread(target=_limpiar, daemon=True).start()
