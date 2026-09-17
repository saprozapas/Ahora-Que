from database import get_db_connection
from models.invitacion import Invitacion


class InvitationService:
    def invite_user(self, user_id, group_id, mensaje, nombre_invitante, conn=None):
            if conn is None:
                conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO public."Invitaciones" ("Id_Usuario", "Id_Grupo", "Mensaje", "Nombre_invitante")
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, group_id, mensaje, nombre_invitante)
            )
            
    
            conn.commit()
    
            cursor.close()
            conn.close()

    def get_invitations_for_user(self, user_id, conn=None):

        if conn is None:
            conn = get_db_connection()

        cursor = conn.cursor()

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

        rows = cursor.fetchall()

        invitations = []

        for row in rows:
            invitation = Invitacion(
                row[0],  # Id_grupo
                row[1],  # Nombre del grupo
                row[2],  # Mensaje
                row[3]   # Nombre invitante
            )

            invitations.append(invitation)

        cursor.close()

        conn.close()

        return invitations

    def reject_invitation(self, user_id, group_id, conn=None):
        if conn is None:
            conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM public."Invitaciones"
            WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s
            """,
            (user_id, group_id)
        )

        conn.commit()
        cursor.close()
        conn.close()

    def accept_invitation(self, user_id, group_id, conn=None):
        if conn is None:
            conn = get_db_connection()

        cursor = conn.cursor()

        # Add the user to the group
        cursor.execute(
            """
            INSERT INTO public."Usuario-Grupo" ("Id_Usuario", "Id_Grupo")
            VALUES (%s, %s)
            """,
            (user_id, group_id)
        )

        # Remove the invitation
        cursor.execute(
            """
            DELETE FROM public."Invitaciones"
            WHERE "Id_Usuario" = %s AND "Id_Grupo" = %s
            """,
            (user_id, group_id)
        )

        conn.commit()
        cursor.close()
        conn.close()