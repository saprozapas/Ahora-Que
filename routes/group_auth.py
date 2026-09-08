from flask import Blueprint, render_template, request, redirect
from models.group import Group
from services.group_auth_service import GroupAuthService
from werkzeug.security import generate_password_hash

group_auth = Blueprint("group_auth", __name__)
group_auth_service = GroupAuthService()

@group_auth.route("/group_register", methods=["GET", "POST"])
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
        group_auth_service.register(Group(name, birth_date, username, password_hash))
        

        return redirect("/login")

    # El usuario simplemente entró a /group_register
    return render_template("group_register.html")
