from database import get_db_connection, release_db_connection
from models.invitacion import Invitacion


class InvitationService:
    """Invitaciones a grupos. Cada método libera la conexión en un finally:
    si algo falla (por ejemplo una invitación repetida), la conexión vuelve
    igual al pool."""

    def invite_user(self, user_id, group_id, mensaje, nombre_invitante, conn=None):
        if conn is None:
            conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public."Invitaciones" ("Id_Usuario", "Id_Grupo", "Mensaje", "Nombre_invitante")
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, group_id, mensaje, nombre_invitante)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def get_invitations_for_user(self, user_id, conn=None):
        if conn is None:
            conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        i."Id_Grupo",
                        g."Nombre",
                        i."Mensaje",
                        i."Nombre_invitante"
                    FROM public."Invitaciones" i
                    JOIN public."Grupos" g ON i."Id_Grupo" = g."Id_Grupo"
                    WHERE i."Id_Usuario" = %s
                    """,
                    (user_id,)
                )
                return [
                    Invitacion(row[0], row[1], row[2], row[3])  # grupo, nombre del grupo, mensaje, invitante
                    for row in cursor.fetchall()
                ]
        finally:
            release_db_connection(conn)

    def reject_invitation(self, user_id, group_id, conn=None):
        if conn is None:
            conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM public."Invitaciones"
                    WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s
                    """,
                    (user_id, group_id)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def accept_invitation(self, user_id, group_id, conn=None):
        """Acepta una invitación PENDIENTE. Primero se borra la invitación y
        solo si existía se agrega al usuario al grupo: así nadie puede entrar
        a un grupo al que no lo invitaron. Si no hay invitación levanta
        ValueError con un mensaje para mostrar."""
        if conn is None:
            conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM public."Invitaciones"
                    WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s
                    """,
                    (user_id, group_id)
                )
                if cursor.rowcount == 0:
                    raise ValueError("No hay una invitación pendiente para ese grupo.")

                cursor.execute(
                    """
                    INSERT INTO public."Usuario-Grupo" ("Id_Usuario", "Id_Grupo")
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (user_id, group_id)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)