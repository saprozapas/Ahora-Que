import time
from concurrent.futures import ThreadPoolExecutor

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
from routes.inicio import guia_bp, inicio_bp, invalidar_pendientes
from routes.avatar import avatar_bp
from routes.push import push_bp
from services.avatar_service import AvatarService
from routes.deudas import deudas_bp
from routes.suscripcion import suscripcion_bp
from routes.crear import crear_bp
from services.inicio_service import InicioService
from services.paralelo_service import correr_en_paralelo
from services.guia_nueva import es_guia_pendiente
from services.sugerencia_service import SugerenciaService
from routes.social import es_moderador, social_api
from services.invitation_service import InvitationService
from services.friend_service import FriendService
from services.deuda_service import DeudaService
from services.suscripcion_service import PLANES_IA_GRATIS_POR_SEMANA, PRECIOS, SuscripcionService
from services.plan_service import PlanService
from services.social_service import SocialService


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
app.config.update(
    BREVO_API_KEY=os.environ.get("BREVO_API_KEY"),
    BREVO_SENDER_EMAIL=os.environ.get("BREVO_SENDER_EMAIL"),
    BREVO_SENDER_NAME=os.environ.get("BREVO_SENDER_NAME", "Ahora Qué"),
    VAPID_PUBLIC_KEY=os.environ.get("VAPID_PUBLIC_KEY", ""),
    VAPID_PRIVATE_KEY=os.environ.get("VAPID_PRIVATE_KEY", ""),
    VAPID_SUBJECT=os.environ.get(
        "VAPID_SUBJECT",
        f'mailto:{os.environ.get("BREVO_SENDER_EMAIL", "admin@example.com")}',
    ),
)
app.permanent_session_lifetime = timedelta(days=5)

# Comprime las respuestas de texto (HTML, CSS, JS, JSON, SVG): viajan en una fracción del tamaño. Si el paquete no está instalado, la app sigue igual.
try:
    from flask_compress import Compress
    app.config.update(COMPRESS_MIMETYPES=["text/html", "text/css", "text/plain", "text/javascript", "application/javascript",
                                          "application/json", "image/svg+xml"], COMPRESS_MIN_SIZE=400, COMPRESS_ALGORITHM=["br", "gzip"])
    Compress(app)
except ImportError:
    print("flask-compress no está instalado: las respuestas van sin comprimir.")
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
app.register_blueprint(suscripcion_bp)
app.register_blueprint(crear_bp)
app.register_blueprint(social_api)
app.register_blueprint(push_bp)
invitation_service = InvitationService()
friend_service = FriendService()
deuda_service = DeudaService()
suscripcion_service = SuscripcionService()
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
app.jinja_env.globals["avatar_v"] = AvatarService.version_de
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
        uid = session["user_id"]
        # Tres lecturas independientes: salen a la vez (con la caché vencida eran unos siete viajes seguidos a la base).
        datos["notificaciones_pendientes"], datos["deudas_pendientes"], datos["es_premium"] = _en_paralelo(
            (lambda: _inbox_guardado(uid)[1], 0, "las notificaciones"),
            (lambda: _deudas_guardado(uid), 0, "las deudas"),
            (lambda: _premium_guardado(uid), False, "el plan del usuario"),
        )
    return datos


# ---- Medición: imprime cuánto tardó cada request (sacar cuando no haga falta) ----
@app.before_request
def _empezar_cronometro():
    g._inicio = time.perf_counter()


