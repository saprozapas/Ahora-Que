from database import get_db_connection
from models.invitacion import Invitacion


class InvitationService:
    def invite_user(self, user_id, group_id, mensaje, nombre_invitante, conn=None):
            if conn is None:
                conn = get_db_connection()
            cursor = conn.cursor()
        
            cursor.execute(
                """
                INSERT INTO public."Invitaciones" ("Id_usuario", "Id_grupo", "Mensaje", "Nombre_invitante")
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
                i."Id_grupo", 
                g."Nombre", 
                i."Mensaje", 
                i."Nombre_invitante"
            FROM public."Invitaciones" i
            JOIN public."Grupos" g ON i."Id_grupo" = g."Id_Grupo"
            WHERE i."Id_usuario" = %s
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