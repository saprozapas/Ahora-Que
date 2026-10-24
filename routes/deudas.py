from flask import Blueprint, flash, redirect, render_template, request, session, url_for
import psycopg2

from services.deuda_service import DeudaService, parsear_monto

deudas_bp = Blueprint("deudas", __name__)
deuda_service = DeudaService()


def _uid():
    return session.get("user_id")


@deudas_bp.route("/deudas")
def deudas():
    if not _uid():
        return redirect(url_for("auth.login"))
    return render_template("deudas.html", deudas_page=True, **deuda_service.listar(_uid()))


@deudas_bp.route("/deudas/nueva", methods=["GET", "POST"])
def nueva():
    if not _uid():
        return redirect(url_for("auth.login"))
    # Desde un grupo llega ?grupo=<id>: se cargan todos los integrantes.
    id_grupo = request.values.get("grupo") or None
    try:
        candidatos = deuda_service.candidatos(_uid(), id_grupo)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("deudas.deudas"))
    except psycopg2.Error as e:
        print(f"Error en deudas/nueva: {e}")
        flash("No se pudo abrir el formulario.")
        return redirect(url_for("deudas.deudas"))

    if request.method == "POST":
        f = request.form
        try:
            # El creador carga lo gastado y lo pagado de todos, incluido él mismo.
            montos = {_uid(): (parsear_monto(f.get("gasto_yo")), parsear_monto(f.get("pago_yo")))}
            for id_persona in f.getlist("participantes"):
                montos[id_persona] = (parsear_monto(f.get("gasto_" + id_persona)),
                                      parsear_monto(f.get("pago_" + id_persona)))
            pagos = deuda_service.crear_reparto(_uid(), f.get("descripcion"), montos, id_grupo)
            flash("Listo: ya se calculó quién le paga a quién." if pagos else "Listo: nadie le debe nada a nadie.")
            return redirect(url_for("deudas.deudas"))
        except ValueError as e:
            flash(str(e))  # se vuelve a mostrar el formulario con lo que escribió
        except psycopg2.Error as e:
            print(f"Error creando reparto: {e}")
            flash("No se pudo guardar la deuda.")

    return render_template("deudas_nueva.html", deudas_page=True, candidatos=candidatos,
                           id_grupo=id_grupo, form=request.form, marcar_todos=bool(id_grupo))


@deudas_bp.route("/deudas/<id_deudor>/pagada", methods=["POST"])
def pagada(id_deudor):
    if not _uid():
        return redirect(url_for("auth.login"))
    try:
        deuda_service.marcar_pagada(_uid(), id_deudor, parsear_monto(request.form.get("monto")))
        flash("Deuda saldada.")
    except ValueError as e:
        flash(str(e))
    except psycopg2.Error as e:
        print(f"Error saldando deuda: {e}")
        flash("No se pudo marcar como pagada.")
    return redirect(url_for("deudas.deudas"))
