from flask import Flask, render_template, request, redirect, session
from routes.auth import auth
from routes.group_auth import group_auth
from datetime import timedelta


app = Flask(__name__)
app.secret_key = "7f4a9c2e8b1d6f03a5c9e7b2d4f8a1c6e3b9d5f7a2c8e4b6d1f9a3c7e5b2d8"
app.permanent_session_lifetime = timedelta(days=5)
app.register_blueprint(auth)
app.register_blueprint(group_auth)
print("loolll")


PLANS = [
    {"id": 1, "slug": "caminata-atardecer", "title": "Caminata al atardecer + café", "type": "tranquilo", "description": "Caminen sin rumbo durante un rato, encuentren un café que no conozcan y terminen viendo caer el sol.", "time": "1 h 40 min", "cost": "$", "distance": "1,8 km", "mood": "Salir", "tone": "coral"},
    {"id": 2, "slug": "feria-y-merienda", "title": "Feria, algo rico y una plaza", "type": "compartir", "description": "Un recorrido breve por una feria cercana, una merienda compartida y un rato al aire libre.", "time": "2 h 15 min", "cost": "$$", "distance": "2,4 km", "mood": "Compartir", "tone": "moss"},
    {"id": 3, "slug": "noche-de-preguntas", "title": "Noche de preguntas sin pantallas", "type": "en casa", "description": "Armen equipos, preparen algo para tomar y dejen que las preguntas hagan el resto.", "time": "1 h 30 min", "cost": "$", "distance": "0 km", "mood": "Bajar un cambio", "tone": "lilac"},
]

@app.context_processor
def inject_user():
    return {
        "logueado": "user_id" in session#true or false
    }

@app.route('/')
def home():
    return render_template('home.html', featured=PLANS[0], plans=PLANS)

@app.route('/explorar')
def explorar():
    return render_template('explorar.html', plans=PLANS)

@app.route('/grupos')
def grupos():
    return render_template('grupos.html')

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
