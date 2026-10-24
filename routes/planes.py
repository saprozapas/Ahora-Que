import math
import uuid

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from services.plan_service import PlanService
from services.plan_ubicacion_service import PlanUbicacionService, UbicacionNoPermitida
from services.lugar_service import LugarService
from services.lugar_filtros import FILTROS_LUGAR

# Los filtros que se ofrecen al crear un plan a mano (algunos existen solo para el chatbot y las encuestas).
FILTROS_FORMULARIO = [f for f in FILTROS_LUGAR if f.get("en_formulario", True)]

planes_bp = Blueprint("planes", __name__, url_prefix="/planes")
plan_service = PlanService()
ubicacion_service = PlanUbicacionService()
lugar_service = LugarService()


def _sin_sesion():
    return not session.get("user_id")


@planes_bp.before_request
def _archivar_vencidos():
    # Barato: corre como mucho una vez por minuto en toda la app.
    if session.get("user_id"):
        plan_service.archivar_vencidos()


def _volver_a(destino, plan_id):
    """Vuelve a la página indicada en el formulario (solo rutas internas),
    o al detalle del plan."""
    if destino and destino.startswith("/") and not destino.startswith("//"):
        return redirect(destino)
    return redirect(url_for("planes.detalle", plan_id=plan_id))


@planes_bp.route("/")
def menu():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    # "Mis planes" abre en la primera pestaña (Confirmados); desde ahí se llega al
    # resto de las listas y al calendario. Crear algo nuevo vive en el botón "+ Crear".
    return redirect(url_for("planes.confirmados"))


@planes_bp.route("/confirmados")
def confirmados():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    planes = plan_service.get_planes_confirmados(session["user_id"])
    return render_template(
        "planes_lista.html",
        titulo="Planes confirmados",
        subtitulo="Los planes que ya confirmaste, en orden de fecha.",
        planes=planes,
        mostrar_fecha=True,
        mostrar_quitar_guardado=False,
        vacio="Todavía no confirmaste ningún plan.",
    )


@planes_bp.route("/grupo")
def de_grupo():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    planes = plan_service.get_planes_grupo(session["user_id"])
    return render_template(
        "planes_lista.html",
        titulo="Planes de grupo",
        subtitulo="Planes de tus grupos en votación, esperando horario, o confirmados por otros a los que todavía te podés sumar.",
        planes=planes,
        mostrar_fecha=True,
        mostrar_quitar_guardado=False,
        vacio="No hay planes de grupo pendientes de confirmar.",
    )


@planes_bp.route("/guardados")
def guardados():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    planes = plan_service.get_planes_guardados(session["user_id"])
    return render_template(
        "planes_lista.html",
        titulo="Ideas guardadas",
        subtitulo="Tus planes sin fecha: proponelos en un grupo para que los voten.",
        planes=planes,
        mostrar_fecha=False,
        mostrar_quitar_guardado=True,
        vacio="No guardaste ningún plan todavía. Creá uno o guardá uno desde Social.",
    )


@planes_bp.route("/archivados")
def archivados():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    planes = plan_service.get_archivados(session["user_id"])
    return render_template(
        "planes_lista.html",
        titulo="Planes archivados",
        subtitulo="Planes que ya hiciste. También los podés volver a proponer en un grupo.",
        planes=planes,
        mostrar_fecha=True,
        mostrar_quitar_guardado=False,
        vacio="Todavía no tenés planes archivados.",
    )


@planes_bp.route("/historial")
def historial():
    return redirect(url_for("planes.archivados"))


@planes_bp.route("/nuevo")
def nuevo():
    # Ya no se crean planes individuales con fecha: solo ideas.
    return redirect(url_for("planes.nueva_idea"))


@planes_bp.route("/nueva-idea/asistente")
def nueva_idea_asistente():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    return render_template("planes_asistente.html")


