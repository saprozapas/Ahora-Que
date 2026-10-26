from flask import Blueprint, jsonify, request, session
from services.chat_service import ChatService
from database_bridge.database_bridge import isUserInGroup
from services.group_auth_service import GroupAuthService
import ia_bridge


chat = Blueprint("chat", __name__)

# Mismo tope que el chatbot (routes/chatbot.py).
MAX_LARGO_MENSAJE = 1000
chat_service = ChatService()
group_auth_service = GroupAuthService()


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
    # Mientras la conversación está abierta, lo que llega se da por leído (las menciones dejan de avisar en el Inicio).
    chat_service.marcar_visto(user_id, group_id)

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


@chat.route("/grupos/<group_id>/chat/limpiar", methods=["POST"])
def limpiar_chat(group_id):
    """Dos modos:
      "todo"  vacía todos los mensajes del grupo (solo admins) y la
              conversación de quien lo pide con el bot.
      "bot"   borra la conversación con el bot y los mensajes que mencionan
              a @AhoraQue. Cada integrante borra los suyos; un admin, todos."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "No estás logueado."}), 401
    if not isUserInGroup(user_id, group_id):
        return jsonify({"error": "No sos integrante de este grupo."}), 403

    modo = str((request.get_json(silent=True) or {}).get("modo", "")).strip()
    if modo not in ("todo", "bot"):
        return jsonify({"error": "Opción no válida."}), 400

    es_admin, _ = group_auth_service.get_rol(user_id, group_id)
    puede_todo = bool(es_admin)
    if modo == "todo" and not puede_todo:
        return jsonify({"error": "Solo los admins del grupo pueden vaciar todo el chat."}), 403

    try:
        if modo == "todo":
            borrados = chat_service.eliminar_mensajes(group_id)
        else:
            borrados = chat_service.eliminar_mensajes(
                group_id, solo_bot=True, de_usuario=None if puede_todo else user_id
            )
        ia_bridge.borrar_conversacion_bot(user_id)
    except Exception:
        return jsonify({"error": "No se pudo limpiar el chat. Intentá de nuevo."}), 500

    return jsonify({"ok": True, "borrados": borrados})