import time

import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, g, render_template, request, redirect, send_from_directory, session
from routes.auth import auth
from routes.group_auth import group_auth
from routes.profile import profile
from routes.inbox import inbox_bp
from datetime import timedelta
from routes.calendario import calendario_bp
from routes.planes import planes_bp
from routes.friends import friends_bp
from routes.chat import chat
from routes.grupo_planes import grupo_planes_bp
from routes.chatbot import chatbot_bp
from routes.inicio import guia_bp, inicio_bp
from routes.avatar import avatar_bp
from services.avatar_service import AvatarService
from routes.deudas import deudas_bp
from services.inicio_service import InicioService
from services.guia_nueva import es_guia_pendiente
from services.sugerencia_service import SugerenciaService
from routes.social import es_moderador, social_api
from services.invitation_service import InvitationService
from services.friend_service import FriendService
from services.deuda_service import DeudaService
from services.plan_service import PlanService
from services.social_service import SocialService


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
app.config.update(
    BREVO_API_KEY=os.environ.get("BREVO_API_KEY"),
    BREVO_SENDER_EMAIL=os.environ.get("BREVO_SENDER_EMAIL"),
    BREVO_SENDER_NAME=os.environ.get("BREVO_SENDER_NAME", "Ahora Qué"),
)
app.permanent_session_lifetime = timedelta(days=5)
app.register_blueprint(auth)
app.register_blueprint(group_auth)
app.register_blueprint(profile)
app.register_blueprint(calendario_bp)
app.register_blueprint(planes_bp)
app.register_blueprint(inbox_bp)
app.register_blueprint(friends_bp)
app.register_blueprint(grupo_planes_bp)
app.register_blueprint(chat)
app.register_blueprint(chatbot_bp)
app.register_blueprint(inicio_bp)
app.register_blueprint(guia_bp)
app.register_blueprint(avatar_bp)
app.register_blueprint(deudas_bp)
app.register_blueprint(social_api)
invitation_service = InvitationService()
friend_service = FriendService()
deuda_service = DeudaService()
plan_service = PlanService()
social_service = SocialService()


PLANS = [
    {"id": 1, "slug": "caminata-atardecer", "title": "Caminata al atardecer + café", "type": "tranquilo", "description": "Caminen sin rumbo durante un rato, encuentren un café que no conozcan y terminen viendo caer el sol.", "time": "1 h 40 min", "cost": "$", "distance": "1,8 km", "mood": "Salir", "tone": "coral"},
    {"id": 2, "slug": "feria-y-merienda", "title": "Feria, algo rico y una plaza", "type": "compartir", "description": "Un recorrido breve por una feria cercana, una merienda compartida y un rato al aire libre.", "time": "2 h 15 min", "cost": "$$", "distance": "2,4 km", "mood": "Compartir", "tone": "moss"},
    {"id": 3, "slug": "noche-de-preguntas", "title": "Noche de preguntas sin pantallas", "type": "en casa", "description": "Armen equipos, preparen algo para tomar y dejen que las preguntas hagan el resto.", "time": "1 h 30 min", "cost": "$", "distance": "0 km", "mood": "Bajar un cambio", "tone": "lilac"},
]

@app.errorhandler(404)
def pagina_no_encontrada(error):
    return render_template("error.html", codigo=404, titulo="No encontramos esa página.",
                           detalle="Puede que el enlace esté viejo o que la dirección tenga un error."), 404


@app.errorhandler(500)
def error_del_servidor(error):
    return render_template("error.html", codigo=500, titulo="Algo salió mal de nuestro lado.",
                           detalle="Probá de nuevo en un momento. Si sigue pasando, contanos desde Contacto."), 500


# iOS pide /apple-touch-icon.png en la raíz cuando una página no declara el ícono (o lo declara tarde);
# se sirve el mismo archivo de static.
@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    return send_from_directory(app.static_folder, "apple-touch-icon.png", max_age=86400)


