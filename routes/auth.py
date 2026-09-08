from flask import Blueprint, render_template, request, redirect
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
        # El usuario apreto "Registrarse"

        name = request.form["name"]
        birth_date = request.form["birth_date"]
        username = request.form["username"]
        password = request.form["password"]


        # validar datos
        password_hash = generate_password_hash(password)
        # crear usuario y guardar usuario en BD
        auth_service.register(User(name, birth_date, username, password_hash))
        

        return redirect("/login")

    # El usuario simplemente entró a /register
    return render_template("register.html")

@auth.route("/logout")
def logout():
    return redirect("/")
