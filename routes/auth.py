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

        try:
            auth_service.register(User(name, birth_date, username, password_hash))
        except psycopg2.Error:
            return render_template(
                "register.html",
                error="No pudimos crear la cuenta. Revisá los datos e intentá nuevamente.",
                form_data=form_data,
            ), 500

        return redirect("/login")

    # El usuario simplemente entró a /register
    return render_template("register.html")

@auth.route("/logout")
def logout():
    return redirect("/")
