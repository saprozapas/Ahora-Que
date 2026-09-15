from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from services.auth_service import AuthService

profile = Blueprint("profile", __name__)
auth_service = AuthService()

@profile.route("/perfil", methods=["GET", "POST"])
def perfil():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    user = session.get("user", {})
    error_name = ""
    error_username = ""
    error_descripcion = ""

    if request.method == "POST":
        target = request.form.get("target", "")
        es_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        if target == "name":
            name = request.form.get("name", "").strip()
            ok, error = auth_service.update_name(session["user_id"], name)
            user = {**user, "name": name}
            if ok:
                session["user"] = user
            else:
                error_name = error
            if es_ajax:
                return jsonify(ok=ok, error=error, value=name)

        elif target == "username":
            username = request.form.get("username", "").strip()
            ok, error = auth_service.update_username(session["user_id"], username)
            user = {**user, "username": username}
            if ok:
                session["user"] = user
            else:
                error_username = error
            if es_ajax:
                return jsonify(ok=ok, error=error, value=username)

        elif target == "descripcion":
            descripcion = request.form.get("descripcion", "").strip()
            ok, error = auth_service.update_descripcion(session["user_id"], descripcion)
            user = {**user, "descripcion": descripcion}
            if ok:
                session["user"] = user
            else:
                error_descripcion = error
            if es_ajax:
                return jsonify(ok=ok, error=error, value=descripcion)

    return render_template(
        "perfil.html",
        user=user,
        groups=[],
        published_plans=[],
        saved_plans=[],
        error_name=error_name,
        error_username=error_username,
        error_descripcion=error_descripcion,
    )