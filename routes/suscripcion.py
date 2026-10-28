from flask import Blueprint, flash, redirect, render_template, request, session

from services.pago_mock import BANCOS, validar_mercadopago, validar_tarjeta, validar_transferencia
from services.suscripcion_service import SuscripcionService

suscripcion_bp = Blueprint("suscripcion", __name__)
suscripcion_service = SuscripcionService()

# Los datos de pago de la maqueta nunca se vuelven a mostrar ni se guardan.
_SECRETOS = {"numero", "cvv", "cuenta", "documento"}


def _uid():
    return session.get("user_id")


@suscripcion_bp.route("/suscripcion")
def suscripcion():
    if not _uid():
        return redirect("/login")
    return render_template("suscripcion.html")


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
    """Maqueta de pago: valida el formato de los datos pero no cobra nada."""
    if not _uid():
        return redirect("/login")
    if suscripcion_service.es_premium(_uid()):
        return redirect("/suscripcion")

    errores, valores, abierto = {}, {}, "tarjeta"
    if request.method == "POST":
        f = request.form
        abierto = f.get("metodo", "tarjeta")
        valores = {k: v for k, v in f.items() if k not in _SECRETOS}
        if abierto == "tarjeta":
            errores = validar_tarjeta(f.get("numero"), f.get("nombre"), f.get("vencimiento"), f.get("cvv"))
        elif abierto == "transferencia":
            errores = validar_transferencia(f.get("banco"), f.get("cuenta"), f.get("titular"), f.get("documento"))
        elif abierto == "mercadopago":
            errores = validar_mercadopago(f.get("contacto"))
        elif abierto != "applepay":  # Apple Pay no pide datos: la maqueta solo confirma
            abierto, errores = "tarjeta", {"numero": "Elegí un medio de pago."}
        if not errores:
            suscripcion_service.cambiar_plan(_uid(), True)
            flash("¡Listo! Ya sos Premium. (Maqueta: no se cobró nada.)")
            return redirect("/suscripcion")

    return render_template(
        "premium_pagar.html", bancos=BANCOS, errores=errores, valores=valores, abierto=abierto
    ), (400 if errores else 200)
