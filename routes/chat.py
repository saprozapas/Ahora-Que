from flask import Blueprint, jsonify, request, session
from services.chat_service import ChatService
from database_bridge.database_bridge import isUserInGroup


chat = Blueprint("chat", __name__)

# Mismo tope que el chatbot (routes/chatbot.py).
MAX_LARGO_MENSAJE = 1000
chat_service = ChatService()


# La página del chat vive en /grupos/<id>/chat (routes/group_auth.py):
# estas dos rutas solo sirven y reciben los mensajes en JSON.

@chat.route("/grupos/<group_id>/chat/mensajes", methods=["GET"])
def obtener_mensajes(group_id):

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "No estás logueado."}), 401

    if not isUserInGroup(user_id, group_id):
        return jsonify({"error": "No sos integrante de este grupo."}), 403

    mensajes = chat_service.obtener_mensajes(group_id)

    return jsonify({
        "mensajes": mensajes
    })


@chat.route("/grupos/<group_id>/chat/mensajes", methods=["POST"])
def enviar_mensaje(group_id):

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "error": "No estás logueado."
        }), 401

    if not isUserInGroup(user_id, group_id):
        return jsonify({"error": "No sos integrante de este grupo."}), 403

    datos = request.get_json(silent=True) or {}

    mensaje = str(datos.get("mensaje", "")).strip()

    if not mensaje:
        return jsonify({
            "error": "El mensaje está vacío."
        }), 400

    if len(mensaje) > MAX_LARGO_MENSAJE:
        return jsonify({
            "error": f"El mensaje puede tener hasta {MAX_LARGO_MENSAJE} caracteres."
        }), 400

    try:
        chat_service.crear_mensaje(
            group_id,
            user_id,
            mensaje
        )
    except Exception:
        return jsonify({
            "error": "No se pudo enviar el mensaje. Intentá de nuevo."
        }), 500

    return jsonify({
        "ok": True
    })