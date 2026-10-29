"""La pestaña Mensajes: los grupos como una lista de conversaciones, igual que los mensajes directos."""

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, redirect, render_template, session, url_for

from services.chat_service import ChatService
from services.racha_service import RachaService

mensajes_bp = Blueprint("mensajes", __name__)
chat_service = ChatService()
racha_service = RachaService()
_MONTEVIDEO = ZoneInfo("America/Montevideo")
_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


def _cuando(momento):
    """La hora si es de hoy, "ayer", el día de la semana si es de esta semana, o la fecha."""
    if momento is None:
        return ""
    ahora = datetime.now(_MONTEVIDEO).replace(tzinfo=None)
    dias = (ahora.date() - momento.date()).days
    if dias <= 0:
        return momento.strftime("%H:%M")
    if dias == 1:
        return "Ayer"
    if dias < 7:
        return _DIAS[momento.weekday()]
    return momento.strftime("%d/%m/%y")


@mensajes_bp.route("/mensajes")
def mensajes():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    conversaciones = chat_service.conversaciones(session["user_id"])
    try:
        rachas = racha_service.obtener_resumenes([c["grupo_id"] for c in conversaciones])
    except Exception as e:
        print(f"No se pudieron leer las rachas: {e}")
        rachas = {}
    for c in conversaciones:
        c["cuando"] = _cuando(c["momento"])
        c["racha"] = rachas.get(c["grupo_id"])
        c["marco"] = (c["racha"] or {}).get("marco")
    return render_template("mensajes.html", conversaciones=conversaciones)
