from flask import Blueprint, render_template, request, redirect

auth = Blueprint("auth", __name__)

@auth.route("/login")
def login():
    return "Login"

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        # El usuario apreto "Registrarse"

        name = request.form["name"]
        birth_date = request.form["birth_date"]
        username = request.form["username"]
        password = request.form["password"]

        # validar datos
        # crear usuario
        # guardar usuario en BD

        return redirect("/login")

    # El usuario simplemente entró a /register
    return render_template("register.html")

@auth.route("/logout")
def logout():
    return "Logout"