@app.after_request
def _cache_de_estaticos(response):
    """Los archivos de /static llevan su versión en la dirección (?v=…): se pueden guardar un año. Sin versión, un día."""
    if request.path.startswith("/static/") and response.status_code == 200:
        if request.args.get("v"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/healthz")
def healthz():
    """Para que Render (o un servicio que visite la página cada pocos minutos) sepa que la app está viva, sin tocar la base."""
    return "ok", 200, {"Cache-Control": "no-store"}


@app.after_request
def _mostrar_tiempo(response):
    if hasattr(g, "_inicio") and not request.path.startswith("/static"):
        print(f"{request.method} {request.path} -> {(time.perf_counter() - g._inicio) * 1000:.0f} ms")
    return response


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
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

    def avisos_sin_leer():
        # Los me gusta y comentarios nuevos también suman. Si todavía no existe la
        # tabla de avisos, el contador sigue funcionando sin ellos.
        try:
            return social_service.contar_avisos_no_leidos(user_id)
        except Exception as e:
            print(f"No se pudieron contar los avisos de publicaciones: {e}")
            return 0

    invitaciones, solicitudes, avisos = correr_en_paralelo(
        lambda: invitation_service.get_invitations_for_user(user_id),
        lambda: friend_service.get_requests_for_user(user_id),
        avisos_sin_leer,
    )
    cantidad = len(invitaciones) + len(solicitudes) + avisos
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


_premium_cache = {}  # user_id -> (es premium, momento)


def _premium_guardado(user_id):
    guardado = _premium_cache.get(user_id)
    if guardado and time.monotonic() - guardado[1] < _SEGUNDOS_INBOX:
        return guardado[0]
    try:
        premium = suscripcion_service.es_premium(user_id)
    except Exception as e:  # por ejemplo, si todavía no se corrió migraciones/planes_suscripcion.sql
        print(f"No se pudo leer el plan del usuario: {e}")
        premium = False
    _premium_cache[user_id] = (premium, time.monotonic())
    return premium


@app.before_request
def _borrar_inbox_guardado():
    # Si el usuario acepta/rechaza algo (cualquier POST), o abre el Inbox
    # (donde se marcan los avisos como leídos), se borra lo guardado para que
    # el contador se actualice al momento.
    if session.get("user_id") and (request.method == "POST" or request.path == "/inbox"):
        _inbox_cache.pop(session["user_id"], None)
        _deudas_cache.pop(session["user_id"], None)
        invalidar_pendientes(session["user_id"])
        _premium_cache.pop(session["user_id"], None)  # pagar o cancelar el plan se ve al instante


@app.route('/')
def home():
    user_agent = request.headers.get("User-Agent", "").lower()

    es_celular = any(palabra in user_agent for palabra in [
        "iphone",
        "ipad",
        "android",
        "mobile"
    ])
    if session.get('user_id') and es_celular:
        return redirect('/dashboard')
    return render_template('home.html', featured=PLANS[0], plans=PLANS)

def _en_paralelo(*tareas):
    """Corre varias lecturas independientes a la vez. Cada tarea es (función, valor si falla, qué lee)."""
    def correr(tarea):
        funcion, por_defecto, que = tarea
        try:
            return funcion()
        except Exception as e:
            print(f"No se pudo leer {que}: {e}")
            return por_defecto

    with ThreadPoolExecutor(max_workers=len(tareas)) as pool:
        return list(pool.map(correr, tareas))


@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect('/login')
    try:
        plan_service.archivar_vencidos()
    except Exception as e:
        print(f"No se pudieron actualizar los planes para puntuar: {e}")
    invitaciones, _ = _inbox_guardado(session["user_id"])
    # Cuatro lecturas que no dependen una de otra: salen a la vez, así la página tarda lo de la más lenta y no la suma de todas.
    uid = session["user_id"]
    pendientes_datos, proximo_plan, primeros_pasos, sugerencias_semana = _en_paralelo(
        (lambda: InicioService().pendientes(uid), None, "las votaciones pendientes"),
        (lambda: InicioService().proximo_plan(uid), None, "el próximo plan"),
        (lambda: InicioService().primeros_pasos(uid), None, "los primeros pasos"),
        # Las sugerencias de la semana solo se leen si ya están armadas; si no, la página las pide y se arman ahí.
        (lambda: SugerenciaService().existentes(uid), [], "las sugerencias"),
    )
    return render_template('home.html', featured=PLANS[0], plans=PLANS, dashboard=True,
                           invitaciones=invitaciones, pendientes_datos=pendientes_datos,
                           proximo_plan=proximo_plan, sugerencias_semana=sugerencias_semana,
                           primeros_pasos=primeros_pasos)

@app.route('/tutorial')
def tutorial():
    if not session.get('user_id'):
        return redirect('/login')
    return render_template('tutorial.html')

@app.route('/premium')
def premium():
    # Por ahora solo muestra los planes: todavía no hay sistema de pago.
    if not session.get('user_id'):
        return redirect('/login')
    return render_template('premium.html', ia_gratis_por_semana=PLANES_IA_GRATIS_POR_SEMANA, precios=PRECIOS)

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