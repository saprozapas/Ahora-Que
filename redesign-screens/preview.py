"""Vista previa del rediseño con datos de ejemplo.

Levanta la app real (los mismos templates, CSS y JS) en
http://127.0.0.1:5058, pero reemplaza en memoria las consultas a la base
por datos de ejemplo. No toca la base de datos:

  * Todo lo que lee está simulado acá abajo.
  * Todo lo que intenta guardar (cualquier POST) se corta antes de llegar
    a las rutas y avisa "Vista de demo: no se guarda nada".

Uso (desde la raíz del repo):
    python redesign-screens/preview.py
o doble clic en redesign-screens/ver-rediseno.bat.

Después entrá a http://127.0.0.1:5058/demo, que inicia una sesión de
ejemplo (Valentina Sosa) y te lleva al dashboard. Las páginas públicas
(landing, login, registro, explorar) se ven en http://127.0.0.1:5058/.

No cambia ningún archivo del backend: solo reemplaza funciones en memoria
mientras corre este proceso.
"""

import os
import sys
from datetime import date, time as hora
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from flask import flash, jsonify, redirect, request, session  # noqa: E402

import app as app_mod  # noqa: E402
from app import app  # noqa: E402
import routes.calendario as calendario  # noqa: E402
import routes.friends as amigos  # noqa: E402
import routes.group_auth as grupos  # noqa: E402
import routes.grupo_planes as grupo_planes  # noqa: E402
import routes.inbox as inbox  # noqa: E402
import routes.planes as planes  # noqa: E402
import routes.profile as perfil  # noqa: E402
from models.group import Group  # noqa: E402
from models.invitacion import Invitacion  # noqa: E402
from models.solicitud_amistad import SolicitudAmistad  # noqa: E402
from models.user import User  # noqa: E402

PUERTO = 5058

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True


# ---------------------------------------------------------------------------
# Nada se guarda: cualquier POST se corta acá, antes que las rutas.
# ---------------------------------------------------------------------------

AVISO = "Vista de demo: no se guarda nada."


def _no_guardar():
    if request.method == "POST":
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.path.startswith("/amigos/solicitar"):
            return jsonify(ok=False, error=AVISO, estado=None)
        flash(AVISO)
        return redirect(request.referrer or "/dashboard")
    return None


app.before_request_funcs.setdefault(None, []).insert(0, _no_guardar)


# ---------------------------------------------------------------------------
# Datos de ejemplo
# ---------------------------------------------------------------------------

hoy = date.today()
otro_dia = hoy.replace(day=min(hoy.day + 3, 28))

yo = User("Valentina Sosa", "2001-03-02", "valen", "valen@ejemplo.com", "x", "Me gustan los planes al aire libre y las juntadas tranquilas.")
diego = User("Diego Pereira", "2000-05-11", "diegop", "diego@ejemplo.com", "x", "Siempre armo el asado.")
carla = User("Carla Méndez", "2001-01-01", "carlam", "carla@ejemplo.com", "x")

grupo = Group(yo, "Amigos de la facu", "Los de siempre: cine, feria y alguna escapada.", id="g1")
lista_de_grupos = [
    grupo,
    Group(yo, "Familia Sosa", "Almuerzos de domingo y cumpleaños.", id="g2"),
    Group(yo, "FIUM", "Amigos de la facultad y Maxi.", id="g3"),
    Group(yo, "Pareja", "", id="g4"),
]

invitaciones = [
    Invitacion("g2", "Familia Sosa", "¡Sumate que el domingo hay asado!", "Diego Pereira"),
    Invitacion("g3", "FIUM", "", "Carla Méndez"),
]
solicitudes = [SolicitudAmistad("u7", "Martín Rodríguez", "martinr")]

planes_de_ejemplo = [
    {"id": "p1", "nombre": "Asado en lo de Juan", "fecha": hoy, "hora": hora(20, 30),
     "resumen_lugares": "Casa de Juan", "precio_min": 300, "precio_max": 600, "precio": None,
     "grupo": "Amigos de la facu", "estado": "confirmado", "estado_texto": "Confirmado", "mi_puntaje": None},
    {"id": "p2", "nombre": "Rambla hasta el Parque Rodó", "fecha": hoy, "hora": hora(16, 0),
     "resumen_lugares": "Rambla · Parque Rodó", "precio_min": 0, "precio_max": 0, "precio": None,
     "grupo": "Amigos de la facu", "estado": "votacion", "estado_texto": "En votación", "mi_puntaje": None},
    {"id": "p3", "nombre": "Cine en Punta Carretas + pizza", "fecha": None, "hora": None,
     "resumen_lugares": "Punta Carretas Shopping · Pizzería", "precio_min": 600, "precio_max": 1000, "precio": None,
     "grupo": None, "estado": "idea", "estado_texto": "Idea", "mi_puntaje": None},
]

