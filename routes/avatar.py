"""Foto de perfil.

GET  /avatar/<user_id>   la imagen de ese usuario (la subida, o el avatar genérico que eligió); 404 si no eligió
POST /perfil/avatar      cambia la propia: {"tipo": "preset", "preset": 1-5} | {"tipo": "foto", "datos": "data:image/jpeg;base64,…"}
                         | {"tipo": "quitar"}
"""

import base64
import binascii
import uuid

from flask import Blueprint, abort, jsonify, make_response, redirect, request, session, url_for

from services.avatar_service import AvatarError, AvatarService

avatar_bp = Blueprint("avatar", __name__)
avatar_service = AvatarService()


@avatar_bp.route("/avatar/<user_id>")
def ver_avatar(user_id):
    if not session.get("user_id"):
        abort(401)
    try:
        user_id = str(uuid.UUID(user_id))
    except ValueError:
        abort(404)

    avatar = avatar_service.obtener(user_id)
    if avatar is None:
        abort(404)

    if avatar["tipo"] == "preset":
        respuesta = redirect(url_for("static", filename=f"avatares/avatar-{avatar['preset']}.svg", v=avatar["version"]), code=302)
        respuesta.headers["Cache-Control"] = "private, max-age=31536000, immutable"   # la dirección lleva ?v=: no cambia mientras no cambie la foto
        return respuesta

    respuesta = make_response(avatar["datos"])
    respuesta.headers["Content-Type"] = "image/jpeg"
    # La dirección lleva ?v=<versión>: al cambiar la foto cambia la dirección, así que puede cachearse sin miedo.
    respuesta.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return respuesta


@avatar_bp.route("/perfil/avatar", methods=["POST"])
def cambiar_avatar():
    if not session.get("user_id"):
        return jsonify({"ok": False, "error": "Tu sesión venció."}), 401

    datos = request.get_json(silent=True) or {}
    tipo = datos.get("tipo")
    user_id = session["user_id"]

    try:
        if tipo == "preset":
            version = avatar_service.elegir_preset(user_id, datos.get("preset"))
        elif tipo == "foto":
            crudo = str(datos.get("datos") or "")
            if "," in crudo:
                crudo = crudo.split(",", 1)[1]
            try:
                bytes_foto = base64.b64decode(crudo, validate=True)
            except (binascii.Error, ValueError):
                raise AvatarError("La foto no se pudo leer.")
            version = avatar_service.subir_foto(user_id, bytes_foto)
        elif tipo == "quitar":
            avatar_service.quitar(user_id)
            version = None
        else:
            raise AvatarError("Elegí una foto.")
    except AvatarError as e:
        return jsonify({"ok": False, "error": str(e)}), e.codigo
    except Exception as e:
        print(f"No se pudo cambiar la foto de perfil: {e}")
        return jsonify({"ok": False, "error": "No se pudo guardar la foto. Intentá de nuevo."}), 500

    session["avatar_v"] = version or 0
    return jsonify({"ok": True, "version": version, "url": f"/avatar/{user_id}?v={version}" if version else None})
