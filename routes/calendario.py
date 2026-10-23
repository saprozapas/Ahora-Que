import calendar
from datetime import date, timedelta

from flask import Blueprint, redirect, render_template, request, session, url_for
from services.fechas import dia_relativo
from services.plan_service import PlanService

calendario_bp = Blueprint("calendario", __name__)
plan_service = PlanService()

NOMBRES_MES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _fecha_de(texto, por_defecto):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return por_defecto


def _rango_de_semana(lunes):
    """"20 - 26 de octubre" o "27 de octubre - 2 de noviembre"."""
    domingo = lunes + timedelta(days=6)
    if lunes.month == domingo.month:
        return f"{lunes.day} - {domingo.day} de {NOMBRES_MES[lunes.month - 1].lower()}"
    return (f"{lunes.day} de {NOMBRES_MES[lunes.month - 1].lower()} - "
            f"{domingo.day} de {NOMBRES_MES[domingo.month - 1].lower()}")


@calendario_bp.route("/calendario")
def ver_calendario():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    hoy = date.today()
    vista = "semana" if request.args.get("vista") == "semana" else "mes"
    planes = plan_service.get_planes_confirmados_calendario(session["user_id"])

    if vista == "semana":
        # La semana arranca el lunes; `fecha` puede ser cualquier día de esa semana.
        base = _fecha_de(request.args.get("fecha"), hoy)
        base = min(max(base, date(2000, 1, 1)), date(2100, 12, 31))
        lunes = base - timedelta(days=base.weekday())

        dias = []
        for i in range(7):
            dia = lunes + timedelta(days=i)
            del_dia = sorted(
                (p for p in planes if p["fecha"] == dia),
                key=lambda p: (p["hora"] is None, p["hora"]),
            )
            dias.append({
                "fecha": dia,
                "iso": dia.isoformat(),
                "nombre": DIAS_SEMANA[i],
                "numero": dia.day,
                "es_hoy": dia == hoy,
                "relativo": dia_relativo(dia, hoy) if abs((dia - hoy).days) <= 1 else "",
                "planes": del_dia,
            })

        return render_template(
            "calendario.html",
            vista="semana",
            dias=dias,
            rango=_rango_de_semana(lunes),
            total=sum(len(d["planes"]) for d in dias),
            semana_anterior=(lunes - timedelta(days=7)).isoformat(),
            semana_siguiente=(lunes + timedelta(days=7)).isoformat(),
            es_esta_semana=lunes <= hoy <= lunes + timedelta(days=6),
            mes_de_la_semana=lunes.month,
            anio_de_la_semana=lunes.year,
        )

    try:
        anio = int(request.args.get("anio", hoy.year))
        mes = int(request.args.get("mes", hoy.month))
    except ValueError:
        anio, mes = hoy.year, hoy.month

    if mes < 1:
        mes, anio = 12, anio - 1
    elif mes > 12:
        mes, anio = 1, anio + 1

    # date() solo admite 1-9999: se acota a un rango razonable.
    anio = min(max(anio, 2000), 2100)

    planes_por_dia = {}
    for plan in planes:
        if plan["fecha"] and plan["fecha"].year == anio and plan["fecha"].month == mes:
            planes_por_dia.setdefault(plan["fecha"].day, []).append(plan)

    cal = calendar.Calendar(firstweekday=0)  # 0 = lunes
    semanas = []
    for semana in cal.monthdayscalendar(anio, mes):
        fila = []
        for dia in semana:
            fila.append({
                "numero": dia,
                "iso": date(anio, mes, dia).isoformat() if dia != 0 else "",
                "es_hoy": dia != 0 and date(anio, mes, dia) == hoy,
                "planes": planes_por_dia.get(dia, []) if dia != 0 else [],
            })
        semanas.append(fila)

    mes_anterior, anio_anterior = (12, anio - 1) if mes == 1 else (mes - 1, anio)
    mes_siguiente, anio_siguiente = (1, anio + 1) if mes == 12 else (mes + 1, anio)

    return render_template(
        "calendario.html",
        vista="mes",
        anio=anio,
        mes=mes,
        nombre_mes=NOMBRES_MES[mes - 1],
        dias_semana=DIAS_SEMANA,
        semanas=semanas,
        mes_anterior=mes_anterior,
        anio_anterior=anio_anterior,
        mes_siguiente=mes_siguiente,
        anio_siguiente=anio_siguiente,
        es_este_mes=(anio, mes) == (hoy.year, hoy.month),
    )
