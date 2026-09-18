import os
import queue
import re
import threading
import time

import psycopg2
from psycopg2 import extensions

# ---- CONEXIÓN A LA BASE DE DATOS (Supabase / PostgreSQL) ----
DB_URL = os.environ.get(
    "AHORAQUE_DB_URL",
    "postgresql://postgres.kmeggurdtvyvtyhpanox:AhoraQue2026@aws-0-us-east-2.pooler.supabase.com:6543/postgres",
)

# =============================================================================
# POR QUÉ ESTE ARCHIVO ES ASÍ
#
# La base está en Ohio: cada viaje de ida y vuelta desde Uruguay son ~170 ms.
# Lo que hace lenta la página es la CANTIDAD de viajes, no la base.
#
# 1) Pool: abrir una conexión son ~6 viajes (~1 s). Se abren una vez y se
#    reutilizan. El close() que ya hace el código la devuelve al pool.
#
# 2) Autocommit + BEGIN diferido: psycopg2 normal manda "BEGIN" en un viaje
#    aparte antes de cada consulta, y después hay que hacer ROLLBACK para
#    devolver la conexión limpia: 3 viajes por un SELECT. Acá:
#      - Un SELECT va solo: 1 viaje.
#      - La primera escritura (INSERT/UPDATE/DELETE) de una función se manda
#        como "BEGIN; INSERT ..." en el MISMO viaje, así que commit() y
#        rollback() siguen funcionando igual y las escrituras múltiples
#        (crear_plan, aceptar invitación...) siguen siendo atómicas.
#
# 3) Conexiones tibias: un hilo de fondo mantiene 2 conexiones abiertas y
#    vivas, así nunca se paga el segundo de abrir una conexión nueva.
# =============================================================================

_MIN_LIBRES = 2
_MAX_LIBRES = 10
_PING_CADA_SEG = 60

_libres = queue.LifoQueue(maxsize=_MAX_LIBRES)
_hilo_iniciado = False
_lock_hilo = threading.Lock()

_ES_ESCRITURA = re.compile(
    r"^\s*(?:--[^\n]*\n\s*)*(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|WITH)\b",
    re.IGNORECASE,
)

_IDLE = extensions.TRANSACTION_STATUS_IDLE
_ROTA = extensions.TRANSACTION_STATUS_UNKNOWN


def _abrir_conexion():
    conn = psycopg2.connect(
        DB_URL,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )
    conn.autocommit = True
    return conn


def _en_transaccion(conn):
    return conn.get_transaction_status() not in (_IDLE, _ROTA)


def _terminar(conn, sql):
    """COMMIT/ROLLBACK a mano (en autocommit, conn.commit() no hace nada)."""
    if not conn.closed and _en_transaccion(conn):
        with conn.cursor() as cursor:
            cursor.execute(sql)


def _devolver(conn):
    try:
        if conn.closed or conn.get_transaction_status() == _ROTA:
            conn.close()
            return
        _terminar(conn, "ROLLBACK")  # por si quedó una escritura sin commit
        _libres.put_nowait((conn, time.monotonic()))
    except queue.Full:
        conn.close()
    except psycopg2.Error:
        try:
            conn.close()
        except psycopg2.Error:
            pass


class _Cursor:
    """Cursor normal, salvo que antepone BEGIN a la primera escritura."""

    __slots__ = ("_cur", "_conn")

    def __init__(self, cur, conn):
        self._cur = cur
        self._conn = conn

    def __getattr__(self, nombre):
        return getattr(self._cur, nombre)

    def __iter__(self):
        return iter(self._cur)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._cur.close()
        return False

    def _necesita_begin(self, sql):
        texto = sql.decode() if isinstance(sql, bytes) else str(sql)
        return not _en_transaccion(self._conn) and _ES_ESCRITURA.match(texto)

    def execute(self, sql, params=None):
        if isinstance(sql, (str, bytes)) and self._necesita_begin(sql):
            sql = self._cur.mogrify(sql, params)
            return self._cur.execute(b"BEGIN; " + sql)
        return self._cur.execute(sql, params)

    def executemany(self, sql, lista):
        if isinstance(sql, (str, bytes)) and self._necesita_begin(sql):
            self._cur.execute("BEGIN")
        return self._cur.executemany(sql, lista)


class _ConexionDelPool:
    """Se usa igual que una conexión de psycopg2."""

    __slots__ = ("_conn",)

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, nombre):
        return getattr(self._conn, nombre)

    def cursor(self, *args, **kwargs):
        return _Cursor(self._conn.cursor(*args, **kwargs), self._conn)

    def commit(self):
        _terminar(self._conn, "COMMIT")

    def rollback(self):
        _terminar(self._conn, "ROLLBACK")

    def __enter__(self):
        return self

    def __exit__(self, tipo, *args):
        if tipo is None:
            self.commit()
        else:
            self.rollback()
        return False

    def close(self):
        conn, self._conn = self._conn, None
        if conn is not None:
            _devolver(conn)


# ---- Hilo que mantiene conexiones abiertas y vivas ---------------------------

def _mantener_conexiones():
    while True:
        try:
            revisadas = []
            while True:
                try:
                    revisadas.append(_libres.get_nowait())
                except queue.Empty:
                    break
            for conn, desde in revisadas:
                try:
                    if time.monotonic() - desde > _PING_CADA_SEG:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT 1")
                        desde = time.monotonic()
                    _libres.put_nowait((conn, desde))
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
            while _libres.qsize() < _MIN_LIBRES:
                _libres.put_nowait((_abrir_conexion(), time.monotonic()))
        except Exception:
            pass
        time.sleep(_PING_CADA_SEG / 2)


def _iniciar_hilo():
    global _hilo_iniciado
    with _lock_hilo:
        if not _hilo_iniciado:
            threading.Thread(target=_mantener_conexiones, daemon=True).start()
            _hilo_iniciado = True


def get_db_connection():
    if not _hilo_iniciado:
        _iniciar_hilo()
    while True:
        try:
            conn, _ = _libres.get_nowait()
        except queue.Empty:
            return _ConexionDelPool(_abrir_conexion())
        if conn.closed:
            continue
        return _ConexionDelPool(conn)