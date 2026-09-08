import psycopg2
import os

#PASS de la BD: AhoraQue2026
# ---- CONEXIÓN A LA BASE DE DATOS (Supabase / PostgreSQL) ----
# Reemplazar esto con el connection string que da Supabase
# (Project Settings -> Database -> Connection String)


DB_URL = "postgresql://postgres.kmeggurdtvyvtyhpanox:AhoraQue2026@aws-0-us-east-2.pooler.supabase.com:6543/postgres"

def get_db_connection():
    return psycopg2.connect(DB_URL)