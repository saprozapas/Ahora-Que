from flask import Blueprint, app, redirect, render_template, request, session, url_for
from services.invitation_service import InvitationService

inbox_bp = Blueprint("inbox", __name__)
invitation_service = InvitationService()

@inbox_bp.route("/inbox")
def inbox():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    invitaciones = invitation_service.get_invitations_for_user(session["user_id"])

    return render_template("inbox.html", logueado = True, invitaciones = invitaciones)