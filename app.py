from flask import Flask, render_template, request
import psycopg2
from auth import auth
import os

app = Flask(__name__)

#registro todas las rutas que estan en auth.py.
app.register_blueprint(auth)

#PASS de la BD: AhoraQue2026
# ---- CONEXIÓN A LA BASE DE DATOS (Supabase / PostgreSQL) ----
# Reemplazá esto con el connection string que te da Supabase
# (Project Settings -> Database -> Connection String)
DB_URL = os.environ.get("DATABASE_URL", "postgresql://usuario:password@host:5432/basededatos")

def get_db_connection():
    conn = psycopg2.connect(DB_URL)
    return conn


# ---- RUTAS ----

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/productos')
def productos():
    # Ejemplo de cómo traer datos reales de una tabla.
    # Si todavía no tenés la tabla creada, comentá estas líneas
    # y usá la lista de ejemplo de abajo.
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, nombre, descripcion FROM productos;')
        filas = cur.fetchall()
        cur.close()
        conn.close()
        items = [{"id": f[0], "nombre": f[1], "descripcion": f[2]} for f in filas]

    except Exception as e:
        # Fallback con datos de ejemplo si la base no está lista todavía
        items = [
            {"id": 1, "nombre": "Mesa", "descripcion": "Mesa de madera, 4 personas"},
            {"id": 2, "nombre": "Silla", "descripcion": "Silla ergonómica"},
            {"id": 3, "nombre": "Lámpara", "descripcion": "Lámpara de pie, luz cálida"},
        ]
    return render_template('productos.html', items=items)


@app.route('/producto/<int:id>')
def ver_producto(id):
    return render_template('detalle_producto.html', id=id)


@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    mensaje_enviado = False
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        mensaje = request.form.get('mensaje')
        # Acá podrías guardar esto en la base de datos, ej:
        # conn = get_db_connection()
        # cur = conn.cursor()
        # cur.execute('INSERT INTO contactos (nombre, email, mensaje) VALUES (%s, %s, %s)',
        #             (nombre, email, mensaje))
        # conn.commit()
        # cur.close()
        # conn.close()
        mensaje_enviado = True
    return render_template('contacto.html', enviado=mensaje_enviado)


if __name__ == '__main__':
    app.run(debug=True)