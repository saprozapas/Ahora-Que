from datetime import date

from flask import Blueprint, jsonify, render_template, request, redirect, session, url_for, flash
import psycopg2
from models.group import Group
from services.invitation_service import InvitationService
from services.group_auth_service import GroupAuthService
from werkzeug.security import generate_password_hash
from services.auth_service import AuthService
from services.grupo_plan_service import GrupoPlanService
from services.plan_service import PlanService
from services.grupo_encuesta_service import GrupoEncuestaService, MAX_FRANJAS, opciones_de_precio
from services.lugar_service import LugarService
from database_bridge.database_bridge import getUser, getGroupsForUser, getUsersInGroup, getUsersInGroupWithIds, isUserInGroup, getGroupById, buscarUsuariosInvitables


group_auth = Blueprint("group_auth", __name__)
group_auth_service = GroupAuthService()
auth_service = AuthService()
invitation_service = InvitationService()
grupo_plan_service = GrupoPlanService()
plan_service = PlanService()
grupo_encuesta_service = GrupoEncuestaService()
lugar_service = LugarService()

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
    usuario = getUser(session.get("user_id"))  # una sola consulta, no una por grupo
    for grupo in grupos:
        grupo.set_user(usuario)

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
            group_id = group_auth_service.register(Group(user, name, description), user_id)
        except psycopg2.errors.NotNullViolation as e:
            return render_template("crear_grupos.html", error="Debes ingresar el nombre del grupo.", form_data=form_data)
        except Exception as e:
            return render_template("crear_grupos.html", error="Error al crear el grupo.", form_data=form_data)

        flash("Grupo creado. Invitá a tus amigos para empezar a armar planes.")
        return redirect(url_for("group_auth.detalle_grupo", group_id=group_id))

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
    users = getUsersInGroupWithIds(group_id)
    plan_service.archivar_vencidos()
    tablero = grupo_plan_service.get_tablero(group_id, session.get("user_id"))
    encuestas = grupo_encuesta_service.get_abiertas(group_id, session.get("user_id"))
    return render_template("grupo.html", group=group, groups_page=True, users=users,
                           seccion="planes", tablero=tablero, hoy=date.today().isoformat(),
                           encuestas=encuestas,
                           tipos=lugar_service.listar_tipos() if encuestas else [],
                           opciones_precio=opciones_de_precio(), max_franjas=MAX_FRANJAS)


@group_auth.route("/grupos/<group_id>/chat")
def chat_grupo(group_id):
    """Página del chat del grupo (los mensajes en sí los sirve routes/chat.py)."""
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    if not isUserInGroup(session.get("user_id"), group_id):
        return redirect(url_for("group_auth.grupos"))

    group = getGroupById(group_id)
    group.set_user(getUser(session.get("user_id")))
    return render_template("grupo_chat.html", group=group, groups_page=True,
                           users=getUsersInGroupWithIds(group_id), seccion="chat")


@group_auth.route("/grupos/<group_id>/invitables")
def usuarios_invitables(group_id):
    """Buscador del modal de invitar: sin texto, tus amigos; con texto,
    cualquier usuario por nombre o username."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(resultados=[]), 401
    if not isUserInGroup(user_id, group_id):
        return jsonify(resultados=[]), 403

    consulta = request.args.get("q", "").strip()
    if consulta and len(consulta) < 2:
        return jsonify(resultados=[])
    return jsonify(resultados=buscarUsuariosInvitables(group_id, user_id, consulta))


@group_auth.route("/grupos/<group_id>/invitar", methods=["POST"])
def invitar_usuario(group_id):
    """Invita a alguien al grupo. Desde el modal llega por fetch con el id de
    la persona elegida y responde JSON, así un error se muestra ahí mismo
    sin sacarte de la página. Sin JavaScript sigue andando por username."""
    es_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    def responder(ok, mensaje):
        if es_ajax:
            return jsonify(ok=ok, mensaje=mensaje)
        flash(mensaje)
        return redirect(url_for("group_auth.detalle_grupo", group_id=group_id))

    user_id_sesion = session.get("user_id")
    if not user_id_sesion:
        if es_ajax:
            return jsonify(ok=False, mensaje="Tenés que iniciar sesión."), 401
        return redirect(url_for("auth.login"))
    if not isUserInGroup(user_id_sesion, group_id):
        if es_ajax:
            return jsonify(ok=False, mensaje="No sos integrante de este grupo."), 403
        return redirect(url_for("group_auth.grupos"))

    mensaje = request.form.get("mensaje")
    nombre_invitante = getUser(user_id_sesion).get_name()

    user_id = request.form.get("user_id", "").strip()
    if not user_id:
        resultado = auth_service.getUserAndId(request.form.get("username", "").strip())
        if resultado is None:
            return responder(False, "Usuario no encontrado.")
        _, user_id = resultado

    if group_auth_service.is_user_in_group(user_id, group_id):
        return responder(False, "Esa persona ya es miembro del grupo.")

    try:
        invitation_service.invite_user(user_id, group_id, mensaje, nombre_invitante)
    except psycopg2.errors.UniqueViolation:
        return responder(False, "Esa persona ya tiene una invitación pendiente para este grupo.")
    except Exception as e:
        print(f"Error al invitar al grupo: {e}")
        return responder(False, "Error al invitar. Intentá de nuevo.")

    return responder(True, "Invitación enviada.")


@group_auth.route("/grupos/<group_id>/editar-grupo", methods=["POST"])
def editar_grupo(group_id):
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    if not isUserInGroup(session.get("user_id"), group_id):
        return redirect(url_for("group_auth.grupos"))

    nombre = (request.form.get("nombre") or "").strip()
    descripcion = request.form.get("descripcion")

    if not nombre:
        flash("El nombre del grupo no puede estar vacío.")
        return redirect(url_for("group_auth.detalle_grupo", group_id=group_id))

    try:
        group_auth_service.update_group(group_id, nombre, descripcion)
        flash("Grupo actualizado exitosamente.")
    except Exception as e:
        print(f"Error al actualizar el grupo: {e}")
        flash("Error al actualizar el grupo.")

    return redirect(url_for("group_auth.detalle_grupo", group_id=group_id))

@group_auth.route("/grupos/<group_id>/eliminar-grupo", methods=["POST"])
def abandonar_grupo(group_id):
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    if not isUserInGroup(session.get("user_id"), group_id):
        return redirect(url_for("group_auth.grupos"))

    try:
        group_auth_service.delete_user_from_group(group_id, session.get("user_id"))
        flash("Grupo abandonado exitosamente.")
    except Exception as e:
        print(f"Error al abandonar el grupo: {e}")
        flash("Error al abandonar el grupo.")

    return redirect(url_for("group_auth.grupos"))