detalle_de_ejemplo = {
    "id": "p1", "nombre": "Asado en lo de Juan", "estado": "archivado", "estado_texto": "Archivado",
    "fecha": hoy, "hora": hora(20, 30), "grupo": "Amigos de la facu", "grupo_id": "g1",
    "descripcion": "Juan pone la parrilla; cada uno lleva algo. Después, cartas.",
    "precio_min": 400, "precio_max": 700, "precio": None,
    "lugares": [
        {"nombre": "Supermercado del barrio", "hora": hora(19, 0), "precio_min": 300, "precio_max": 600},
        {"nombre": "Casa de Juan", "hora": hora(20, 30), "precio_min": None, "precio_max": None},
        {"nombre": "Heladería de la esquina", "hora": None, "precio_min": 100, "precio_max": 100},
    ],
    "promedio": 4.5, "votos": 4, "puede_puntuar": True, "mi_puntaje": 5,
    "guardado": False, "confirmado": True, "es_creador": True,
}


def _tablero(group_id, user_id):
    return {
        "para_puntuar": [
            {"id": "t1", "nombre": "Asado en lo de Juan", "fecha": hoy, "hora": hora(20, 30), "resumen_lugares": "Casa de Juan"},
        ],
        "votacion": [
            {"id": "t2", "nombre": "Rambla hasta el Parque Rodó", "fecha": hoy, "hora": hora(16, 0),
             "resumen_lugares": "Rambla · Parque Rodó", "creador": "Diego Pereira",
             "descripcion": "Salimos desde Pocitos y terminamos en la feria.",
             "votos": 2, "miembros": 4, "gustan": 2, "pueden": 1, "mi_gusta": None, "mi_puedo": None, "es_creador": True},
        ],
        "esperando_horario": [
            {"id": "t3", "nombre": "Cine en Punta Carretas", "fecha": hoy, "hora": hora(21, 0),
             "resumen_lugares": "Punta Carretas Shopping", "miembros": 4, "es_creador": False, "horarios": [
                 {"id": 7, "fecha": otro_dia, "hora": hora(19, 30), "propuesto_por": "Valentina Sosa", "pueden": 3, "votos": 3, "mi_puedo": True},
                 {"id": 8, "fecha": otro_dia, "hora": hora(22, 0), "propuesto_por": "Diego Pereira", "pueden": 1, "votos": 2, "mi_puedo": None},
             ]},
        ],
        "confirmados": [
            {"id": "t4", "nombre": "Feria de Tristán Narvaja", "fecha": otro_dia, "hora": hora(10, 0),
             "resumen_lugares": "Tristán Narvaja", "van": ["Valentina Sosa", "Diego Pereira", "Carla Méndez"], "confirmado": False},
        ],
    }


# ---------------------------------------------------------------------------
# Reemplazos en memoria de las consultas a la base
# ---------------------------------------------------------------------------

app_mod._inbox_guardado = lambda uid: (invitaciones, len(invitaciones) + len(solicitudes))
app_mod.plan_service.archivar_vencidos = lambda forzar=False: None
app_mod.plan_service.get_sugerencias_amigos = lambda uid, nivel=4: {
    "planes": [
        {"id": "p1", "nombre": "Feria de Tristán Narvaja", "fecha": hoy, "hora": hora(10, 0), "resumen_lugares": "Tristán Narvaja",
         "amigos": ["Diego Pereira"], "promedio": 4.7, "votos": 3},
        {"id": "p1", "nombre": "Cine en Punta Carretas + pizza", "fecha": hoy, "hora": hora(21, 0),
         "resumen_lugares": "Punta Carretas Shopping · Pizzería",
         "amigos": ["Carla Méndez", "Martín Rodríguez", "Lucía Fernández"], "promedio": 4.0, "votos": 5},
        {"id": "p1", "nombre": "Rambla hasta el Parque Rodó", "fecha": hoy, "hora": None, "resumen_lugares": "Rambla · Parque Rodó",
         "amigos": ["Diego Pereira", "Carla Méndez"], "promedio": None, "votos": 0},
    ],
    "nivel": nivel, "hay_siguiente": nivel is not None, "siguiente_nivel": 3 if nivel == 4 else None, "total": 5,
}

