from datetime import date, datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from services.plan_service import PlanService
from services.lugar_service import LugarService
from services.lugar_filtros import FILTROS_LUGAR

planes_bp = Blueprint("planes", __name__, url_prefix="/planes")
plan_service = PlanService()
lugar_service = LugarService()


def _sin_sesion():
    return not session.get("user_id")


@planes_bp.route("/")
def menu():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    return render_template("planes_menu.html")


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
        subtitulo="Planes que van a pasar en tus grupos y todavía no confirmaste.",
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
        titulo="Planes guardados",
        subtitulo="Ideas de plan que guardaste para más adelante.",
        planes=planes,
        mostrar_fecha=False,
        mostrar_quitar_guardado=True,
        vacio="No guardaste ningún plan todavía.",
    )


@planes_bp.route("/historial")
def historial():
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    planes = plan_service.get_historial(session["user_id"])
    return render_template(
        "planes_lista.html",
        titulo="Historial de planes",
        subtitulo="Planes confirmados a los que fuiste en los últimos 3 meses.",
        planes=planes,
        mostrar_fecha=True,
        mostrar_quitar_guardado=False,
        vacio="No tenés planes en tu historial reciente.",
    )


@planes_bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if _sin_sesion():
        return redirect(url_for("auth.login"))

    hoy = date.today().isoformat()

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        fecha = request.form.get("fecha", "").strip()
        hora = request.form.get("hora", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        guardado = request.form.get("guardado") == "on"

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
            # No se repiten lugares: si el mismo id ya se usó, se ignora
            # el duplicado (esto es el respaldo del lado del servidor;
            # el buscador ya no deja agregarlo dos veces del lado del
            # navegador).
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

        error = ""
        fecha_valida = None
        if not nombre:
            error = "El plan necesita un nombre."
        elif not fecha:
            error = "El plan necesita una fecha."
        elif not hora:
            error = "El plan necesita una hora."
        else:
            try:
                fecha_valida = datetime.strptime(fecha, "%Y-%m-%d").date()
            except ValueError:
                error = "La fecha no es válida."
            else:
                if fecha_valida < date.today():
                    error = "No se puede crear un plan para una fecha que ya pasó."

        if not error:
            try:
                plan_id = plan_service.crear_plan(
                    user_id=session["user_id"],
                    nombre=nombre,
                    fecha=fecha,
                    hora=hora,
                    descripcion=descripcion or None,
                    lugares=lugares,
                    guardado=guardado,
                )
                flash("Plan creado y confirmado. Ya está en tu calendario.", "success")
                return redirect(url_for("planes.detalle", plan_id=plan_id))
            except Exception:
                error = "Hubo un error al crear el plan. Intentá de nuevo."

        return render_template(
            "planes_nuevo.html",
            filtros=FILTROS_LUGAR,
            tipos=lugar_service.listar_tipos(),
            error=error,
            valores=request.form,
            hoy=hoy,
        )

    return render_template(
        "planes_nuevo.html",
        filtros=FILTROS_LUGAR,
        tipos=lugar_service.listar_tipos(),
        error="",
        valores={},
        hoy=hoy,
    )


@planes_bp.route("/buscar-lugares")
def buscar_lugares():
    """Devuelve lugares en JSON para el buscador de la página de crear plan."""
    if _sin_sesion():
        return jsonify(resultados=[]), 401

    resultados = lugar_service.buscar(
        texto=request.args.get("texto", ""),
        tipo_id=request.args.get("tipo", ""),
        filtros=request.args,
    )
    return jsonify(resultados=resultados)


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


@planes_bp.route("/<plan_id>")
def detalle(plan_id):
    if _sin_sesion():
        return redirect(url_for("auth.login"))
    plan = plan_service.get_plan_detalle(plan_id, session["user_id"])
    if plan is None:
        abort(404)
    return render_template("plan_detalle.html", plan=plan)
