from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request, session

from services.push_service import PushService


push_bp = Blueprint("push", __name__, url_prefix="/notificaciones/push")
push_service = PushService()


def _same_origin():
    """Bloquea envíos cross-site a los endpoints autenticados de suscripciones."""
    origin = request.headers.get("Origin")
    if origin:
        return urlsplit(origin).netloc.casefold() == request.host.casefold()
    referer = request.headers.get("Referer")
    return bool(referer and urlsplit(referer).netloc.casefold() == request.host.casefold())


@push_bp.route("/suscripciones", methods=["POST"])
def guardar_suscripcion():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(ok=False, error="Iniciá sesión para activar notificaciones."), 401
    if not _same_origin():
        return jsonify(ok=False, error="Origen no permitido."), 403
    if not current_app.config.get("VAPID_PRIVATE_KEY"):
        return jsonify(ok=False, error="Las notificaciones en dispositivo todavía no están configuradas en el servidor."), 503

    datos = request.get_json(silent=True) or {}
    suscripcion = datos.get("subscription")
    if not isinstance(suscripcion, dict):
        return jsonify(ok=False, error="Falta la suscripción del dispositivo."), 400
    try:
        push_service.guardar_suscripcion(user_id, suscripcion)
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 400
    except Exception:
        current_app.logger.exception("No se pudo guardar la suscripción Web Push.")
        return jsonify(ok=False, error="No se pudo registrar este dispositivo."), 500
    return jsonify(ok=True)


@push_bp.route("/suscripciones", methods=["DELETE"])
def eliminar_suscripcion():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(ok=False, error="Iniciá sesión para administrar notificaciones."), 401
    if not _same_origin():
        return jsonify(ok=False, error="Origen no permitido."), 403

    datos = request.get_json(silent=True) or {}
    try:
        push_service.eliminar_suscripcion(user_id, datos.get("endpoint"))
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 400
    except Exception:
        current_app.logger.exception("No se pudo borrar la suscripción Web Push.")
        return jsonify(ok=False, error="No se pudo quitar este dispositivo."), 500
    return jsonify(ok=True)
