"""Endpoints JSON del feed social.

La página /social vive en app.py; acá están solo las rutas que usa
static/social.js. Todas devuelven JSON, piden sesión y validan que los ids
sean UUID (un id mal formado llegaría a la base y daría un error 500).

Las reglas de quién puede qué viven en services/social_service.py.
"""

import uuid

from flask import Blueprint, jsonify, request, session

from services.social_service import SocialError, SocialService


social_api = Blueprint("social_api", __name__, url_prefix="/social")

social_service = SocialService()


def _error(mensaje, estado):
    return jsonify({"error": mensaje}), estado


def _id_o_404(valor):
    try:
        return str(uuid.UUID(str(valor)))
    except ValueError:
        raise SocialError("No encontramos eso.", 404)


def _cuerpo():
    """Los POST de acá solo se aceptan como JSON.

    Un formulario de otro sitio no puede mandar application/json sin pasar
    por un permiso del navegador (CORS), así que exigirlo evita que una
    página ajena dispare acciones con la sesión de la persona.
    """
    datos = request.get_json(silent=True) if request.is_json else None
    if not isinstance(datos, dict):
        raise SocialError("La solicitud no es válida.", 415)
    return datos


def _con_sesion(funcion):
    """Pide sesión y traduce SocialError a una respuesta JSON."""
    def envoltura(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return _error("Iniciá sesión para continuar.", 401)
        try:
            return funcion(user_id, *args, **kwargs)
        except SocialError as e:
            return _error(e.mensaje, e.estado)
        except Exception:
            return _error("Algo salió mal. Intentá de nuevo.", 500)
    envoltura.__name__ = funcion.__name__
    return envoltura


# ------------------------------------------------------------------ Feed

@social_api.route("/feed", methods=["GET"])
@_con_sesion
def feed(user_id):
    limite = request.args.get("limite", type=int)
    argumentos = {} if limite is None else {"limite": limite}
    return jsonify(social_service.listar_feed(
        user_id,
        request.args.get("pestana", "amigos"),
        request.args.get("antes") or None,
        **argumentos,
    ))


@social_api.route("/publicables", methods=["GET"])
@_con_sesion
def publicables(user_id):
    return jsonify({"planes": social_service.listar_publicables(user_id)})


# --------------------------------------------------------- Publicaciones

@social_api.route("/publicaciones", methods=["POST"])
@_con_sesion
def publicar(user_id):
    datos = _cuerpo()
    publicacion = social_service.publicar(
        user_id,
        _id_o_404(datos.get("plan_id", "")),
        str(datos.get("texto") or ""),
        str(datos.get("visibilidad") or "amigos"),
    )
    return jsonify({"publicacion": publicacion}), 201


@social_api.route("/publicaciones/<publicacion_id>/eliminar", methods=["POST"])
@_con_sesion
def eliminar_publicacion(user_id, publicacion_id):
    _cuerpo()
    social_service.eliminar_publicacion(user_id, _id_o_404(publicacion_id))
    return jsonify({"ok": True})


@social_api.route("/publicaciones/<publicacion_id>/like", methods=["POST"])
@_con_sesion
def me_gusta(user_id, publicacion_id):
    datos = _cuerpo()
    return jsonify(social_service.set_me_gusta(
        user_id, _id_o_404(publicacion_id), datos.get("me_gusta") is True
    ))


@social_api.route("/publicaciones/<publicacion_id>/guardar", methods=["POST"])
@_con_sesion
def guardar(user_id, publicacion_id):
    datos = _cuerpo()
    return jsonify(social_service.set_guardado(
        user_id, _id_o_404(publicacion_id), datos.get("guardar") is True
    ))


# ----------------------------------------------------------- Comentarios

@social_api.route("/publicaciones/<publicacion_id>/comentarios", methods=["GET"])
@_con_sesion
def comentarios(user_id, publicacion_id):
    return jsonify({
        "comentarios": social_service.listar_comentarios(
            user_id, _id_o_404(publicacion_id)
        )
    })


@social_api.route("/publicaciones/<publicacion_id>/comentarios", methods=["POST"])
@_con_sesion
def comentar(user_id, publicacion_id):
    datos = _cuerpo()
    comentario = social_service.comentar(
        user_id, _id_o_404(publicacion_id), str(datos.get("texto") or "")
    )
    return jsonify({"comentario": comentario}), 201


@social_api.route("/comentarios/<comentario_id>/eliminar", methods=["POST"])
@_con_sesion
def eliminar_comentario(user_id, comentario_id):
    _cuerpo()
    social_service.eliminar_comentario(user_id, _id_o_404(comentario_id))
    return jsonify({"ok": True})


# -------------------------------------------------------------- Reportes

@social_api.route("/reportes", methods=["POST"])
@_con_sesion
def reportar(user_id):
    datos = _cuerpo()
    social_service.reportar(
        user_id,
        str(datos.get("tipo") or ""),
        _id_o_404(datos.get("id", "")),
        str(datos.get("motivo") or ""),
    )
    return jsonify({"ok": True})
