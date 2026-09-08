from datetime import datetime

import psycopg2
from flask import Blueprint, redirect, render_template, request
from models.user import User
from services.auth_service import AuthService
from werkzeug.security import generate_password_hash

auth = Blueprint("auth", __name__)
auth_service = AuthService()

@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return redirect("/")
    return render_template("login.html")

@auth.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        form_data = request.form.to_dict()
        name = form_data.get("name", "").strip()
        birth_date_input = form_data.get("birth_date", "").strip()
        username = form_data.get("username", "").strip()
        email = form_data.get("email", "").strip()
        password = form_data.get("password", "")

        try:
            birth_date = datetime.strptime(birth_date_input, "%d/%m/%Y").date()
        except ValueError:
            return render_template(
                "register.html",
                error="Ingresá una fecha válida con el formato dd/mm/yyyy.",
                form_data=form_data,
            ), 400

        if birth_date > datetime.now().date():
            return render_template(
                "register.html",
                error="La fecha de nacimiento no puede ser posterior a hoy.",
                form_data=form_data,
            ), 400

        password_hash = generate_password_hash(password)
        # crear usuario y guardar usuario en BD
        try:
            auth_service.register(User(name, birth_date, username, email, password_hash))
            return render_template(
                "register.html",
                error="Se registró correctamente. Ahora podés iniciar sesión.",
                form_data=form_data,
            ), 400
        except ValueError as ve:
            print("ACA IRIA SI SE INTENTA CREAR UN USUARIO CON MAIL O USERNAME REPETIDO//// el auth_service.register lanza ValueError si el mail o username ya existen")
        except Exception as e:
            print(f"Error al registrar usuario: {e}")
            return render_template(
                "register.html",
                error="Hubo un error. Intenta nuevamente.",
                form_data=form_data,
            ), 400

    
    # El usuario simplemente entró a /register
    return render_template("register.html",error=None, form_data={})

@auth.route("/logout")
def logout():
    return redirect("/")
