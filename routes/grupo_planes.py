"""Rutas de los planes dentro de un grupo (postular, votar, horarios).

Todas redirigen de vuelta a la página del grupo con un mensaje."""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from services.grupo_plan_service import GrupoPlanError, GrupoPlanService
from services.plan_service import PlanService
from database_bridge.database_bridge import getGroupById, isUserInGroup

grupo_planes_bp = Blueprint("grupo_planes", __name__, url_prefix="/grupos/<group_id>")
grupo_plan_service = GrupoPlanService()
plan_service = PlanService()

MENSAJES_RESULTADO = {
    "confirmado": "¡Votaron todos y el plan quedó confirmado! Ya está en el calendario de los que pueden.",
    "rechazado": "Votaron todos: la idea no juntó suficientes \"me gusta\" y se descartó.",
    "esperando_horario": "La idea gustó, pero no pueden en ese horario. Propongan otro.",
}

MENSAJES_HORARIO = {
    "aprobado": "¡Horario aprobado! El plan quedó confirmado con esa fecha.",
    "rechazado": "El horario no juntó suficientes \"puedo\" y se descartó.",
}


def _volver(group_id, ancla="planes-grupo"):
    return redirect(url_for("group_auth.detalle_grupo", group_id=group_id) + "#" + ancla)


def _leer_fecha_hora():
    """Lee fecha y hora del formulario y valida que sean futuras.
    Devuelve (fecha, hora) como texto o levanta GrupoPlanError."""
    fecha = request.form.get("fecha", "").strip()
    hora = request.form.get("hora", "").strip()
    if not fecha or not hora:
        raise GrupoPlanError("Elegí fecha y hora.")
    try:
        momento = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise GrupoPlanError("La fecha u hora no es válida.")
    if momento <= datetime.now():
        raise GrupoPlanError("Elegí una fecha y hora que todavía no pasó.")
    return fecha, hora


def _si_no(nombre):
    valor = request.form.get(nombre)
    if valor not in ("si", "no"):
        raise GrupoPlanError("Respondé las dos preguntas para votar.")
    return valor == "si"


@grupo_planes_bp.before_request
def _requiere_sesion():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))


# --- Postular una idea ---------------------------------------------------------

@grupo_planes_bp.route("/postular", methods=["GET", "POST"])
def postular(group_id):
    user_id = session["user_id"]
    if not isUserInGroup(user_id, group_id):
        return redirect(url_for("group_auth.grupos"))

    error = ""
    if request.method == "POST":
        try:
            idea_id = request.form.get("idea_id", "").strip()
            if not idea_id:
                raise GrupoPlanError("Elegí una idea para postular.")
            fecha, hora = _leer_fecha_hora()
            grupo_plan_service.postular_idea(group_id, user_id, idea_id, fecha, hora)
        except GrupoPlanError as e:
            error = str(e)
        except Exception as e:
            print(f"Error al postular idea: {e}")
            error = "No se pudo postular la idea. Intentá de nuevo."
        else:
            flash("Idea postulada: ahora el grupo la vota.")
            return _volver(group_id)

    return render_template(
        "grupo_postular.html",
        group=getGroupById(group_id),
        ideas=plan_service.get_ideas_postulables(user_id),
        error=error,
        valores=request.form if request.method == "POST" else request.args,
        hoy=datetime.now().date().isoformat(),
        groups_page=True,
    )


@grupo_planes_bp.route("/asistente")
def asistente(group_id):
    """Crear una idea con el asistente para postularla en este grupo."""
    user_id = session["user_id"]
    if not isUserInGroup(user_id, group_id):
        return redirect(url_for("group_auth.grupos"))
    return render_template(
        "grupo_asistente.html",
        group=getGroupById(group_id),
        groups_page=True,
    )


# --- Votación del plan ------------------------------------------------------

def _ejecutar(group_id, accion, ok="Listo.", ancla="planes-grupo", mensajes=MENSAJES_RESULTADO):
    """Corre la acción, muestra el mensaje que corresponda y vuelve al grupo."""
    try:
        resultado = accion()
    except GrupoPlanError as e:
        flash(str(e))
    except Exception as e:
        print(f"Error en plan de grupo: {e}")
        flash("Algo salió mal. Intentá de nuevo.")
    else:
        flash(mensajes.get(resultado, ok))
    return _volver(group_id, ancla)


@grupo_planes_bp.route("/planes/<plan_id>/votar", methods=["POST"])
def votar(group_id, plan_id):
    def accion():
        return grupo_plan_service.votar_plan(
            group_id, plan_id, session["user_id"], _si_no("me_gusta"), _si_no("puedo")
        )
    return _ejecutar(group_id, accion, "Voto guardado.", f"plan-{plan_id}")


@grupo_planes_bp.route("/planes/<plan_id>/cerrar", methods=["POST"])
def cerrar(group_id, plan_id):
    return _ejecutar(
        group_id,
        lambda: grupo_plan_service.cerrar_votacion(group_id, plan_id, session["user_id"]),
        "Votación cerrada.",
    )


# --- Horarios -----------------------------------------------------------------

@grupo_planes_bp.route("/planes/<plan_id>/horarios", methods=["POST"])
def proponer_horario(group_id, plan_id):
    def accion():
        fecha, hora = _leer_fecha_hora()
        return grupo_plan_service.proponer_horario(group_id, plan_id, session["user_id"], fecha, hora)
    return _ejecutar(group_id, accion, "Horario propuesto: ahora lo vota el grupo.",
                     f"plan-{plan_id}", mensajes=MENSAJES_HORARIO)


@grupo_planes_bp.route("/horarios/<int:horario_id>/votar", methods=["POST"])
def votar_horario(group_id, horario_id):
    def accion():
        return grupo_plan_service.votar_horario(
            group_id, horario_id, session["user_id"], _si_no("puedo")
        )
    return _ejecutar(group_id, accion, "Voto guardado.", mensajes=MENSAJES_HORARIO)


@grupo_planes_bp.route("/horarios/<int:horario_id>/cerrar", methods=["POST"])
def cerrar_horario(group_id, horario_id):
    return _ejecutar(
        group_id,
        lambda: grupo_plan_service.cerrar_horario(group_id, horario_id, session["user_id"]),
        "Todavía nadie votó ese horario.",
        mensajes=MENSAJES_HORARIO,
    )