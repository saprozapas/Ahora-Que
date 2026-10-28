from flask import Blueprint, flash, redirect, render_template, request, session

from services.pago_mock import BANCOS
from services.suscripcion_service import PLANES_IA_GRATIS_POR_SEMANA, PRECIOS, SuscripcionService

suscripcion_bp = Blueprint("suscripcion", __name__)
suscripcion_service = SuscripcionService()

_METODOS = {"tarjeta", "transferencia", "mercadopago", "applepay"}


def _uid():
    return session.get("user_id")


@suscripcion_bp.route("/suscripcion")
def suscripcion():
    if not _uid():
        return redirect("/login")
    return render_template(
        "suscripcion.html",
        ia_usados=suscripcion_service.planes_ia_usados(_uid()),
        ia_gratis_por_semana=PLANES_IA_GRATIS_POR_SEMANA,
    )


@suscripcion_bp.route("/suscripcion/cancelar", methods=["POST"])
def cancelar():
    if not _uid():
        return redirect("/login")
    if suscripcion_service.es_premium(_uid()):
        suscripcion_service.cambiar_plan(_uid(), False)
        flash("Cancelaste tu suscripción Premium. Volviste al plan gratis.")
    return redirect("/suscripcion")


@suscripcion_bp.route("/premium/pagar", methods=["GET", "POST"])
def pagar():
    """Pago de DEMOSTRACIÓN: no cobra nada.

    Los datos de la tarjeta, la cuenta o la cédula se revisan y se descartan en el navegador (ver static/premium.js):
    nunca llegan acá. Al servidor solo viaja el método elegido y la frecuencia.
    """
    if not _uid():
        return redirect("/login")
    if suscripcion_service.es_premium(_uid()):
        return redirect("/suscripcion")

    if request.method == "POST":
        metodo = request.form.get("metodo", "")
        if metodo in _METODOS and request.form.get("confirmado") == "1":
            suscripcion_service.cambiar_plan(_uid(), True)
            flash("¡Listo! Ya sos Premium. (Demostración: no se cobró nada.)")
            return redirect("/suscripcion")
        return redirect("/premium/pagar")

    ciclo = request.args.get("ciclo", "mensual")
    if ciclo not in PRECIOS:
        ciclo = "mensual"
    return render_template("premium_pagar.html", bancos=BANCOS, precios=PRECIOS, ciclo=ciclo)
