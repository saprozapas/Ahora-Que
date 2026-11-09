from flask import Blueprint, current_app, flash, redirect, render_template, request, session

from services.legal_info import PROVEEDOR, VERSION_CONDICIONES_PREMIUM, premium_demo_activo
from services.notification_service import NotificationService
from services.pago_mock import BANCOS
from services.suscripcion_service import PLANES_IA_GRATIS_POR_SEMANA, PRECIOS, SuscripcionService

suscripcion_bp = Blueprint("suscripcion", __name__)
suscripcion_service = SuscripcionService()

_METODOS = {"tarjeta", "transferencia", "mercadopago", "applepay"}


def _uid():
    return session.get("user_id")


@suscripcion_bp.app_context_processor
def _datos_legales():
    """Deja disponibles en TODAS las plantillas: el aviso de demo, los datos de quien vende y la versión de las condiciones."""
    return {
        "premium_demo": premium_demo_activo(),
        "proveedor": PROVEEDOR,
        "version_condiciones": VERSION_CONDICIONES_PREMIUM,
    }


def _enviar_comprobante(ciclo):
    """Comprobante por correo después del alta. Es 'lo mejor posible': si el correo falla, la suscripción igual queda activa."""
    try:
        usuario = session.get("user") or {}
        destino = usuario.get("email")
        if not destino:
            return
        precio = PRECIOS[ciclo]
        frecuencia = "anual" if ciclo == "anual" else "mensual"
        demo = (
            "*** COMPROBANTE DE DEMOSTRACIÓN: no se realizó ningún cobro. ***\n\n"
            if premium_demo_activo() else ""
        )
        cuerpo = (
            f"{demo}"
            f"Hola {usuario.get('name', '')},\n\n"
            f"Activaste Ahora Qué Premium ({frecuencia}).\n\n"
            f"Importe: $ {precio['total']} (pesos uruguayos, IVA incluido).\n"
            f"Se renueva automáticamente cada {'año' if ciclo == 'anual' else 'mes'} hasta que canceles.\n"
            f"Podés cancelar cuando quieras desde Tu suscripción (/suscripcion).\n"
            f"Podés arrepentirte dentro del plazo legal (art. 16 de la Ley N.º 17.250) escribiendo a {PROVEEDOR['email']}.\n\n"
            f"Vendedor: {PROVEEDOR['razon_social']} · RUT {PROVEEDOR['rut']} · {PROVEEDOR['domicilio']}\n"
            f"Condiciones aceptadas: versión {VERSION_CONDICIONES_PREMIUM}.\n"
        )
        NotificationService().enviar(destino, "Comprobante de tu suscripción Premium", cuerpo)
    except Exception as e:
        current_app.logger.warning("No se pudo enviar el comprobante de Premium: %s", e)


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
        suscripcion_service.cancelar_premium(_uid())
        flash("Suscripción cancelada\nVolviste al plan gratis. Podés volver a Premium cuando quieras.")
    return redirect("/suscripcion")


@suscripcion_bp.route("/premium/pagar", methods=["GET", "POST"])
def pagar():
    """Pago de DEMOSTRACIÓN: no cobra nada.

    Los datos de la tarjeta, la cuenta o la cédula se revisan y se descartan en el navegador (ver static/premium.js):
    nunca llegan acá. Al servidor solo viaja el método elegido, la frecuencia y la aceptación de las condiciones.
    """
    if not _uid():
        return redirect("/login")

    # 1) Sin demo encendida no se activa nada (así nadie se hace Premium gratis en producción).
    if not premium_demo_activo():
        flash("El pago de Premium todavía no está habilitado.")
        return redirect("/premium")

    if suscripcion_service.es_premium(_uid()):
        return redirect("/suscripcion")

    # 2) Un menor de edad no puede contratar por su cuenta. Se controla en el servidor, no en el navegador.
    if not suscripcion_service.es_mayor_de_edad(_uid()):
        flash("Premium es solo para personas mayores de 18 años.")
        return redirect("/premium")

    ciclo = request.values.get("ciclo", "mensual")
    if ciclo not in PRECIOS:
        ciclo = "mensual"

    if request.method == "POST":
        metodo = request.form.get("metodo", "")
        if metodo not in _METODOS or request.form.get("confirmado") != "1":
            return redirect(f"/premium/pagar?ciclo={ciclo}")

        # 3) Hay que haber aceptado las condiciones: también se exige acá, porque el navegador se puede saltear.
        if request.form.get("acepta") != "1":
            flash("Para activar Premium tenés que aceptar las condiciones.")
            return redirect(f"/premium/pagar?ciclo={ciclo}")

        try:
            suscripcion_service.activar_premium(_uid(), ciclo, VERSION_CONDICIONES_PREMIUM)
        except Exception as e:
            # Lo más probable: falta correr migraciones/premium_historial.sql
            current_app.logger.error("No se pudo activar Premium: %s", e)
            flash("No pudimos activar Premium. Probá de nuevo en un rato.")
            return redirect(f"/premium/pagar?ciclo={ciclo}")

        _enviar_comprobante(ciclo)
        flash("¡Listo, ya sos Premium!\nEs una demostración: no se cobró nada.")
        return redirect("/suscripcion")

    return render_template("premium_pagar.html", bancos=BANCOS, precios=PRECIOS, ciclo=ciclo)