# Fechas en lenguaje de todos los días ("hoy", "mañana", "el sábado"): ver services/fechas.py.
from services.fechas import cuando as _cuando, dia_relativo as _dia_relativo
app.jinja_env.filters["dia_rel"] = _dia_relativo
app.jinja_env.filters["cuando"] = lambda fecha, hora=None: _cuando(fecha, hora)


@app.context_processor
def inject_user():
    datos = {
        "logueado": bool(session.get("user_id")),
        "current_user": session.get("user", {}),
    }
    # Versión de la foto de perfil propia (None si no eligió): cambia al cambiar la foto, así el navegador no usa una vieja.
    if session.get("user_id"):
        version = session.get("avatar_v")
        if version is None:
            try:
                version = AvatarService().version(session["user_id"]) or 0
            except Exception as e:
                print(f"No se pudo leer la foto de perfil: {e}")
                version = 0
            session["avatar_v"] = version
        datos["mi_avatar_v"] = version or None
    # La guía de bienvenida solo aparece en el navegador donde se creó la cuenta, hasta que se termina.
    datos["guia_nueva"] = bool(session.get("user_id")) and es_guia_pendiente(request.cookies, (session.get("user") or {}).get("email"))
    # El contador del Inbox tiene que verse en TODAS las páginas que usan la
    # barra lateral, no solo en /dashboard. Se inyecta acá para cualquier
    # template; como _inbox_guardado cachea 30 s, no suma viajes a la base
    # en cada página.
    if session.get("user_id"):
        try:
            _, datos["notificaciones_pendientes"] = _inbox_guardado(session["user_id"])
        except Exception as e:
            print(f"No se pudo contar las notificaciones: {e}")
            datos["notificaciones_pendientes"] = 0
        datos["deudas_pendientes"] = _deudas_guardado(session["user_id"])
    return datos


# ---- Medición: imprime cuánto tardó cada request (sacar cuando no haga falta) ----
@app.before_request
def _empezar_cronometro():
    g._inicio = time.perf_counter()


@app.after_request
def _mostrar_tiempo(response):
    if hasattr(g, "_inicio") and not request.path.startswith("/static"):
        print(f"{request.method} {request.path} -> {(time.perf_counter() - g._inicio) * 1000:.0f} ms")
    return response

# ---- Inbox guardado en memoria ----
# El dashboard no consulta la base cada vez que se entra: usa lo que se
# guardó y lo vuelve a pedir recién cuando pasaron 30 segundos.
_SEGUNDOS_INBOX = 30
_inbox_cache = {}  # user_id -> (invitaciones, cantidad, momento)


def _inbox_guardado(user_id):
    guardado = _inbox_cache.get(user_id)
    if guardado and time.monotonic() - guardado[2] < _SEGUNDOS_INBOX:
        return guardado[0], guardado[1]

    invitaciones = invitation_service.get_invitations_for_user(user_id)
    solicitudes = friend_service.get_requests_for_user(user_id)
    cantidad = len(invitaciones) + len(solicitudes)
    # Los me gusta y comentarios nuevos también suman. Si todavía no existe la
    # tabla de avisos, el contador sigue funcionando sin ellos.
    try:
        cantidad += social_service.contar_avisos_no_leidos(user_id)
    except Exception as e:
        print(f"No se pudieron contar los avisos de publicaciones: {e}")
    _inbox_cache[user_id] = (invitaciones, cantidad, time.monotonic())
    return invitaciones, cantidad


_deudas_cache = {}  # user_id -> (a cuántas personas les debe, momento)


def _deudas_guardado(user_id):
    guardado = _deudas_cache.get(user_id)
    if guardado and time.monotonic() - guardado[1] < _SEGUNDOS_INBOX:
        return guardado[0]
    try:
        cantidad = deuda_service.contar_que_debo(user_id)
    except Exception as e:  # por ejemplo, si todavía no se corrió migraciones/deudas.sql
        print(f"No se pudieron contar las deudas: {e}")
        cantidad = 0
    _deudas_cache[user_id] = (cantidad, time.monotonic())
    return cantidad


