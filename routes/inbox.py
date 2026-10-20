from flask import Blueprint, flash, app, redirect, render_template, request, session, url_for
from services.invitation_service import InvitationService
from services.friend_service import FriendService
from services.social_service import SocialService

inbox_bp = Blueprint("inbox", __name__)
invitation_service = InvitationService()
friend_service = FriendService()
social_service = SocialService()

@inbox_bp.route("/inbox")
def inbox():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    user_id = session["user_id"]
    invitaciones = invitation_service.get_invitations_for_user(user_id)
    solicitudes_amistad = friend_service.get_requests_for_user(user_id)

    # Dos pestañas: "Solicitudes" (amistades e invitaciones a grupos) y
    # "Publicaciones" (me gusta y comentarios de lo que publicaste).
    try:
        avisos = social_service.listar_avisos(user_id)
    except Exception as e:
        print(f"No se pudieron leer los avisos de publicaciones: {e}")
        avisos = []
    avisos_nuevos = sum(1 for a in avisos if a["no_leida"])
    pendientes = len(invitaciones) + len(solicitudes_amistad)

    tab = request.args.get("tab")
    if tab not in ("solicitudes", "publicaciones"):
        # Sin pedir una pestaña: la de solicitudes, salvo que no haya nada
        # pendiente ahí y sí avisos nuevos.
        tab = "publicaciones" if (avisos_nuevos and not pendientes) else "solicitudes"

    if tab == "publicaciones" and avisos_nuevos:
        # Abrir la pestaña los da por vistos; esta vez se muestran marcados como
        # nuevos y la próxima ya no.
        try:
            social_service.marcar_avisos_leidos(user_id)
        except Exception as e:
            print(f"No se pudieron marcar los avisos como leídos: {e}")

    return render_template(
        "inbox.html",
        logueado=True,
        tab=tab,
        invitaciones=invitaciones,
        solicitudes_amistad=solicitudes_amistad,
        pendientes=pendientes,
        avisos=avisos,
        avisos_nuevos=avisos_nuevos,
    )

@inbox_bp.route("/invitaciones/<group_id>/rechazar", methods=["POST"])
def rechazar_invitacion(group_id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    try:
        invitation_service.reject_invitation(session["user_id"], group_id)
    except Exception as e:
        print(f"Error occurred while rejecting invitation: {e}")
        flash("Error al rechazar la invitación.")
    return redirect(url_for("inbox.inbox", tab="solicitudes"))

@inbox_bp.route("/invitaciones/<group_id>/aceptar", methods=["POST"])
def aceptar_invitacion(group_id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    try:
        invitation_service.accept_invitation(session["user_id"], group_id)
        flash("Te has unido al grupo.")
    except ValueError as e:
        flash(str(e))
    except Exception as e:
        print(f"Error occurred while accepting invitation: {e}")
        flash("Error al aceptar la invitación.")

    return redirect(url_for("inbox.inbox", tab="solicitudes"))



#####       ACEPTAR FRIENDS ESTA EN friends.py         ##########