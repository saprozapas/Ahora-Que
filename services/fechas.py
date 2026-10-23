"""Fechas en lenguaje de todos los días: "hoy", "mañana", "el sábado", "el 28/10".

Se usa desde las plantillas con los filtros `dia_rel` y `cuando` (ver app.py), para que
quien mira un plan confirmado entienda cuándo es sin hacer la cuenta del calendario.
"""

from datetime import date, datetime

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _a_fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    return valor if isinstance(valor, date) else None


def dia_relativo(valor, hoy=None):
    """"hoy", "mañana", "ayer", "el sábado" (de aquí a una semana) o "el 28/10"
    (con el año si no es el actual). Vacío si no hay fecha."""
    fecha = _a_fecha(valor)
    if fecha is None:
        return ""
    hoy = hoy or date.today()
    diferencia = (fecha - hoy).days
    if diferencia == 0:
        return "hoy"
    if diferencia == 1:
        return "mañana"
    if diferencia == -1:
        return "ayer"
    if 2 <= diferencia <= 6:
        return f"el {DIAS[fecha.weekday()]}"
    if fecha.year == hoy.year:
        return f"el {fecha.day}/{fecha.month}"
    return f"el {fecha.day}/{fecha.month}/{fecha.year}"


def cuando(valor, hora=None, hoy=None):
    """"hoy a las 20:30", "mañana", "el sábado a las 19:00"."""
    texto = dia_relativo(valor, hoy)
    if texto and hora is not None and hasattr(hora, "strftime"):
        texto += f" a las {hora.strftime('%H:%M')}"
    return texto
