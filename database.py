import os

from psycopg2 import pool

# ---- CONEXIÓN A LA BASE DE DATOS (Supabase / PostgreSQL) ----
DB_URL = os.environ.get(
    "AHORAQUE_DB_URL",
    "postgresql://postgres.kmeggurdtvyvtyhpanox:AhoraQue2026@aws-0-us-east-2.pooler.supabase.com:6543/postgres",
)

connection_pool = pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=DB_URL
)

def get_db_connection():
    return connection_pool.getconn()

def release_db_connection(conn):
    connection_pool.putconn(conn)