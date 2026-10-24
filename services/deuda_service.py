from decimal import Decimal, InvalidOperation

import psycopg2

from database import get_db_connection, release_db_connection

CENTAVO = Decimal("0.01")
_MAX_EXACTO = 12  # hasta acá se busca el mínimo exacto de transferencias


def parsear_monto(texto):
    """'1250,50' o '1250.50' (vacío = 0) -> Decimal con 2 decimales."""
    try:
        monto = Decimal((texto or "").strip().replace(",", ".") or "0").quantize(CENTAVO)
    except InvalidOperation:
        raise ValueError("Poné un monto válido.")
    if not monto.is_finite() or monto < 0 or monto >= 10 ** 9:
        raise ValueError("Poné un monto válido.")
    return monto


# ---------------------------------------------------------------------------
# Cálculo: quién le paga a quién con la menor cantidad de transferencias
# ---------------------------------------------------------------------------

def _saldar(grupo):
    """Un grupo cuyos saldos suman 0: el que más debe le paga al que más espera.
    Cada paso deja a alguien en 0, así que son como mucho (personas - 1)."""
    deben = [[-s, u] for u, s in grupo if s < 0]
    reciben = [[s, u] for u, s in grupo if s > 0]
    pagos = []
    while deben:
        d = max(deben, key=lambda x: x[0])
        c = max(reciben, key=lambda x: x[0])
        m = min(d[0], c[0])
        pagos.append((d[1], c[1], m))
        d[0] -= m
        c[0] -= m
        deben = [x for x in deben if x[0]]
        reciben = [x for x in reciben if x[0]]
    return pagos


def _grupos_que_cierran(activos):
    """Parte a las personas en la mayor cantidad posible de grupos que suman 0
    entre sí (cada grupo de k personas se salda con k-1 pagos, así que más
    grupos = menos pagos). DP sobre subconjuntos."""
    n = len(activos)
    suma = [Decimal(0)] * (1 << n)
    for m in range(1, 1 << n):
        suma[m] = suma[m & (m - 1)] + activos[(m & -m).bit_length() - 1][1]
    mejor = [0] * (1 << n)
    for m in range(1, 1 << n):
        mejor[m] = max(mejor[m ^ (1 << i)] for i in range(n) if m >> i & 1) + (suma[m] == 0)
    orden, m = [], (1 << n) - 1
    while m:
        i = next(i for i in range(n)
                 if m >> i & 1 and mejor[m ^ (1 << i)] + (suma[m] == 0) == mejor[m])
        orden.append(i)
        m ^= 1 << i
    grupos, actual, acum = [], [], Decimal(0)
    for i in reversed(orden):
        actual.append(activos[i])
        acum += activos[i][1]
        if acum == 0:
            grupos.append(actual)
            actual = []
    return grupos


def transferencias_minimas(saldos):
    """saldos: {usuario: pagó - gastó} (suma 0). -> [(deudor, acreedor, monto)]."""
    activos = [(str(u), s) for u, s in saldos.items() if s != 0]
    # ponytail: con más de _MAX_EXACTO personas se salda todo junto (puede salir
    # alguna transferencia de más); la búsqueda exacta crece como 2^n.
    grupos = _grupos_que_cierran(activos) if len(activos) <= _MAX_EXACTO else [activos]
    return [p for g in grupos for p in _saldar(g)]


def _plata(n):
    return "$" + f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _par(a, b):
    return sorted([str(a).lower(), str(b).lower()])