@planes_bp.route("/nueva-idea", methods=["GET", "POST"])
def nueva_idea():
    if _sin_sesion():
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip()

        # Las paradas llegan como listas paralelas desde el formulario.
        ids = request.form.getlist("lugar_id")
        nombres = request.form.getlist("lugar_nombre")
        niveles = request.form.getlist("lugar_nivel_precio")
        horas = request.form.getlist("lugar_hora")

        lugares = []
        ids_vistos = set()
        for indice, nombre_lugar in enumerate(nombres):
            nombre_lugar = nombre_lugar.strip()
            if not nombre_lugar:
                continue

            id_lugar = ids[indice].strip() if indice < len(ids) else ""
            # No se repiten lugares (respaldo del lado del servidor).
            if id_lugar and id_lugar in ids_vistos:
                continue
            if id_lugar:
                ids_vistos.add(id_lugar)

            nivel_texto = niveles[indice].strip() if indice < len(niveles) else ""
            try:
                nivel_precio = int(nivel_texto) if nivel_texto != "" else None
            except ValueError:
                nivel_precio = None

            hora_lugar = horas[indice].strip() if indice < len(horas) else ""

            lugares.append({
                "id_lugar": id_lugar or None,
                "nombre": nombre_lugar,
                "nivel_precio": nivel_precio,
                "hora": hora_lugar or None,
            })

        error = "" if nombre else "El plan necesita un nombre."
        if not error:
            try:
                plan_id = plan_service.crear_idea(
                    user_id=session["user_id"],
                    nombre=nombre,
                    descripcion=descripcion or None,
                    lugares=lugares,
                )
                flash("Plan guardado. Proponelo en un grupo cuando quieras.", "success")
                return redirect(url_for("planes.detalle", plan_id=plan_id))
            except Exception as e:
                print(f"Error al crear idea: {e}")
                error = "Hubo un error al crear el plan. Intentá de nuevo."

        return render_template(
            "planes_nuevo.html",
            filtros=FILTROS_FORMULARIO,
            tipos=lugar_service.listar_tipos(),
            error=error,
            valores=request.form,
        )

    return render_template(
        "planes_nuevo.html",
        filtros=FILTROS_FORMULARIO,
        tipos=lugar_service.listar_tipos(),
        error="",
        valores={},
    )


@planes_bp.route("/buscar-lugares")
def buscar_lugares():
    """Devuelve lugares en JSON para el buscador de la página de crear plan."""
    if _sin_sesion():
        return jsonify(resultados=[]), 401

    # "limite" lo usa el desplegable que aparece al escribir (pocos resultados).
    limite = request.args.get("limite", default=30, type=int)
    # "lat" y "lon" (opcionales) son la ubicación de quien busca: se usan solo para
    # calcular distancias en esta consulta; no se guardan.
    resultados = lugar_service.buscar(
        texto=request.args.get("texto", ""),
        tipo_id=request.args.get("tipo", ""),
        filtros=request.args,
        limite=limite,
        lat=request.args.get("lat"),
        lon=request.args.get("lon"),
        max_km=request.args.get("max_km"),
    )
    return jsonify(resultados=resultados)


@planes_bp.route("/buscar-barrios")
def buscar_barrios():
    """Barrios que coinciden con lo escrito (para el campo Barrio del buscador)."""
    if _sin_sesion():
        return jsonify(resultados=[]), 401

    resultados = lugar_service.buscar_barrios(
        texto=request.args.get("texto", ""),
        limite=request.args.get("limite", default=8, type=int),
    )
    return jsonify(resultados=resultados)


@planes_bp.route("/barrio-cercano")
def barrio_cercano():
    """El barrio más cercano a la ubicación que manda el navegador (para sugerir el de la encuesta).
    Las coordenadas se usan solo para esta consulta; no se guardan."""
    if _sin_sesion():
        return jsonify(barrio=None), 401
    barrio = lugar_service.barrio_cercano(request.args.get("lat"), request.args.get("lon"))
    return jsonify(barrio=barrio)


@planes_bp.route("/<plan_id>/guardar", methods=["POST"])
def guardar(plan_id):
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    plan_service.set_guardado(plan_id, session["user_id"], True)
    flash("Plan guardado.", "success")
    return redirect(request.referrer or url_for("planes.detalle", plan_id=plan_id))


@planes_bp.route("/<plan_id>/desguardar", methods=["POST"])
def desguardar(plan_id):
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    plan_service.set_guardado(plan_id, session["user_id"], False)
    flash("Plan sacado de guardados.", "success")
    return redirect(request.referrer or url_for("planes.guardados"))


@planes_bp.route("/<plan_id>/sumarme", methods=["POST"])
def sumarme(plan_id):
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    if plan_service.sumarse_a_plan(plan_id, session["user_id"]):
        flash("¡Te sumaste! El plan ya está en tu calendario.", "success")
    else:
        flash("No te pudiste sumar: el plan ya no está confirmado.", "error")
    return _volver_a(request.form.get("volver"), plan_id)


