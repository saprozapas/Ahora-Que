"""Lo que espera tu respuesta en el Inicio: avisos de votaciones de todos tus grupos.

GET /inicio/pendientes   el panel ya armado (HTML), para refrescarlo cada pocos segundos

Solo avisa: cada tarjeta lleva al grupo (a la votación, al horario, a la encuesta o a la puntuación).
Votar se hace ahí, no en el Inicio. El Inbox queda para las solicitudes y los avisos de publicaciones."""

from flask import Blueprint, jsonify, make_response, render_template, session

from services.grupo_plan_service import GrupoPlanService

inicio_bp = Blueprint("inicio", __name__, url_prefix="/inicio")
grupo_plan_service = GrupoPlanService()


@inicio_bp.route("/pendientes")
def pendientes():
    if not session.get("user_id"):
        return jsonify({"ok": False, "error": "Tu sesión venció. Volvé a iniciar sesión."}), 401
    try:
        datos = grupo_plan_service.get_pendientes(session["user_id"])
    except Exception as e:
        print(f"No se pudieron leer los pendientes: {e}")
        return jsonify({"ok": False, "error": "No se pudieron cargar tus votaciones."}), 500
    respuesta = make_response(render_template("_inicio_pendientes.html", p=datos))
    respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["X-Pendientes"] = str(datos["total"])
    return respuesta
