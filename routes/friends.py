from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
import psycopg2

from services.friend_service import FriendService
from services.invitation_service import InvitationService
from services.group_auth_service import GroupAuthService
from database_bridge.database_bridge import getFriendsForUser, getGroupsForUser, buscarUsuarios, getUser


friends_bp = Blueprint("friends", __name__)
friend_service = FriendService()
invitation_service = InvitationService()
group_auth_service = GroupAuthService()


def _require_login():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    return None


@friends_bp.route("/amigos")
def amigos():
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    uid = session["user_id"]
    friends = getFriendsForUser(uid)
    groups = getGroupsForUser(uid)

    return render_template("amigos.html", friends=friends, groups=groups, friends_page=True)


@friends_bp.route("/amigos/buscar")
def buscar_amigos():
    if not session.get("user_id"):
        return jsonify(resultados=[])

    consulta = request.args.get("q", "").strip()
    if len(consulta) < 2:
        return jsonify(resultados=[])

    resultados = buscarUsuarios(consulta, session["user_id"])
    return jsonify(resultados=resultados)


@friends_bp.route("/amigos/solicitar", methods=["POST"])
def solicitar_amistad():
    if not session.get("user_id"):
        return jsonify(ok=False, error="Tenés que iniciar sesión."), 401

    destinatario_id = request.form.get("user_id")
    if not destinatario_id:
        return jsonify(ok=False, error="Falta indicar a quién.")

    try:
        resultado = friend_service.send_request(session["user_id"], destinatario_id)
        if resultado == "amigos":
            return jsonify(ok=True, estado="amigos")
        return jsonify(ok=True, estado="solicitud_enviada")
    except ValueError as e:
        return jsonify(ok=False, error=str(e))
    except Exception:
        return jsonify(ok=False, error="Error al enviar la solicitud.")


@friends_bp.route("/amigos/<friend_id>/eliminar", methods=["POST"])
def eliminar_amigo(friend_id):
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    try:
        friend_service.remove_friend(session["user_id"], friend_id)
        flash("Amigo eliminado.")
    except Exception:
        flash("Error al eliminar al amigo.")

    return redirect(url_for("friends.amigos"))


@friends_bp.route("/amigos/<friend_id>/invitar-grupo", methods=["POST"])
def invitar_amigo_a_grupo(friend_id):
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    group_id = request.form.get("group_id")
    if not group_id:
        flash("Elegí un grupo para invitarlo.")
        return redirect(url_for("friends.amigos"))

    if not group_auth_service.is_user_in_group(session["user_id"], group_id):
        flash("Ese grupo no es tuyo.")
        return redirect(url_for("friends.amigos"))

    if group_auth_service.is_user_in_group(friend_id, group_id):
        flash("Tu amigo ya es miembro de ese grupo.")
        return redirect(url_for("friends.amigos"))

    nombre_invitante = getUser(session["user_id"]).get_name()

    try:
        invitation_service.invite_user(friend_id, group_id, None, nombre_invitante)
        flash("Invitación enviada.")
    except psycopg2.errors.UniqueViolation:
        flash("Tu amigo ya tiene una invitación pendiente para ese grupo.")
    except Exception:
        flash("Error al invitar a tu amigo al grupo.")

    return redirect(url_for("friends.amigos"))


@friends_bp.route("/amigos/solicitudes/<solicitante_id>/aceptar", methods=["POST"])
def aceptar_solicitud(solicitante_id):
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    try:
        friend_service.accept_request(solicitante_id, session["user_id"])
        flash("Ahora son amigos.")
    except Exception:
        flash("Error al aceptar la solicitud.")

    return redirect(url_for("inbox.inbox"))


@friends_bp.route("/amigos/solicitudes/<solicitante_id>/rechazar", methods=["POST"])
def rechazar_solicitud(solicitante_id):
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    try:
        friend_service.reject_request(solicitante_id, session["user_id"])
    except Exception:
        flash("Error al rechazar la solicitud.")

    return redirect(url_for("inbox.inbox"))
