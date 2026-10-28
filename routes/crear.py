"""Un solo camino para crear: + Crear → ¿Con quién? → cómo armarlo.

GET /crear            elegir dónde: uno de tus grupos o "solo yo"
GET /crear/<destino>  elegir cómo: con el asistente (principal) o las otras formas, según el destino ("yo" o el id de un grupo)
"""

from flask import Blueprint, abort, redirect, render_template, session, url_for

from database_bridge.database_bridge import getGroupById, getGroupsForUser, isUserInGroup
from services.plan_service import PlanService

crear_bp = Blueprint("crear", __name__)
plan_service = PlanService()


@crear_bp.route("/crear")
def elegir_destino():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    grupos = getGroupsForUser(session["user_id"])
    try:
        borradores = len(plan_service.get_planes_guardados(session["user_id"]))
    except Exception as e:
        print(f"No se pudieron contar los borradores: {e}")
        borradores = 0
    return render_template("crear.html", grupos=grupos, borradores=borradores)


@crear_bp.route("/crear/<destino>")
def elegir_forma(destino):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    grupo = None
    if destino != "yo":
        if not isUserInGroup(session["user_id"], destino):
            abort(404)
        grupo = getGroupById(destino)
    return render_template("crear_como.html", grupo=grupo, destino=destino)
