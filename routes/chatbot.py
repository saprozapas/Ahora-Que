"""Endpoints JSON del chatbot para crear ideas de plan.

  GET  /chatbot/historial       mensajes de la conversación activa
  POST /chatbot/mensaje         {"mensaje": str, "grupo_id"?: str} -> respuesta del bot (+ borrador)
  POST /chatbot/confirmar_plan  {"mensaje_id": str, "grupo_id"?: str} -> guarda el borrador como idea

Con "grupo_id" (el chat usado desde un grupo) el bot sabe cuántos son, y al
guardar devuelve el link para postular la idea en ese grupo.
  POST /chatbot/nueva           borra la conversación y arranca de cero
"""
import json

import psycopg2
from cryptography.exceptions import InvalidTag
from flask import Blueprint, jsonify, request, session, url_for

import ia_bridge
from services.chatbot_service import historial_para_llm, procesar_mensaje_bot
from services.crypto_service import ClaveMaestraFaltante
from services.llm_service import LLMNoConfigurado
from services.plan_service import PlanService

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")
plan_service = PlanService()

MAX_LARGO_MENSAJE = 1000
LIMITE_HISTORIAL = 20


def _no_autorizado():
    return jsonify(error="Tenés que iniciar sesión."), 401


def _error(mensaje, codigo):
    return jsonify(error=mensaje), codigo


def _mensaje_para_cliente(mensaje):
    """Formato que usa el frontend: los borradores van como objeto."""
    dato = {"id": mensaje["id"], "role": mensaje["role"], "tipo": mensaje["tipo"]}
    if mensaje["tipo"] == "borrador":
        dato["borrador"] = dict(json.loads(mensaje["content"]), mensaje_id=mensaje["id"])
    else:
        dato["content"] = mensaje["content"]
    return dato


@chatbot_bp.errorhandler(ClaveMaestraFaltante)
@chatbot_bp.errorhandler(LLMNoConfigurado)
def _no_configurado(error):
    print(f"Chatbot sin configurar: {error}")
    return _error("El asistente no está configurado en este servidor.", 503)


@chatbot_bp.errorhandler(InvalidTag)
def _no_se_pudo_descifrar(error):
    # Un mensaje o la DEK no pasan la verificación de AES-GCM: se
    # modificaron en la base o cambió CHAT_MASTER_KEY.
    print("Chatbot: falló la verificación del cifrado (InvalidTag).")
    return _error("No se pudo leer la conversación. Empezá una nueva conversación.", 500)


@chatbot_bp.errorhandler(psycopg2.Error)
def _error_de_base(error):
    print(f"Chatbot, error de base de datos: {error}")
    return _error("El chat no puede acceder a la base de datos.", 500)


@chatbot_bp.route("/historial")
def historial():
    user_id = session.get("user_id")
    if not user_id:
        return _no_autorizado()

    conversacion = ia_bridge.obtener_conversacion_bot(user_id)
    if conversacion is None:
        return jsonify(mensajes=[])
    conv_id, dek = conversacion
    mensajes = ia_bridge.obtener_historial_desencriptado(conv_id, dek, limite=LIMITE_HISTORIAL)
    return jsonify(mensajes=[_mensaje_para_cliente(m) for m in mensajes])


