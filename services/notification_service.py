from services.mail_service import MailService
from flask import current_app, has_app_context
from database import get_db_connection, release_db_connection


def _registrar_error():
    if has_app_context():
        current_app.logger.exception("No se pudo enviar la notificación")


class NotificationService:
    """Envía notificaciones usando el canal de correo disponible actualmente."""

    def __init__(self, mail_service=None):
        self.mail_service = mail_service or MailService()

    def enviar(self, destino, subject, cuerpo):
        """Envía una notificación con la misma interfaz que MailService.enviar."""
        return self.mail_service.enviar(destino, subject, cuerpo)

    def preferencias(self, user_id):
        """Lee las preferencias de correo; si aún no hay fila, todas están activas."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT "Solicitudes_Amistad", "Invitaciones_Grupo", "Votos_Grupo", "Puntuar_Plan", "Menciones_Chat", '
                    '"Mail_Activo", "Dispositivo_Activo" '
                    'FROM public."Preferencias_Notificacion" WHERE "Id_Usuario" = %s',
                    (user_id,),
                )
                fila = cursor.fetchone()
                if fila:
                    return dict(zip(("amistad", "grupo", "votos", "puntuar", "menciones", "mail_activo", "dispositivo_activo"), fila))
                return {"amistad": True, "grupo": True, "votos": True, "puntuar": True, "menciones": True,
                        "mail_activo": True, "dispositivo_activo": False}
        finally:
            release_db_connection(conn)

    def guardar_preferencias(self, user_id, preferencias):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''INSERT INTO public."Preferencias_Notificacion"
                       ("Id_Usuario", "Solicitudes_Amistad", "Invitaciones_Grupo", "Votos_Grupo", "Puntuar_Plan", "Menciones_Chat", "Mail_Activo", "Dispositivo_Activo")
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT ("Id_Usuario") DO UPDATE SET
                         "Solicitudes_Amistad" = EXCLUDED."Solicitudes_Amistad",
                         "Invitaciones_Grupo" = EXCLUDED."Invitaciones_Grupo",
                         "Votos_Grupo" = EXCLUDED."Votos_Grupo",
                         "Puntuar_Plan" = EXCLUDED."Puntuar_Plan",
                         "Menciones_Chat" = EXCLUDED."Menciones_Chat",
                         "Mail_Activo" = EXCLUDED."Mail_Activo",
                         "Dispositivo_Activo" = EXCLUDED."Dispositivo_Activo"''',
                    (user_id, preferencias["amistad"], preferencias["grupo"],
                     preferencias["votos"], preferencias["puntuar"], preferencias["menciones"],
                     preferencias["mail_activo"], preferencias["dispositivo_activo"]),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            release_db_connection(conn)

    def notificar_usuario(self, user_id, tipo, subject, cuerpo, url="/dashboard", cuerpo_push=None):
        """Envía cada aviso por los canales activos y permitidos para esa categoría."""
        claves = {"amistad": "Solicitudes_Amistad", "grupo": "Invitaciones_Grupo",
                  "votos": "Votos_Grupo", "puntuar": "Puntuar_Plan", "menciones": "Menciones_Chat"}
        if tipo not in claves:
            raise ValueError("Tipo de notificación desconocido.")
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f'''SELECT u."Id_Usuario", u."Mail", COALESCE(p."Mail_Activo", true),
                               COALESCE(p."Dispositivo_Activo", false), COALESCE(p."{claves[tipo]}", true)
                        FROM public."Usuarios" u LEFT JOIN public."Preferencias_Notificacion" p
                          ON p."Id_Usuario" = u."Id_Usuario"
                        WHERE u."Id_Usuario" = %s''', (user_id,)
                )
                fila = cursor.fetchone()
        finally:
            release_db_connection(conn)
        if not fila:
            return False
        _, email, mail_activo, push_activo, categoria_activa = fila
        if not categoria_activa:
            return False
        enviado = False
        if mail_activo and email:
            try:
                self.enviar(email, subject, cuerpo)
                enviado = True
            except Exception:
                _registrar_error()
        if push_activo:
            from services.push_service import PushService
            enviado = bool(PushService().enviar_a_usuario(
                user_id, subject, cuerpo_push or cuerpo, url
            )) or enviado
        return enviado

    def notificar_grupo(self, group_id, actor_id, subject, cuerpo, url=None):
        """Notifica a los demás integrantes del grupo según su preferencia de votos (actor_id None: a todos)."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT ug."Id_Usuario"
                       FROM public."Usuario-Grupo" ug
                       WHERE ug."Id_Grupo" = %s AND ug."Id_Usuario" IS DISTINCT FROM %s::uuid''',
                    (group_id, actor_id),
                )
                destinatarios = cursor.fetchall()
        finally:
            release_db_connection(conn)
        enviados = 0
        for (destinatario_id,) in destinatarios:
            try:
                if self.notificar_usuario(
                    destinatario_id, "votos", subject, cuerpo,
                    url or f"/grupos/{group_id}", cuerpo_push=cuerpo.split("\n\n", 1)[0],
                ):
                    enviados += 1
            except Exception:
                _registrar_error()
        return enviados

    def notificar_resultado_plan(self, group_id, actor_id, plan_id, tipo, resultado):
        """Avisa al grupo (menos a quien disparó el resultado, que ya lo ve en pantalla) cómo terminó
        una votación.

        tipo "plan":    resultado "confirmado", "rechazado" o "esperando_horario" (votación del plan).
        tipo "horario": resultado "aprobado" o "rechazado" (votación de un horario propuesto).
        tipo "vencido": el plan se dio por vencido sin que nadie lo moviera (resultado se ignora).
        Nunca levanta error: un aviso que falla no tiene que romper el voto que ya se guardó."""
        try:
            from services.fechas import cuando

            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        '''SELECT p."Nombre", p."Fecha", p."Hora", g."Nombre"
                           FROM public."Plan" p JOIN public."Grupos" g ON g."Id_Grupo" = p."Grupo_id"
                           WHERE p."id_Plan" = %s''',
                        (plan_id,),
                    )
                    fila = cursor.fetchone()
            finally:
                release_db_connection(conn)
            if not fila:
                return 0
            nombre, fecha, hora, grupo = fila
            cuando_texto = cuando(fecha, hora)

            if (tipo, resultado) in (("plan", "confirmado"), ("horario", "aprobado")):
                asunto = f"Plan confirmado: {nombre} — {grupo}"
                detalle = f"{nombre} quedó confirmado" + (f" para {cuando_texto}" if cuando_texto else "") + "."
                cuerpo = f"{detalle}\n\nEntrá a la app para ver quiénes van."
            elif (tipo, resultado) == ("plan", "rechazado"):
                asunto = f"Plan descartado: {nombre} — {grupo}"
                cuerpo = f"{nombre} no juntó suficientes \"me gusta\" y se descartó.\n\nPueden proponer otro plan en el grupo."
            elif (tipo, resultado) == ("plan", "esperando_horario"):
                asunto = f"Falta definir el horario: {nombre} — {grupo}"
                cuerpo = (f"A la mayoría le gustó {nombre}, pero no alcanzan a ir en esa fecha.\n\n"
                          "Propongan otro horario desde el grupo.")
            elif (tipo, resultado) == ("horario", "rechazado"):
                asunto = f"Horario descartado: {nombre} — {grupo}"
                cuerpo = f"El horario propuesto para {nombre} no juntó suficientes \"puedo\".\n\nPropongan otro desde el grupo."
            elif tipo == "vencido":
                asunto = f"Plan vencido: {nombre} — {grupo}"
                cuerpo = f"{nombre} venció sin que el grupo lo decidiera.\n\nSi todavía les interesa, propónganlo de nuevo."
            else:
                return 0
            return self.notificar_grupo(group_id, actor_id, asunto, cuerpo, f"/grupos/{group_id}#plan-{plan_id}")
        except Exception:
            _registrar_error()
            return 0

    def notificar_asistentes(self, plan_id, subject, cuerpo):
        """Notifica a quienes confirmaron asistencia a un plan recién realizado."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT up."Usuario_id", p."Grupo_id"
                       FROM public."Usuario-Plan" up
                       JOIN public."Plan" p ON p."id_Plan" = up."Plan_id"
                       WHERE up."Plan_id" = %s AND up."Confirmado"''',
                    (plan_id,),
                )
                destinatarios = cursor.fetchall()
        finally:
            release_db_connection(conn)
        for user_id, group_id in destinatarios:
            try:
                self.notificar_usuario(
                    user_id, "puntuar", subject, cuerpo,
                    f"/grupos/{group_id}#plan-{plan_id}",
                    cuerpo_push=cuerpo.split("\n\n", 1)[0],
                )
            except Exception:
                _registrar_error()

    def notificar_menciones_chat(self, group_id, actor_id, mensaje):
        import re
        from services.chat_service import ChatService

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT u."Id_Usuario", u."Nombre", u."Username", g."Nombre", actor."Nombre"
                       FROM public."Usuario-Grupo" ug JOIN public."Usuarios" u ON u."Id_Usuario" = ug."Id_Usuario"
                       JOIN public."Grupos" g ON g."Id_Grupo" = ug."Id_Grupo"
                       JOIN public."Usuarios" actor ON actor."Id_Usuario" = %s
                       WHERE ug."Id_Grupo" = %s AND ug."Id_Usuario" <> %s''', (actor_id, group_id, actor_id)
                )
                destinatarios = cursor.fetchall()
        finally:
            release_db_connection(conn)
        for user_id, nombre, username, nombre_grupo, nombre_actor in destinatarios:
            handle = ChatService.handle(username, nombre)
            menciona_a_todos = any(
                re.search(rf"(?<![\w@])@{etiqueta}(?![\w])", mensaje, flags=re.IGNORECASE | re.UNICODE)
                for etiqueta in ("all", "todos")
            )
            menciona_a_esta_persona = re.search(
                rf"(?<![\w@])@{re.escape(handle)}(?![\w])", mensaje,
                flags=re.IGNORECASE | re.UNICODE,
            )
            if menciona_a_todos or menciona_a_esta_persona:
                try:
                    asunto = f"{nombre_actor} te mencionó en {nombre_grupo}"
                    cuerpo = f"{nombre_actor} te mencionó en el grupo {nombre_grupo}."
                    self.notificar_usuario(
                        user_id, "menciones", asunto, cuerpo,
                        f"/grupos/{group_id}/chat", cuerpo_push=cuerpo,
                    )
                except Exception:
                    _registrar_error()
