import psycopg2

from database import get_db_connection
from models.solicitud_amistad import SolicitudAmistad


class FriendService:

    def send_request(self, from_id, to_id):
        """Manda una solicitud de amistad. Si el destinatario ya te había
        mandado una a vos, en vez de duplicarla se confirma la amistad
        directamente."""

        if str(from_id) == str(to_id):
            raise ValueError("No podés agregarte a vos mismo.")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            id_menor, id_mayor = sorted([str(from_id).lower(), str(to_id).lower()])

            cursor.execute(
                'SELECT EXISTS (SELECT 1 FROM public."Amistades" WHERE "Id_Usuario1" = %s AND "Id_Usuario2" = %s)',
                (id_menor, id_mayor)
            )
            if cursor.fetchone()[0]:
                raise ValueError("Ya son amigos.")

            cursor.execute(
                'SELECT 1 FROM public."Solicitudes_Amistad" WHERE "Id_Solicitante" = %s AND "Id_Destinatario" = %s',
                (to_id, from_id)
            )
            if cursor.fetchone():
                cursor.execute(
                    'DELETE FROM public."Solicitudes_Amistad" WHERE "Id_Solicitante" = %s AND "Id_Destinatario" = %s',
                    (to_id, from_id)
                )
                cursor.execute(
                    'INSERT INTO public."Amistades" ("Id_Usuario1", "Id_Usuario2") VALUES (%s, %s)',
                    (id_menor, id_mayor)
                )
                conn.commit()
                return "amigos"

            cursor.execute(
                'INSERT INTO public."Solicitudes_Amistad" ("Id_Solicitante", "Id_Destinatario") VALUES (%s, %s)',
                (from_id, to_id)
            )
            conn.commit()
            return "solicitud_enviada"

        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise ValueError("Ya le enviaste una solicitud a este usuario.")
        except psycopg2.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def get_requests_for_user(self, user_id, conn=None):
        cerrar_conexion = conn is None
        if conn is None:
            conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT s."Id_Solicitante", u."Nombre", u."Username", s."Fecha"
            FROM public."Solicitudes_Amistad" s
            JOIN public."Usuarios" u ON u."Id_Usuario" = s."Id_Solicitante"
            WHERE s."Id_Destinatario" = %s
            ORDER BY s."Fecha" DESC
            """,
            (user_id,)
        )

        rows = cursor.fetchall()

        solicitudes = [
            SolicitudAmistad(row[0], row[1], row[2], row[3])
            for row in rows
        ]

        cursor.close()
        if cerrar_conexion:
            conn.close()

        return solicitudes

    def accept_request(self, from_id, to_id):
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'DELETE FROM public."Solicitudes_Amistad" WHERE "Id_Solicitante" = %s AND "Id_Destinatario" = %s',
                (from_id, to_id)
            )
            if cursor.rowcount == 0:
                raise ValueError("Esa solicitud ya no existe.")

            id_menor, id_mayor = sorted([str(from_id).lower(), str(to_id).lower()])
            cursor.execute(
                'INSERT INTO public."Amistades" ("Id_Usuario1", "Id_Usuario2") VALUES (%s, %s) ON CONFLICT DO NOTHING',
                (id_menor, id_mayor)
            )
            conn.commit()
        except psycopg2.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def reject_request(self, from_id, to_id):
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'DELETE FROM public."Solicitudes_Amistad" WHERE "Id_Solicitante" = %s AND "Id_Destinatario" = %s',
                (from_id, to_id)
            )
            conn.commit()
        except psycopg2.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def remove_friend(self, uid1, uid2):
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            id_menor, id_mayor = sorted([str(uid1).lower(), str(uid2).lower()])
            cursor.execute(
                'DELETE FROM public."Amistades" WHERE "Id_Usuario1" = %s AND "Id_Usuario2" = %s',
                (id_menor, id_mayor)
            )
            conn.commit()
        except psycopg2.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
