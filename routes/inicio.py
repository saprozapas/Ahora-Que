"""El Inicio en vivo: avisos de votación y menciones, y los planes que el asistente sugiere cada semana.

GET  /inicio/pendientes                  el panel de avisos ya armado (HTML), para refrescarlo cada pocos segundos
GET  /inicio/sugerencias                 las 3 sugerencias de la semana (si todavía no existen, se arman ahora)
POST /inicio/sugerencias/<id>/guardar    guarda una sugerencia como idea en tus planes

Los avisos solo avisan: cada tarjeta lleva al grupo o al chat, donde se vota, se elige el horario o se contesta.
El Inbox queda para las solicitudes y los avisos de publicaciones."""

import time

from flask import Blueprint, flash, jsonify, make_response, redirect, render_template, session, url_for

from services.guia_nueva import COOKIE as COOKIE_GUIA
from services.inicio_service import InicioService
from services.sugerencia_service import SugerenciaService

inicio_bp = Blueprint("inicio", __name__, url_prefix="/inicio")
inicio_service = InicioService()
sugerencia_service = SugerenciaService()


def _sin_sesion():
    return jsonify({"ok": False, "error": "Tu sesión venció. Volvé a iniciar sesión."}), 401


# Los pendientes se vuelven a pedir cada pocos segundos desde el Inicio y cada pedido son varias consultas a la base:
# se guardan unos segundos por persona. Cualquier POST suyo (votar, aceptar…) lo borra al instante (ver app.py).
_SEGUNDOS_PENDIENTES = 10
_cache_pendientes = {}  # user_id -> (datos, momento)


def invalidar_pendientes(user_id):
    _cache_pendientes.pop(user_id, None)


def _pendientes_guardados(user_id):
    guardado = _cache_pendientes.get(user_id)
    if guardado and time.monotonic() - guardado[1] < _SEGUNDOS_PENDIENTES:
        return guardado[0]
    datos = inicio_service.pendientes(user_id)
    _cache_pendientes[user_id] = (datos, time.monotonic())
    return datos


@inicio_bp.route("/pendientes")
def pendientes():
    if not session.get("user_id"):
        return _sin_sesion()
    try:
        datos = _pendientes_guardados(session["user_id"])
    except Exception as e:
        print(f"No se pudieron leer los pendientes: {e}")
        return jsonify({"ok": False, "error": "No se pudieron cargar tus votaciones."}), 500
    respuesta = make_response(render_template("_inicio_pendientes.html", p=datos))
    respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["X-Pendientes"] = str(datos["total"])
    return respuesta


@inicio_bp.route("/sugerencias")
def sugerencias():
    if not session.get("user_id"):
        return _sin_sesion()
    try:
        lista = sugerencia_service.obtener(session["user_id"])
    except Exception as e:
        print(f"No se pudieron armar las sugerencias: {e}")
        return jsonify({"ok": False, "error": "No se pudieron armar tus sugerencias."}), 500
    respuesta = make_response(render_template("_inicio_sugerencias.html", sugerencias=lista))
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@inicio_bp.route("/sugerencias/<sugerencia_id>/guardar", methods=["POST"])
def guardar_sugerencia(sugerencia_id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    try:
        idea_id = sugerencia_service.guardar_como_idea(session["user_id"], sugerencia_id)
    except Exception as e:
        print(f"No se pudo guardar la sugerencia: {e}")
        idea_id = None
    if not idea_id:
        flash("No pudimos guardar esa sugerencia. Probá de nuevo.")
        return redirect("/dashboard")
    flash("Guardado en tus planes. Ahora podés proponerlo en un grupo.")
    return redirect(url_for("planes.detalle", plan_id=idea_id))


# La guía de bienvenida terminó (o se omitió): se borra la cookie y no vuelve a mostrarse.
guia_bp = Blueprint("guia", __name__)


@guia_bp.route("/guia/terminada", methods=["POST"])
def guia_terminada():
    respuesta = make_response(jsonify({"ok": True}))
    respuesta.delete_cookie(COOKIE_GUIA)
    return respuesta