grupos.getGroupsForUser = lambda uid: lista_de_grupos
grupos.getUser = lambda uid: yo
grupos.isUserInGroup = lambda uid, gid: True
grupos.getGroupById = lambda gid: next((g for g in lista_de_grupos if g.get_id() == gid), grupo)
grupos.getUsersInGroupWithIds = lambda gid: [{"id": "u1", "user": yo}, {"id": "u2", "user": diego}, {"id": "u3", "user": carla}]
grupos.plan_service.archivar_vencidos = lambda forzar=False: None
grupos.grupo_plan_service.get_tablero = _tablero

grupo_planes.isUserInGroup = lambda uid, gid: True
grupo_planes.getGroupById = grupos.getGroupById
grupo_planes.plan_service.get_ideas_postulables = lambda uid: [
    {"id": "i1", "nombre": "Cena y pool", "guardado": True, "resumen_lugares": "La Pasiva · Bar Tabaré",
     "precio_min": 600, "precio_max": 900, "descripcion": "Cenar algo rápido y jugar un par de partidas."},
    {"id": "i2", "nombre": "Merienda en el Mercado Agrícola", "guardado": True, "resumen_lugares": "MAM",
     "precio_min": 450, "precio_max": 450, "descripcion": None},
    {"id": "i3", "nombre": "Noche de juegos", "guardado": False, "resumen_lugares": "Sin lugar específico",
     "precio_min": None, "precio_max": None, "descripcion": None},
]

planes.plan_service.archivar_vencidos = lambda forzar=False: None
planes.plan_service.get_planes_confirmados = lambda uid: [planes_de_ejemplo[0]]
planes.plan_service.get_planes_grupo = lambda uid: planes_de_ejemplo[:2]
planes.plan_service.get_planes_guardados = lambda uid: [planes_de_ejemplo[2]]
planes.plan_service.get_archivados = lambda uid: []
planes.plan_service.get_plan_detalle = lambda pid, uid: detalle_de_ejemplo
planes.lugar_service.listar_tipos = lambda: [{"id": 1, "nombre": "Restaurante"}, {"id": 2, "nombre": "Bar"}, {"id": 3, "nombre": "Parque"}]
planes.lugar_service.buscar = lambda texto="", tipo_id="", filtros=None: [
    {"id": "l1", "nombre": "La Pasiva Pocitos", "direccion": "Av. Brasil 2800", "ambiente": "Informal", "nivel_precio": 2},
    {"id": "l2", "nombre": "Parque Rodó", "direccion": "Rambla Wilson", "ambiente": "Aire libre", "nivel_precio": 0},
    {"id": "l3", "nombre": "Bar Tabaré", "direccion": "Zorrilla de San Martín 152", "ambiente": "Tranquilo", "nivel_precio": 3},
]

inbox.invitation_service.get_invitations_for_user = lambda uid: invitaciones
inbox.friend_service.get_requests_for_user = lambda uid: solicitudes

amigos.getFriendsForUser = lambda uid: [{"id": "u2", "user": diego}, {"id": "u3", "user": carla}]
amigos.getGroupsForUser = lambda uid: lista_de_grupos
amigos.buscarUsuarios = lambda q, uid: [
    {"id": "u8", "nombre": "Lucía Fernández", "username": "luciaf", "ya_amigos": False, "solicitud_enviada": False, "solicitud_recibida": False},
    {"id": "u2", "nombre": "Diego Pereira", "username": "diegop", "ya_amigos": True, "solicitud_enviada": False, "solicitud_recibida": False},
]

perfil.getUser = lambda uid: diego

calendario.plan_service.get_planes_confirmados_calendario = lambda uid: [
    {"id": "p1", "nombre": "Asado en lo de Juan", "fecha": hoy, "hora": hora(20, 30)},
    {"id": "p1", "nombre": "Cine + pizza", "fecha": otro_dia, "hora": hora(19, 0)},
    {"id": "p1", "nombre": "Feria de Tristán Narvaja", "fecha": otro_dia, "hora": hora(10, 0)},
]


# ---------------------------------------------------------------------------
# Entrada a la demo
# ---------------------------------------------------------------------------

@app.route("/demo")
def entrar_a_la_demo():
    session["user_id"] = "u1"
    session["user"] = {"name": "Valentina Sosa", "username": "valen", "email": "valen@ejemplo.com",
                       "descripcion": "Me gustan los planes al aire libre y las juntadas tranquilas."}
    return redirect("/dashboard")


if __name__ == "__main__":
    print()
    print(f"  Vista previa del rediseño en http://127.0.0.1:{PUERTO}")
    print(f"  Con sesión de ejemplo:      http://127.0.0.1:{PUERTO}/demo")
    print("  (Ctrl + C para cerrarla. No se guarda nada en la base.)")
    print()
    app.run(host="127.0.0.1", port=PUERTO, debug=False)
