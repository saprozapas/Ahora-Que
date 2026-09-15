from flask import Blueprint, redirect, render_template, request, session, url_for
from services.auth_service import AuthService

profile = Blueprint("profile", __name__)
auth_service = AuthService()

@profile.route("/perfil", methods=["GET", "POST"])
def perfil():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    user = session.get("user", {})

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        descripcion = request.form.get("descripcion", "").strip()

        ok, error = auth_service.update_profile(session["user_id"], name, username, descripcion)
        if not ok:
            return render_template("perfil.html", user=user, groups=[], published_plans=[], saved_plans=[], error=error)

        session["user"] = {**user, "name": name, "username": username, "descripcion": descripcion}
        user = session["user"]

    return render_template(
        "perfil.html",
        user=user,
        groups=[],
        published_plans=[],
        saved_plans=[],
    )