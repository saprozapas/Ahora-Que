import calendar
from datetime import date

from flask import Blueprint, redirect, render_template, request, session, url_for
from services.plan_service import PlanService

calendario_bp = Blueprint("calendario", __name__)
plan_service = PlanService()

NOMBRES_MES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


@calendario_bp.route("/calendario")
def ver_calendario():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    hoy = date.today()

    try:
        anio = int(request.args.get("anio", hoy.year))
        mes = int(request.args.get("mes", hoy.month))
    except ValueError:
        anio, mes = hoy.year, hoy.month

    if mes < 1:
        mes, anio = 12, anio - 1
    elif mes > 12:
        mes, anio = 1, anio + 1

    planes = plan_service.get_planes_confirmados(session["user_id"])

    planes_por_dia = {}
    for plan in planes:
        if plan["fecha"].year == anio and plan["fecha"].month == mes:
            planes_por_dia.setdefault(plan["fecha"].day, []).append(plan)

    cal = calendar.Calendar(firstweekday=0)  # 0 = lunes
    semanas = []
    for semana in cal.monthdayscalendar(anio, mes):
        fila = []
        for dia in semana:
            fila.append({
                "numero": dia,
                "es_hoy": dia != 0 and date(anio, mes, dia) == hoy,
                "planes": planes_por_dia.get(dia, []) if dia != 0 else [],
            })
        semanas.append(fila)

    mes_anterior, anio_anterior = (12, anio - 1) if mes == 1 else (mes - 1, anio)
    mes_siguiente, anio_siguiente = (1, anio + 1) if mes == 12 else (mes + 1, anio)

    return render_template(
        "calendario.html",
        anio=anio,
        mes=mes,
        nombre_mes=NOMBRES_MES[mes - 1],
        dias_semana=DIAS_SEMANA,
        semanas=semanas,
        mes_anterior=mes_anterior,
        anio_anterior=anio_anterior,
        mes_siguiente=mes_siguiente,
        anio_siguiente=anio_siguiente,
    )