@planes_bp.route("/<plan_id>/bajarme", methods=["POST"])
def bajarme(plan_id):
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    plan_service.bajarse_de_plan(plan_id, session["user_id"])
    flash("Te bajaste del plan.", "success")
    return redirect(url_for("planes.menu"))


@planes_bp.route("/<plan_id>/eliminar", methods=["POST"])
def eliminar(plan_id):
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    borrado = plan_service.eliminar_plan(plan_id, session["user_id"])
    if borrado:
        flash("Plan eliminado.", "success")
    else:
        flash("Solo quien creó el plan lo puede eliminar.", "error")
        return redirect(url_for("planes.detalle", plan_id=plan_id))
    return redirect(url_for("planes.menu"))


@planes_bp.route("/<plan_id>/puntuar", methods=["POST"])
def puntuar(plan_id):
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    try:
        puntaje = int(request.form.get("puntaje", ""))
    except ValueError:
        puntaje = -1
    if not 0 <= puntaje <= 5:
        flash("Elegí un puntaje entre 0 y 5 estrellas.", "error")
    elif plan_service.set_puntaje(plan_id, session["user_id"], puntaje):
        flash("¡Gracias! Tu puntaje quedó guardado.", "success")
    else:
        flash("Solo pueden puntuar quienes fueron al plan, 12 h después de que arrancó.", "error")
    return _volver_a(request.form.get("volver"), plan_id)


@planes_bp.route("/<plan_id>")
def detalle(plan_id):
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    plan = plan_service.get_plan_detalle(plan_id, session["user_id"])
    if plan is None:
        abort(404)
    return render_template("plan_detalle.html", plan=plan)


# --- Mapa del plan confirmado: el lugar y, si cada uno quiere, dónde está cada asistente ------------------------

def _id_valido(plan_id):
    try:
        return str(uuid.UUID(str(plan_id)))
    except ValueError:
        return None


@planes_bp.route("/<plan_id>/mapa")
def mapa_datos(plan_id):
    if _sin_sesion():
        return jsonify({"ok": False, "error": "Tu sesión venció."}), 401
    plan_id = _id_valido(plan_id)
    if plan_id is None:
        return jsonify({"ok": False, "error": "Ese plan no existe."}), 404
    try:
        datos = ubicacion_service.datos(plan_id, session["user_id"])
    except UbicacionNoPermitida:
        return jsonify({"ok": False, "error": "El mapa es solo para quienes van a un plan confirmado."}), 403
    except Exception as e:
        print(f"No se pudo armar el mapa del plan: {e}")
        return jsonify({"ok": False, "error": "No se pudo cargar el mapa."}), 500
    respuesta = jsonify({"ok": True, **datos})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@planes_bp.route("/<plan_id>/ubicacion", methods=["POST"])
def compartir_ubicacion(plan_id):
    if _sin_sesion():
        return jsonify({"ok": False, "error": "Tu sesión venció."}), 401
    plan_id = _id_valido(plan_id)
    datos = request.get_json(silent=True) or {}
    try:
        lat, lon = float(datos.get("lat")), float(datos.get("lon"))
    except (TypeError, ValueError):
        lat = lon = float("nan")
    if plan_id is None or not (math.isfinite(lat) and math.isfinite(lon)) or abs(lat) > 90 or abs(lon) > 180:
        return jsonify({"ok": False, "error": "Esa ubicación no es válida."}), 400
    try:
        ubicacion_service.compartir(plan_id, session["user_id"], lat, lon)
    except UbicacionNoPermitida:
        return jsonify({"ok": False, "error": "Solo podés compartir tu ubicación en un plan confirmado al que vas."}), 403
    except Exception as e:
        print(f"No se pudo guardar la ubicación: {e}")
        return jsonify({"ok": False, "error": "No se pudo guardar tu ubicación."}), 500
    return jsonify({"ok": True})


@planes_bp.route("/<plan_id>/ubicacion/detener", methods=["POST"])
def detener_ubicacion(plan_id):
    if _sin_sesion():
        return jsonify({"ok": False, "error": "Tu sesión venció."}), 401
    plan_id = _id_valido(plan_id)
    if plan_id is None:
        return jsonify({"ok": False, "error": "Ese plan no existe."}), 404
    try:
        ubicacion_service.dejar_de_compartir(plan_id, session["user_id"])
    except Exception as e:
        print(f"No se pudo borrar la ubicación: {e}")
        return jsonify({"ok": False, "error": "No se pudo dejar de compartir."}), 500
    return jsonify({"ok": True})
