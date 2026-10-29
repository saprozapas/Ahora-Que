"""Cifra los números de cuenta bancaria que quedaron guardados sin cifrar.

Se corre UNA vez, después de aplicar migraciones/cuenta_bancaria_cifrada.sql y desplegar el código nuevo:

    python scripts/cifrar_cuentas_existentes.py

Es seguro correrlo más de una vez: solo toca las filas que todavía no empiezan con "enc1:".
Necesita en el .env: AHORAQUE_DB_URL y CHAT_MASTER_KEY (la misma clave que usa la app).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from database import get_db_connection, release_db_connection  # noqa: E402
from services.crypto_service import cifrar_campo  # noqa: E402
from services.deuda_service import _aad_cuenta  # noqa: E402


def main():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT "Id_Usuario", "Nro_Cuenta" FROM public."Cuenta_Bancaria" WHERE "Nro_Cuenta" NOT LIKE %s',
                ("enc1:%",),
            )
            filas = cur.fetchall()
            for user_id, numero in filas:
                cur.execute(
                    'UPDATE public."Cuenta_Bancaria" SET "Nro_Cuenta" = %s WHERE "Id_Usuario" = %s',
                    (cifrar_campo(numero, _aad_cuenta(user_id)), user_id),
                )
        conn.commit()
        print(f"Cuentas cifradas: {len(filas)}")
    except Exception:
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)


if __name__ == "__main__":
    main()
