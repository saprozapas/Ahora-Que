"""Limpieza de los datos de prueba que dejan los flujos (prefijo "ZZ Sereno").

Solo toca filas de grupos cuyo nombre empieza con "ZZ Sereno" y que ya no tienen
integrantes, y de planes/ideas con ese prefijo. Descubre solo las tablas que
cuelgan de esos ids (columnas Id_Grupo / Grupo_id / Id_Plan / Id_Conversacion) y
las muestra con su recuento. Con "ver" (predeterminado) no borra nada; con
"borrar" ejecuta los DELETE hijo-primero y confirma con un recuento final.

Uso (desde la raiz del repo, con el .env cargado):
    python redesign-screens/herramientas/limpieza_bd.py ver
    python redesign-screens/herramientas/limpieza_bd.py borrar
"""
import os, sys
sys.path.insert(0, os.getcwd())
from database import get_db_connection, release_db_connection

MODO = sys.argv[1] if len(sys.argv) > 1 else "ver"
PREFIJO = "ZZ Sereno%"

conn = get_db_connection()
cur = conn.cursor()


def columnas(nombres):
    cur.execute("""SELECT table_name, column_name FROM information_schema.columns
                   WHERE table_schema = 'public' AND column_name = ANY(%s)""", (nombres,))
    return cur.fetchall()


try:
    cur.execute("""SELECT g."Id_Grupo", g."Nombre",
                          (SELECT COUNT(*) FROM public."Usuario-Grupo" ug WHERE ug."Id_Grupo" = g."Id_Grupo")
                   FROM public."Grupos" g WHERE g."Nombre" LIKE %s""", (PREFIJO,))
    grupos = cur.fetchall()
    gids = [g[0] for g in grupos]
    print("Grupos de prueba:", [(str(i)[:8], n, "integrantes=%d" % m) for i, n, m in grupos])
    cur.execute('SELECT "id_Plan" FROM public."Plan" WHERE "Nombre" LIKE %s OR "Grupo_id" = ANY(%s)', (PREFIJO, gids or [None]))
    pids = [r[0] for r in cur.fetchall()]
    print("Planes/ideas de prueba:", len(pids))
    cur.execute('SELECT "Id_Conversacion" FROM public."Conversacion" WHERE "Id_Grupo" = ANY(%s)', (gids or [None],))
    cids = [r[0] for r in cur.fetchall()]
    print("Conversaciones del grupo:", len(cids))
    cur.execute('SELECT "Id_Encuesta" FROM public."Grupo_Encuesta" WHERE "Id_Grupo" = ANY(%s)', (gids or [None],))
    eids = [r[0] for r in cur.fetchall()]
    print("Encuestas del grupo:", len(eids))

    objetivos = []  # (tabla, columna, ids)
    for t, c in columnas(["Id_Grupo"]):
        if t not in ("Grupos",):
            objetivos.append((t, c, gids))
    for t, c in columnas(["Grupo_id"]):
        objetivos.append((t, c, gids))
    for t, c in columnas(["Id_Plan", "id_Plan", "Plan_id"]):
        if t != "Plan":
            objetivos.append((t, c, pids))
    for t, c in columnas(["Id_Conversacion"]):
        if t != "Conversacion":
            objetivos.append((t, c, cids))
    for t, c in columnas(["Id_Encuesta"]):
        if t != "Grupo_Encuesta":
            objetivos.append((t, c, eids))
    vistos = set(); filtrados = []
    for t, c, ids in objetivos:
        if (t, c) in vistos or not ids:
            continue
        vistos.add((t, c)); filtrados.append((t, c, ids))
    print("\nTablas con filas de prueba:")
    for t, c, ids in filtrados:
        cur.execute(f'SELECT COUNT(*) FROM public."{t}" WHERE "{c}" = ANY(%s)', (ids,))
        n = cur.fetchone()[0]
        if n:
            print(f"   {t}.{c}: {n}")
    if MODO != "borrar":
        print("\n(modo ver: no se borra nada)")
        sys.exit(0)

    con_miembros = [g for g in grupos if g[2] != 0]
    if con_miembros:
        print("ATENCION: hay grupos de prueba con integrantes; no se borra nada:", [g[1] for g in con_miembros])
        sys.exit(1)

    pendientes = [(t, c, ids) for t, c, ids in filtrados]
    for pasada in range(1, 7):
        siguientes = []
        for t, c, ids in pendientes:
            cur.execute("SAVEPOINT s")
            try:
                cur.execute(f'DELETE FROM public."{t}" WHERE "{c}" = ANY(%s)', (ids,))
                if cur.rowcount:
                    print(f"   pasada {pasada}: {t}.{c} -> {cur.rowcount} filas")
            except Exception as ex:
                cur.execute("ROLLBACK TO SAVEPOINT s")
                siguientes.append((t, c, ids))
        pendientes = siguientes
        if not pendientes:
            break
    for tabla, col, ids in (("Conversacion", "Id_Conversacion", cids), ("Grupo_Encuesta", "Id_Encuesta", eids), ("Plan", "id_Plan", pids), ("Grupos", "Id_Grupo", gids)):
        if ids:
            cur.execute(f'DELETE FROM public."{tabla}" WHERE "{col}" = ANY(%s)', (ids,))
            print(f"   {tabla}: {cur.rowcount} filas")
    conn.commit()
    cur.execute('SELECT COUNT(*) FROM public."Grupos" WHERE "Nombre" LIKE %s', (PREFIJO,)); g = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM public."Plan" WHERE "Nombre" LIKE %s', (PREFIJO,)); p = cur.fetchone()[0]
    print(f"\nquedan: grupos={g} planes={p}; tablas sin poder borrar: {[(t, c) for t, c, _ in pendientes]}")
except SystemExit:
    raise
except Exception:
    conn.rollback()
    raise
finally:
    release_db_connection(conn)
