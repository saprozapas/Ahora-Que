"""Mide la latencia de red a la base: python scripts/medir_db.py"""
import os
import time

import psycopg2

inicio = time.perf_counter()
conn = psycopg2.connect(os.environ["AHORAQUE_DB_URL"], connect_timeout=10)
conn.autocommit = True
print(f"conectar: {(time.perf_counter() - inicio) * 1000:.0f} ms")
cur = conn.cursor()
for _ in range(5):
    inicio = time.perf_counter()
    cur.execute("SELECT 1")
    print(f"SELECT 1: {(time.perf_counter() - inicio) * 1000:.0f} ms")