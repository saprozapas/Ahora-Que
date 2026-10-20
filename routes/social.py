"""Endpoints JSON del feed social.

La página /social vive en app.py; acá están solo las rutas que usa
static/social.js. Todas devuelven JSON, piden sesión y validan que los ids
sean UUID (un id mal formado llegaría a la base y daría un error 500).

Las reglas de quién puede qué viven en services/social_service.py.
"""

import base64
import binascii
import uuid

from flask import Blueprint, Response, jsonify, request, session

from database_bridge.database_bridge import getGroupsForUser
from services.social_service import MAX_FOTOS, SocialError, SocialService


social_api = Blueprint("social_api", __name__, url_prefix="/social")

social_service = SocialService()

# Dos fotos de hasta 400 KB, en base64 (+33 %), más el texto.
MAX_BYTES_PUBLICAR = 1_200_000


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


def _decodificar_fotos(valores):
    """Las fotos llegan como data URL ("data:image/jpeg;base64,...") o base64
    pelado. Acá solo se decodifican; el servicio valida que sean JPEG."""
    if valores is None:
        return []
    if not isinstance(valores, list) or len(valores) > MAX_FOTOS:
        raise SocialError(f"Podés subir hasta {MAX_FOTOS} fotos.")
    fotos = []
    for valor in valores:
        if not isinstance(valor, str):
            raise SocialError("Las fotos no son válidas.")
        try:
            fotos.append(base64.b64decode(valor.split(",", 1)[-1], validate=True))
        except (binascii.Error, ValueError):
            raise SocialError("Las fotos no son válidas.")
    return fotos


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
    autor = request.args.get("autor")
    if autor:
        return jsonify(social_service.listar_de_autor(
            user_id,
            _id_o_404(autor),
            request.args.get("antes") or None,
            **argumentos,
        ))
    return jsonify(social_service.listar_feed(
        user_id,
        request.args.get("pestana", "amigos"),
        request.args.get("antes") or None,
        **argumentos,
    ))


@social_api.route("/mis-grupos", methods=["GET"])
@_con_sesion
def mis_grupos(user_id):
    """Los grupos del usuario, para elegir a cuál proponer un plan."""
    return jsonify({
        "grupos": [
            {"id": str(grupo.get_id()), "nombre": grupo.get_name()}
            for grupo in getGroupsForUser(user_id)
        ]
    })


@social_api.route("/publicables", methods=["GET"])
@_con_sesion
def publicables(user_id):
    return jsonify({"planes": social_service.listar_publicables(user_id)})


# ----------------------------------------------------------------- Fotos

@social_api.route("/fotos/<foto_id>", methods=["GET"])
@_con_sesion
def foto(user_id, foto_id):
    datos = social_service.obtener_foto(user_id, _id_o_404(foto_id))
    return Response(
        datos,
        mimetype="image/jpeg",
        headers={
            # Una foto no se edita: el navegador puede guardarla. "private"
            # evita que un proxy compartido se la dé a otra persona.
            "Cache-Control": "private, max-age=86400, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


# --------------------------------------------------------- Publicaciones

@social_api.route("/publicaciones", methods=["POST"])
@_con_sesion
def publicar(user_id):
    if request.content_length and request.content_length > MAX_BYTES_PUBLICAR:
        raise SocialError("Las fotos pesan demasiado.", 413)
    datos = _cuerpo()
    publicacion = social_service.publicar(
        user_id,
        _id_o_404(datos.get("plan_id", "")),
        str(datos.get("texto") or ""),
        str(datos.get("visibilidad") or "amigos"),
        _decodificar_fotos(datos.get("fotos")),
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
