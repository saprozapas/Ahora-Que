"""Rutas de los planes dentro de un grupo (postular, votar, horarios).

Todas redirigen de vuelta a la página del grupo con un mensaje."""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from services.grupo_encuesta_service import GrupoEncuestaService, opciones_de_distancia, opciones_de_precio
from services.grupo_plan_service import GrupoPlanError, GrupoPlanService
from services.lugar_service import LugarService
from services.plan_service import PlanService, capitalizar
from database_bridge.database_bridge import getGroupById, isUserInGroup
from services.notification_service import NotificationService

grupo_planes_bp = Blueprint("grupo_planes", __name__, url_prefix="/grupos/<group_id>")
grupo_plan_service = GrupoPlanService()
grupo_encuesta_service = GrupoEncuestaService()
lugar_service = LugarService()
plan_service = PlanService()
notification_service = NotificationService()


def _avisar_votacion(group_id, user_id, detalle):
    try:
        grupo = getGroupById(group_id)
        nombre_grupo = grupo.get_name()
        notification_service.notificar_grupo(
            group_id, user_id, f"El grupo {nombre_grupo} está votando",
            f"El grupo {nombre_grupo} está votando.\n\n{detalle}.",
        )
    except Exception:
        pass

MENSAJES_RESULTADO = {
    "confirmado": "¡Votaron todos y el plan quedó confirmado! Ya está en el calendario de los que pueden.",
    "rechazado": "Votaron todos: el plan no juntó suficientes \"me gusta\" y se descartó.",
    "esperando_horario": "El plan gustó, pero no pueden en ese horario. Propongan otro.",
}

MENSAJES_HORARIO = {
    "aprobado": "¡Horario aprobado! El plan quedó confirmado con esa fecha.",
    "rechazado": "El horario no juntó suficientes \"puedo\" y se descartó.",
}


MENSAJES_ENCUESTA = {
    "otros_planes": "Ganó «ninguna me convence»: se armaron otros planes para elegir.",
    "desempate": "Hubo empate: se vota de nuevo entre las opciones más votadas.",
    "plan_creado": "¡Ya hay plan elegido! Ahora el grupo vota si le gusta el plan y si puede en ese horario.",
    "cancelada": "Encuesta cancelada.",
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
                raise GrupoPlanError("Elegí un plan para proponer.")
            fecha, hora = _leer_fecha_hora()
            grupo_plan_service.postular_idea(group_id, user_id, idea_id, fecha, hora)
            _avisar_votacion(group_id, user_id, "Hay un plan nuevo para votar")
        except GrupoPlanError as e:
            error = str(e)
        except Exception as e:
            print(f"Error al postular idea: {e}")
            error = "No se pudo proponer el plan. Intentá de nuevo."
        else:
            flash("Plan propuesto: ahora el grupo lo vota.")
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
        me_gusta = _si_no("me_gusta")
        # Un plan sin fecha todavía no pregunta "¿podés?": el campo no viene.
        puedo = _si_no("puedo") if "puedo" in request.form else None
        return grupo_plan_service.votar_plan(group_id, plan_id, session["user_id"], me_gusta, puedo)
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
        resultado = grupo_plan_service.proponer_horario(group_id, plan_id, session["user_id"], fecha, hora)
        _avisar_votacion(group_id, session["user_id"], "Hay un horario nuevo para votar")
        return resultado
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


# --- Encuestas: armar un plan entre todos ---------------------------------------

@grupo_planes_bp.route("/encuestas/nueva", methods=["GET", "POST"])
def nueva_encuesta(group_id):
    """Una sola instancia: se completa el formulario, se arman las opciones y el grupo vota."""
    user_id = session["user_id"]
    if not isUserInGroup(user_id, group_id):
        return redirect(url_for("group_auth.grupos"))

    error = ""
    if request.method == "POST":
        try:
            fecha = request.form.get("fecha", "").strip()
            hora = request.form.get("hora", "").strip()
            try:
                fecha = datetime.strptime(fecha, "%Y-%m-%d").date() if fecha else None
                hora = datetime.strptime(hora, "%H:%M").time() if hora else None
            except ValueError:
                raise GrupoPlanError("El día o la hora no es válido.")
            nivel = request.form.get("nivel_precio", "").strip()
            if nivel not in ("", "1", "2", "3", "4", "5"):
                raise GrupoPlanError("El precio máximo no es válido.")
            grupo_encuesta_service.crear(
                group_id, user_id, capitalizar(request.form.get("titulo", "")), fecha, hora,
                nivel_precio=int(nivel) if nivel else None,
                tipos=request.form.getlist("tipos"),
                barrio=request.form.get("barrio", "").strip(),
                distancia_km=request.form.get("distancia_km", "").strip(),
            )
            _avisar_votacion(group_id, user_id, "Hay una encuesta nueva para votar")
        except GrupoPlanError as e:
            error = str(e)
        except Exception as e:
            print(f"Error al crear encuesta: {e}")
            error = "No se pudo crear la encuesta. Intentá de nuevo."
        else:
            flash("¡Listo! Se armaron opciones de plan: elijan una, o voten que ninguna les convence.")
            return _volver(group_id, "encuestas-grupo")

    return render_template(
        "grupo_encuesta_nueva.html",
        group=getGroupById(group_id),
        error=error,
        valores=request.form,
        tipos=lugar_service.listar_tipos(),
        opciones_precio=opciones_de_precio(),
        opciones_distancia=opciones_de_distancia(),
        hoy=datetime.now().date().isoformat(),
        groups_page=True,
    )


@grupo_planes_bp.route("/encuestas/<encuesta_id>/elegir", methods=["POST"])
def elegir_opcion(group_id, encuesta_id):
    def accion():
        opcion = request.form.get("opcion", "").strip()
        if not opcion:
            raise GrupoPlanError("Elegí una opción, o «ninguna me convence».")
        return grupo_encuesta_service.votar(
            group_id, encuesta_id, session["user_id"], None if opcion == "ninguna" else opcion)
    return _ejecutar(group_id, accion, "Voto guardado.", "encuestas-grupo", mensajes=MENSAJES_ENCUESTA)


@grupo_planes_bp.route("/encuestas/<encuesta_id>/cerrar", methods=["POST"])
def cerrar_encuesta(group_id, encuesta_id):
    return _ejecutar(
        group_id,
        lambda: grupo_encuesta_service.cerrar(group_id, encuesta_id, session["user_id"]),
        "Listo.", "encuestas-grupo", mensajes=MENSAJES_ENCUESTA,
    )


@grupo_planes_bp.route("/encuestas/<encuesta_id>/cancelar", methods=["POST"])
def cancelar_encuesta(group_id, encuesta_id):
    return _ejecutar(
        group_id,
        lambda: grupo_encuesta_service.cancelar(group_id, encuesta_id, session["user_id"]),
        "Encuesta cancelada.", "planes-grupo", mensajes=MENSAJES_ENCUESTA,
    )
