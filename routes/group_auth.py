from flask import Blueprint, render_template, request, redirect, session, url_for
from models.group import Group
from services.group_auth_service import GroupAuthService
from werkzeug.security import generate_password_hash
from database_bridge.database_bridge import getUser

group_auth = Blueprint("group_auth", __name__)
group_auth_service = GroupAuthService()


def _require_login():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    return None


@group_auth.route("/grupos")
def grupos():
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    return render_template("grupos.html", groups=[], groups_page=True)


@group_auth.route("/grupos/nuevo", methods=["GET", "POST"])
def nuevo_grupo():
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        form_data = request.form.to_dict()
        user_id = session.get("user_id")
        name = form_data["name"]
        description = form_data["description"]
        try:
            user = getUser(user_id)
        except Exception as e:
            return render_template("crear_grupos.html", error="Error al crear grupo. Intenta loguearte nuevamente.", form_data=form_data)

        try:
            group_auth_service.register(Group(user, name, description), user_id)
        except Exception as e:
            return render_template("crear_grupos.html", error="Error al crear el grupo.", form_data=form_data)

        return render_template("crear_grupos.html", error="Grupo creado exitosamente.", form_data={})

    return render_template("crear_grupos.html", 
                           error=None, 
                           form_data={})


@group_auth.route("/grupos/<int:group_id>")
def detalle_grupo(group_id):
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    return render_template("grupos.html", groups=[], groups_page=True, selected_group_id=group_id)


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