@app.before_request
def _borrar_inbox_guardado():
    # Si el usuario acepta/rechaza algo (cualquier POST), o abre el Inbox
    # (donde se marcan los avisos como leídos), se borra lo guardado para que
    # el contador se actualice al momento.
    if session.get("user_id") and (request.method == "POST" or request.path == "/inbox"):
        _inbox_cache.pop(session["user_id"], None)
        _deudas_cache.pop(session["user_id"], None)


@app.route('/')
def home():
    return render_template('home.html', featured=PLANS[0], plans=PLANS)

@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect('/login')
    invitaciones, _ = _inbox_guardado(session["user_id"])
    # Lo que espera tu voto en todos tus grupos (se refresca solo desde el navegador, ver routes/inicio.py).
    try:
        pendientes_datos = InicioService().pendientes(session["user_id"])
    except Exception as e:
        print(f"No se pudieron leer las votaciones pendientes: {e}")
        pendientes_datos = None
    try:
        proximo_plan = InicioService().proximo_plan(session["user_id"])
    except Exception as e:
        print(f"No se pudo leer el proximo plan: {e}")
        proximo_plan = None
    try:
        primeros_pasos = InicioService().primeros_pasos(session["user_id"])
    except Exception as e:
        print(f"No se pudieron calcular los primeros pasos: {e}")
        primeros_pasos = None
    # Las sugerencias de la semana solo se leen si ya están armadas; si no, la página las pide y se arman ahí.
    try:
        sugerencias_semana = SugerenciaService().existentes(session["user_id"])
    except Exception as e:
        print(f"No se pudieron leer las sugerencias: {e}")
        sugerencias_semana = []
    return render_template('home.html', featured=PLANS[0], plans=PLANS, dashboard=True,
                           invitaciones=invitaciones, pendientes_datos=pendientes_datos,
                           proximo_plan=proximo_plan, sugerencias_semana=sugerencias_semana,
                           primeros_pasos=primeros_pasos)

@app.route('/tutorial')
def tutorial():
    if not session.get('user_id'):
        return redirect('/login')
    return render_template('tutorial.html')

@app.route('/social')
def social():
    if not session.get('user_id'):
        return redirect('/login')

    # Amigos y Descubrir son el feed de publicaciones: la página solo trae el
    # armazón y static/social.js lo llena con /social/feed. Actividad es la
    # lista automática de lo que hicieron los amigos.
    pestana = request.args.get('tab', 'amigos')
    if pestana not in ('amigos', 'descubrir', 'actividad'):
        pestana = 'amigos'

    if pestana != 'actividad':
        return render_template('social.html', pestana=pestana, es_moderador=es_moderador())

    nivel_pedido = request.args.get('nivel', '4')
    if nivel_pedido == 'todos':
        nivel = None
    else:
        try:
            nivel = int(nivel_pedido)
        except ValueError:
            nivel = 4
        if nivel not in PlanService.NIVELES_SOCIAL:
            nivel = 4

    plan_service.archivar_vencidos()
    sugerencias = plan_service.get_sugerencias_amigos(session['user_id'], nivel)
    return render_template('social.html', pestana=pestana, **sugerencias)

@app.route('/explorar')
def explorar():
    return render_template('explorar.html', plans=PLANS)

@app.route('/plan/<slug>')
def plan(slug):
    selected = next((item for item in PLANS if item['slug'] == slug), PLANS[0])
    return render_template('plan.html', plan=selected)

@app.route('/productos')
def productos():
    return redirect('/explorar')

@app.route('/producto/<int:id>')
def ver_producto(id):
    selected = next((item for item in PLANS if item['id'] == id), PLANS[0])
    return render_template('plan.html', plan=selected)

@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    enviado = request.method == 'POST'
    return render_template('contacto.html', enviado=enviado)

if __name__ == '__main__':
    app.run(debug=True)
