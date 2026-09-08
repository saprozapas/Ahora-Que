import psycopg2
import os

#PASS de la BD: AhoraQue2026
# ---- CONEXIÓN A LA BASE DE DATOS (Supabase / PostgreSQL) ----
# Reemplazar esto con el connection string que da Supabase
# (Project Settings -> Database -> Connection String)


DB_URL = os.environ.get("postgresql://postgres:AhoraQue2026@db.kmeggurdtvyvtyhpanox.supabase.co:5432/postgres")

def get_db_connection():
    return psycopg2.connect(DB_URL)