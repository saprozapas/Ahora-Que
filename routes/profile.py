from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from services.auth_service import AuthService
from werkzeug.security import check_password_hash, generate_password_hash

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


@profile.route("/perfil/cambiar-contrasena", methods=["GET", "POST"])
def cambiar_contrasena():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    error = ""
    exito = ""

    if request.method == "POST":
        actual = request.form.get("actual", "")
        nueva = request.form.get("nueva", "")
        confirmar = request.form.get("confirmar", "")

        hash_actual = auth_service.get_password_hash_by_id(session["user_id"])

        if hash_actual is None or not check_password_hash(hash_actual, actual):
            error = "La contraseña actual es incorrecta."
        # Esto es por si queremos hacer que la contraseña tenga un mínimo de caracteres, pero por ahora no lo hacemos.
        # elif len(nueva) < 8:
        #     error = "La nueva contraseña debe tener al menos 8 caracteres."
        elif nueva != confirmar:
            error = "Las contraseñas nuevas no coinciden."
        elif actual == nueva:
            error = "La nueva contraseña tiene que ser distinta a la actual."
        else:
            nuevo_hash = generate_password_hash(nueva)
            ok, err = auth_service.update_password(session["user_id"], nuevo_hash)
            if ok:
                session.clear()
                flash("Tu contraseña se actualizó correctamente. Iniciá sesión de nuevo.", "success")
                return redirect(url_for("auth.login"))
            else:
                error = err

    return render_template("cambiar_contrasena.html", error=error, exito=exito)