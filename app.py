import time

from flask import Flask, g, render_template, request, redirect, session
from routes.auth import auth
from routes.group_auth import group_auth
from routes.profile import profile
from routes.inbox import inbox_bp
from datetime import timedelta
from routes.calendario import calendario_bp
from routes.planes import planes_bp
from routes.friends import friends_bp
from services.invitation_service import InvitationService
from services.friend_service import FriendService


app = Flask(__name__)
app.secret_key = "7f4a9c2e8b1d6f03a5c9e7b2d4f8a1c6e3b9d5f7a2c8e4b6d1f9a3c7e5b2d8"
app.permanent_session_lifetime = timedelta(days=5)
app.register_blueprint(auth)
app.register_blueprint(group_auth)
app.register_blueprint(profile)
app.register_blueprint(calendario_bp)
app.register_blueprint(planes_bp)
app.register_blueprint(inbox_bp)
app.register_blueprint(friends_bp)
invitation_service = InvitationService()
friend_service = FriendService()


PLANS = [
    {"id": 1, "slug": "caminata-atardecer", "title": "Caminata al atardecer + café", "type": "tranquilo", "description": "Caminen sin rumbo durante un rato, encuentren un café que no conozcan y terminen viendo caer el sol.", "time": "1 h 40 min", "cost": "$", "distance": "1,8 km", "mood": "Salir", "tone": "coral"},
    {"id": 2, "slug": "feria-y-merienda", "title": "Feria, algo rico y una plaza", "type": "compartir", "description": "Un recorrido breve por una feria cercana, una merienda compartida y un rato al aire libre.", "time": "2 h 15 min", "cost": "$$", "distance": "2,4 km", "mood": "Compartir", "tone": "moss"},
    {"id": 3, "slug": "noche-de-preguntas", "title": "Noche de preguntas sin pantallas", "type": "en casa", "description": "Armen equipos, preparen algo para tomar y dejen que las preguntas hagan el resto.", "time": "1 h 30 min", "cost": "$", "distance": "0 km", "mood": "Bajar un cambio", "tone": "lilac"},
]

@app.context_processor
def inject_user():
    return {
        "logueado": bool(session.get("user_id")),
        "current_user": session.get("user", {}),
    }


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
    notificaciones = invitaciones + solicitudes
    _inbox_cache[user_id] = (invitaciones, len(notificaciones), time.monotonic())
    return invitaciones, len(notificaciones)


@app.before_request
def _borrar_inbox_guardado():
    # Si el usuario acepta/rechaza algo (cualquier POST), se borra lo
    # guardado para que el contador se actualice al momento.
    if request.method == "POST" and session.get("user_id"):
        _inbox_cache.pop(session["user_id"], None)


@app.route('/')
def home():
    return render_template('home.html', featured=PLANS[0], plans=PLANS)

@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect('/login')
    invitaciones, cantidad = _inbox_guardado(session["user_id"])
    return render_template('home.html', featured=PLANS[0], plans=PLANS, dashboard=True,
                           invitaciones=invitaciones,
                           notificaciones_pendientes=cantidad)

@app.route('/social')
def social():
    if not session.get('user_id'):
        return redirect('/login')
    return render_template('social.html', featured=PLANS[0])

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