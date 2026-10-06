

from flask import Blueprint, jsonify, request, session
from services.chat_service import ChatService


chat = Blueprint("chat", __name__)
chat_service = ChatService()


@chat.route("/grupos/<group_id>/chat", methods=["GET"])
def obtener_mensajes(group_id):

    mensajes = chat_service.obtener_mensajes(group_id)

    return jsonify({
        "mensajes": mensajes
    })


@chat.route("/grupos/<group_id>/chat", methods=["POST"])
def enviar_mensaje(group_id):

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "error": "No estás logueado."
        }), 401

    datos = request.get_json()

    mensaje = datos.get("mensaje", "").strip()

    if not mensaje:
        return jsonify({
            "error": "El mensaje está vacío."
        }), 400

    chat_service.crear_mensaje(
        group_id,
        user_id,
        mensaje
    )

    return jsonify({
        "ok": True
    })