@chatbot_bp.route("/mensaje", methods=["POST"])
def enviar_mensaje():
    user_id = session.get("user_id")
    if not user_id:
        return _no_autorizado()

    datos = request.get_json(silent=True) or {}
    texto_usuario = str(datos.get("mensaje") or "").strip()
    if not texto_usuario:
        return _error("El mensaje está vacío.", 400)
    if len(texto_usuario) > MAX_LARGO_MENSAJE:
        return _error(f"El mensaje puede tener hasta {MAX_LARGO_MENSAJE} caracteres.", 400)

    # Si el chat se usa desde un grupo, se verifica que sea miembro y se le
    # cuenta al bot cuántos son.
    grupo = None
    grupo_id = str(datos.get("grupo_id") or "").strip()
    if grupo_id:
        grupo = ia_bridge.contexto_grupo(user_id, grupo_id)
        if grupo is None:
            return _error("No sos parte de ese grupo.", 403)

    conv_id, dek = ia_bridge.obtener_o_crear_conversacion_bot(user_id)
    historial_guardado = ia_bridge.obtener_historial_desencriptado(conv_id, dek, limite=LIMITE_HISTORIAL)
    mensajes_llm = historial_para_llm(historial_guardado, grupo)
    mensajes_llm.append({"role": "user", "content": texto_usuario})

    # Mientras no haya un borrador en la conversación, un mensaje con algo de
    # contenido tiene que terminar en un plan (no en una tanda de preguntas).
    hay_borrador = any(m["tipo"] == "borrador" for m in historial_guardado)
    forzar_plan = not hay_borrador and len(texto_usuario.split()) >= 4

    try:
        respuesta, borrador = procesar_mensaje_bot(mensajes_llm, forzar_plan=forzar_plan)
    except (ClaveMaestraFaltante, LLMNoConfigurado):
        raise
    except Exception as e:
        print(f"Error del chatbot: {e}")
        return _error("El asistente no pudo responder. Probá de nuevo en un rato.", 502)

    # Se guarda todo junto recién cuando el bot respondió bien: así no
    # quedan mensajes del usuario sin respuesta en el historial.
    nuevos = [
        {"remitente": user_id, "rol": "user", "texto": texto_usuario, "tipo": "texto"},
        {"remitente": None, "rol": "assistant", "texto": respuesta, "tipo": "texto"},
    ]
    if borrador:
        nuevos.append({
            "remitente": None,
            "rol": "assistant",
            "texto": json.dumps(borrador, ensure_ascii=False, default=str),
            "tipo": "borrador",
        })
    ids = ia_bridge.guardar_mensajes(conv_id, dek, nuevos)

    return jsonify(
        respuesta=respuesta,
        borrador=dict(borrador, mensaje_id=ids[2]) if borrador else None,
    )


@chatbot_bp.route("/confirmar_plan", methods=["POST"])
def confirmar_plan():
    user_id = session.get("user_id")
    if not user_id:
        return _no_autorizado()

    datos = request.get_json(silent=True) or {}
    conversacion = ia_bridge.obtener_conversacion_bot(user_id)
    if conversacion is None:
        return _error("No hay ninguna conversación con el asistente.", 404)
    conv_id, dek = conversacion

    # El borrador se lee de la base (cifrado), no del navegador: el
    # cliente solo manda el id del mensaje.
    borrador = ia_bridge.obtener_borrador(conv_id, dek, datos.get("mensaje_id"))
    if borrador is None:
        return _error("No se encontró ese borrador.", 404)

    # Se vuelve a verificar por si algún lugar se borró desde que se propuso.
    ids = [lugar["id_lugar"] for lugar in borrador["lugares"]]
    existentes = ia_bridge.lugares_por_ids(ids)
    lugares = [
        {
            "id_lugar": id_lugar,
            "nombre": existentes[id_lugar]["nombre"],
            "nivel_precio": existentes[id_lugar]["nivel_precio"],
            "hora": lugar.get("hora"),
        }
        for lugar, id_lugar in zip(borrador["lugares"], ids)
        if id_lugar in existentes
    ]
    if not lugares:
        return _error("Los lugares de este borrador ya no existen. Pedile al asistente otra propuesta.", 409)

    try:
        plan_id = plan_service.crear_idea(
            user_id=user_id,
            nombre=borrador["nombre"],
            descripcion=borrador.get("descripcion") or None,
            lugares=lugares,
        )
    except Exception as e:
        print(f"Error al guardar la idea del chatbot: {e}")
        return _error("No se pudo guardar la idea. Intentá de nuevo.", 500)

    respuesta = {"status": "ok", "plan_id": str(plan_id), "url": url_for("planes.detalle", plan_id=plan_id)}

    # Desde un grupo: el link lleva a postular la idea recién creada.
    grupo_id = str(datos.get("grupo_id") or "").strip()
    if grupo_id and ia_bridge.contexto_grupo(user_id, grupo_id):
        respuesta["postular_url"] = url_for("grupo_planes.postular", group_id=grupo_id, idea_id=plan_id)
    return jsonify(respuesta)


@chatbot_bp.route("/nueva", methods=["POST"])
def nueva_conversacion():
    user_id = session.get("user_id")
    if not user_id:
        return _no_autorizado()
    ia_bridge.borrar_conversacion_bot(user_id)
    return jsonify(status="ok")
