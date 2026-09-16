from flask import Blueprint, render_template, request, redirect, session, url_for, flash
import psycopg2
from models.group import Group
from services.invitation_service import InvitationService
from services.group_auth_service import GroupAuthService
from werkzeug.security import generate_password_hash
from services.auth_service import AuthService
from database_bridge.database_bridge import getUser, getGroupsForUser, isUserInGroup, getGroupById


group_auth = Blueprint("group_auth", __name__)
group_auth_service = GroupAuthService()
auth_service = AuthService()
invitation_service = InvitationService()

def _require_login():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    return None


@group_auth.route("/grupos")
def grupos():
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    grupos = getGroupsForUser(session.get("user_id"))# getGroups no devuelve grupos con usuario asignado.
    for grupo in grupos:
        grupo.set_user(getUser(session.get("user_id")))

    return render_template("grupos.html", groups=grupos, groups_page=True)


@group_auth.route("/grupos/nuevo", methods=["GET", "POST"])
def nuevo_grupo():
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        form_data = request.form.to_dict()
        user_id = session.get("user_id")
        name = form_data["name"]
        description = form_data["description"]
        try:
            user = getUser(user_id)
        except Exception as e:
            return render_template("crear_grupos.html", error="Error al crear grupo. Intenta loguearte nuevamente.", form_data=form_data)

        try:
            if name.strip() == "":
                raise psycopg2.errors.NotNullViolation("El nombre del grupo no puede estar vacío.")
            group_auth_service.register(Group(user, name, description), user_id)
        except psycopg2.errors.NotNullViolation as e:
            return render_template("crear_grupos.html", error="Debes ingresar el nombre del grupo.", form_data=form_data)
        except Exception as e:
            return render_template("crear_grupos.html", error="Error al crear el grupo.", form_data=form_data)

        return render_template("crear_grupos.html", error="Grupo creado exitosamente.", form_data={})

    return render_template("crear_grupos.html", 
                           error=None, 
                           form_data={})


@group_auth.route("/grupos/<group_id>")
def detalle_grupo(group_id):
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    if not isUserInGroup(session.get("user_id"), group_id):
        return redirect(url_for("group_auth.grupos"))

    group = getGroupById(group_id)
    group.set_user(getUser(session.get("user_id")))
    return render_template("grupo.html", group=group, groups_page=True)

@group_auth.route("/grupos/<group_id>/invitar", methods=["POST"])
def invitar_usuario(group_id):
    username = request.form.get("username")
    mensaje = request.form.get("mensaje")
    nombre_invitante = getUser(session.get("user_id")).get_name()
    resultado = auth_service.getUserAndId(username)
    
    if resultado is None:
        flash("Usuario no encontrado.")
        return redirect(
        url_for("group_auth.detalle_grupo", group_id=group_id)
        )
    x, user_id = resultado
    
    try:
        invitation_service.invite_user(user_id, group_id, mensaje, nombre_invitante)
        flash("Usuario invitado exitosamente.")
        
    except Exception as e:
        flash("Error al invitar al usuario.")
  
    return redirect(url_for("group_auth.detalle_grupo", group_id=group_id))


