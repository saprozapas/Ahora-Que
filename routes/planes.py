from flask import Blueprint, abort, redirect, render_template, session, url_for
from services.plan_service import PlanService

planes_bp = Blueprint("planes", __name__, url_prefix="/planes")
plan_service = PlanService()


def _sin_sesion():
    return not session.get("user_id")


@planes_bp.route("/")
def menu():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    return render_template("planes_menu.html")


@planes_bp.route("/confirmados")
def confirmados():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    planes = plan_service.get_planes_confirmados(session["user_id"])
    return render_template(
        "planes_lista.html",
        titulo="Planes confirmados",
        subtitulo="Los planes que ya confirmaste, en orden de fecha.",
        planes=planes,
        mostrar_fecha=True,
        vacio="Todavía no confirmaste ningún plan.",
    )


@planes_bp.route("/grupo")
def de_grupo():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    planes = plan_service.get_planes_grupo(session["user_id"])
    return render_template(
        "planes_lista.html",
        titulo="Planes de grupo",
        subtitulo="Planes que van a pasar en tus grupos y todavía no confirmaste.",
        planes=planes,
        mostrar_fecha=True,
        vacio="No hay planes de grupo pendientes de confirmar.",
    )


@planes_bp.route("/guardados")
def guardados():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    planes = plan_service.get_planes_guardados(session["user_id"])
    return render_template(
        "planes_lista.html",
        titulo="Planes guardados",
        subtitulo="Ideas de plan que guardaste para más adelante.",
        planes=planes,
        mostrar_fecha=False,
        vacio="No guardaste ningún plan todavía.",
    )


@planes_bp.route("/historial")
def historial():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    planes = plan_service.get_historial(session["user_id"])
    return render_template(
        "planes_lista.html",
        titulo="Historial de planes",
        subtitulo="Planes confirmados a los que fuiste en los últimos 3 meses.",
        planes=planes,
        mostrar_fecha=True,
        vacio="No tenés planes en tu historial reciente.",
    )


@planes_bp.route("/<plan_id>")
def detalle(plan_id):
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    plan = plan_service.get_plan_detalle(plan_id, session["user_id"])
    if plan is None:
        abort(404)
    return render_template("plan_detalle.html", plan=plan)
