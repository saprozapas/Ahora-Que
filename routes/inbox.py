from flask import Blueprint, flash, app, redirect, render_template, request, session, url_for
from services.invitation_service import InvitationService

inbox_bp = Blueprint("inbox", __name__)
invitation_service = InvitationService()

@inbox_bp.route("/inbox")
def inbox():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    invitaciones = invitation_service.get_invitations_for_user(session["user_id"])

    return render_template("inbox.html", logueado = True, invitaciones = invitaciones)

@inbox_bp.route("/invitaciones/<group_id>/rechazar", methods=["POST"])
def rechazar_invitacion(group_id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    try:
        invitation_service.reject_invitation(session["user_id"], group_id)
    except Exception as e:
        print(f"Error occurred while rejecting invitation: {e}")
        flash("Error al rechazar la invitación.")
    return redirect(url_for("inbox.inbox"))

@inbox_bp.route("/invitaciones/<group_id>/aceptar", methods=["POST"])
def aceptar_invitacion(group_id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    try:
        invitation_service.accept_invitation(session["user_id"], group_id)
        flash("Te has unido al grupo.")
    except Exception as e:
        print(f"Error occurred while accepting invitation: {e}")
        flash("Error al aceptar la invitación.")

    return redirect(url_for("inbox.inbox"))