class DeudaService:

    # ----- consultas -------------------------------------------------------

    def contar_que_debo(self, user_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT count(*) FROM public."Deuda" '
                    'WHERE ("Id_Usuario1" = %s AND "Saldo" > 0) OR ("Id_Usuario2" = %s AND "Saldo" < 0)',
                    (user_id, user_id))
                return cur.fetchone()[0]
        finally:
            release_db_connection(conn)

    def listar(self, user_id):
        """{'debo': [...], 'me_deben': [...]} para la pantalla. Los datos bancarios
        solo viajan en lo que DEBO: se los ve quien tiene que transferir."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u."Id_Usuario", u."Nombre",
                           CASE WHEN d."Id_Usuario1" = %s THEN d."Saldo" ELSE -d."Saldo" END,
                           c."Banco", c."Nro_Cuenta"
                    FROM public."Deuda" d
                    JOIN public."Usuarios" u ON u."Id_Usuario" =
                         CASE WHEN d."Id_Usuario1" = %s THEN d."Id_Usuario2" ELSE d."Id_Usuario1" END
                    LEFT JOIN public."Cuenta_Bancaria" c ON c."Id_Usuario" = u."Id_Usuario"
                    WHERE d."Id_Usuario1" = %s OR d."Id_Usuario2" = %s
                    ORDER BY u."Nombre"
                    """, (user_id,) * 4)
                filas = [{"id": str(r[0]), "nombre": r[1], "monto": r[2], "banco": r[3], "cuenta": r[4]}
                         for r in cur.fetchall()]
                # monto > 0: yo le debo a esa persona; monto < 0: ella me debe a mí
                debo = [f for f in filas if f["monto"] > 0]
                me_deben = [dict(f, monto=-f["monto"], banco=None, cuenta=None) for f in filas if f["monto"] < 0]
                return {"debo": debo, "me_deben": me_deben}
        finally:
            release_db_connection(conn)

    def candidatos(self, user_id, id_grupo=None):
        """A quién se puede sumar: integrantes del grupo, o amigos."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                if id_grupo:
                    cur.execute(
                        'SELECT 1 FROM public."Usuario-Grupo" WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s',
                        (user_id, id_grupo))
                    if not cur.fetchone():
                        raise ValueError("No sos parte de ese grupo.")
                    cur.execute(
                        """SELECT u."Id_Usuario", u."Nombre" FROM public."Usuarios" u
                           JOIN public."Usuario-Grupo" g ON g."Id_Usuario" = u."Id_Usuario"
                           WHERE g."Id_Grupo" = %s AND u."Id_Usuario" <> %s ORDER BY u."Nombre" """,
                        (id_grupo, user_id))
                else:
                    cur.execute(
                        """SELECT u."Id_Usuario", u."Nombre" FROM public."Usuarios" u
                           JOIN public."Amistades" a ON u."Id_Usuario" =
                                CASE WHEN a."Id_Usuario1" = %s THEN a."Id_Usuario2" ELSE a."Id_Usuario1" END
                           WHERE a."Id_Usuario1" = %s OR a."Id_Usuario2" = %s ORDER BY u."Nombre" """,
                        (user_id, user_id, user_id))
                return [{"id": str(r[0]), "nombre": r[1]} for r in cur.fetchall()]
        finally:
            release_db_connection(conn)

    # ----- escrituras ------------------------------------------------------

    def crear_reparto(self, user_id, descripcion, montos, id_grupo=None):
        """montos: {id_usuario: (gasto, pago)} de TODOS los que participan (el
        creador carga lo de todos). Valida, calcula y actualiza las deudas en el
        momento. Devuelve cuántas transferencias quedaron."""
        descripcion = (descripcion or "").strip() or None  # el nombre es opcional
        if descripcion and len(descripcion) > 100:
            raise ValueError("El nombre puede tener hasta 100 letras.")
        yo = str(user_id).lower()
        montos = {str(u).lower(): m for u, m in montos.items()}
        montos.setdefault(yo, (Decimal(0), Decimal(0)))
        permitidos = {c["id"].lower() for c in self.candidatos(user_id, id_grupo)} | {yo}
        if len(montos) < 2 or not set(montos) <= permitidos:
            raise ValueError("Elegí al menos una persona de la lista.")
        gastado = sum(g for g, _ in montos.values())
        pagado = sum(p for _, p in montos.values())
        if gastado != pagado:
            raise ValueError(f"Lo gastado ({_plata(gastado)}) y lo pagado ({_plata(pagado)}) no coinciden.")
        if gastado == 0:
            raise ValueError("Cargá cuánto se gastó.")

        pagos = transferencias_minimas({u: p - g for u, (g, p) in montos.items()})
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO public."Deuda_Reparto" ("Id_Creador", "Id_Grupo", "Descripcion", "Calculado") '
                    'VALUES (%s, %s, %s, true) RETURNING "Id_Reparto"',
                    (user_id, id_grupo or None, descripcion))
                rid = cur.fetchone()[0]
                cur.executemany(
                    'INSERT INTO public."Deuda_Reparto_Participante" ("Id_Reparto", "Id_Usuario", "Gasto", "Pago") '
                    'VALUES (%s, %s, %s, %s)',
                    [(rid, u, g, p) for u, (g, p) in montos.items()])
                for deudor, acreedor, monto in pagos:
                    self._sumar_deuda(cur, deudor, acreedor, monto)
            conn.commit()
            return len(pagos)
        except psycopg2.Error:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    @staticmethod
    def _sumar_deuda(cur, deudor, acreedor, monto):
        """Una sola fila por par: si ya había deuda se suma o se resta con signo,
        y si el resultado cambia de signo, se invierten deudor y acreedor. Si queda
        en 0 se borra la fila (la tabla no admite Saldo = 0, así que no se puede
        hacer UPDATE a 0)."""
        u1, u2 = _par(deudor, acreedor)
        delta = monto if str(deudor).lower() == u1 else -monto
        cur.execute('SELECT "Saldo" FROM public."Deuda" WHERE "Id_Usuario1" = %s AND "Id_Usuario2" = %s FOR UPDATE',
                    (u1, u2))
        fila = cur.fetchone()
        if fila and fila[0] + delta == 0:
            cur.execute('DELETE FROM public."Deuda" WHERE "Id_Usuario1" = %s AND "Id_Usuario2" = %s', (u1, u2))
        else:
            cur.execute(
                'INSERT INTO public."Deuda" ("Id_Usuario1", "Id_Usuario2", "Saldo") VALUES (%s, %s, %s) '
                'ON CONFLICT ("Id_Usuario1", "Id_Usuario2") DO UPDATE SET "Saldo" = public."Deuda"."Saldo" + EXCLUDED."Saldo"',
                (u1, u2, delta))

    # ----- cuenta bancaria (se edita en el perfil) -------------------------

    def get_cuenta(self, user_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT "Banco", "Nro_Cuenta" FROM public."Cuenta_Bancaria" WHERE "Id_Usuario" = %s',
                            (user_id,))
                fila = cur.fetchone()
                return {"banco": fila[0], "cuenta": fila[1]} if fila else {"banco": "", "cuenta": ""}
        finally:
            release_db_connection(conn)

    def guardar_cuenta(self, user_id, banco, cuenta):
        """Los dos vacíos borran la cuenta; si se completa uno, hay que completar el otro."""
        banco, cuenta = (banco or "").strip(), (cuenta or "").strip()
        if not banco and not cuenta:
            sql, params = 'DELETE FROM public."Cuenta_Bancaria" WHERE "Id_Usuario" = %s', (user_id,)
        elif not banco or not cuenta:
            raise ValueError("Completá el banco y el número de cuenta.")
        elif len(banco) > 60 or len(cuenta) > 40:
            raise ValueError("El banco admite hasta 60 letras y la cuenta hasta 40.")
        else:
            sql = ('INSERT INTO public."Cuenta_Bancaria" ("Id_Usuario", "Banco", "Nro_Cuenta") VALUES (%s, %s, %s) '
                   'ON CONFLICT ("Id_Usuario") DO UPDATE SET "Banco" = EXCLUDED."Banco", "Nro_Cuenta" = EXCLUDED."Nro_Cuenta"')
            params = (user_id, banco, cuenta)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        except psycopg2.Error:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def marcar_pagada(self, acreedor_id, deudor_id, monto):
        """Solo el acreedor salda. El monto es el que vio en pantalla: si mientras
        tanto la deuda cambió, no se borra."""
        u1, u2 = _par(acreedor_id, deudor_id)
        esperado = monto if str(deudor_id).lower() == u1 else -monto
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'DELETE FROM public."Deuda" WHERE "Id_Usuario1" = %s AND "Id_Usuario2" = %s AND "Saldo" = %s',
                    (u1, u2, esperado))
                if cur.rowcount == 0:
                    raise ValueError("La deuda cambió, revisá el monto.")
            conn.commit()
        except (psycopg2.Error, ValueError):
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)


if __name__ == "__main__":
    D = Decimal
    # A pagó todo (90) y gastaron 30 cada uno: B y C le pagan 30 a A (2 pagos)
    assert sorted(transferencias_minimas({"a": D(60), "b": D(-30), "c": D(-30)})) == \
        [("b", "a", D(30)), ("c", "a", D(30))]
    # caso donde pagar "el mayor al mayor" da 5 pagos y lo mínimo es 4
    sal = dict(zip("abcdef", map(D, [-8, 6, -2, 3, 4, -3])))
    assert len(_saldar(list(sal.items()))) == 5 and len(transferencias_minimas(sal)) == 4
    assert transferencias_minimas({"a": D(0), "b": D(0)}) == []
    assert parsear_monto("1250,5") == D("1250.50") and parsear_monto("") == 0
    print("ok")
