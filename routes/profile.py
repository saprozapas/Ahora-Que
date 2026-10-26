from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from services.auth_service import AuthService
from services.avatar_service import AvatarService
from services.deuda_service import DeudaService
from services.plan_service import PlanService
from database_bridge.database_bridge import getUser
from werkzeug.security import check_password_hash, generate_password_hash
from services.password_policy import validar_contrasena

profile = Blueprint("profile", __name__)
auth_service = AuthService()
deuda_service = DeudaService()
plan_service = PlanService()

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
        if target == "banco":
            try:
                deuda_service.guardar_cuenta(session["user_id"], request.form.get("banco"), request.form.get("cuenta"))
                flash("Datos bancarios guardados.")
            except ValueError as e:
                flash(str(e))
            except Exception as e:
                print(f"No se pudo guardar la cuenta bancaria: {e}")
                flash("No se pudieron guardar los datos bancarios.")
            return redirect(url_for("profile.perfil"))
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

    # Los tres contadores de abajo (antes llegaban listas vacías y siempre decían 0).
    try:
        resumen = plan_service.contar_resumen_perfil(session["user_id"])
    except Exception as error:
        print(f"No se pudo armar el resumen del perfil: {error}")
        resumen = {"grupos": 0, "publicados": 0, "guardados": 0}

    try:
        cuenta = deuda_service.get_cuenta(session["user_id"])
    except Exception as error:  # por ejemplo, si todavía no se corrió migraciones/deudas_v2.sql
        print(f"No se pudo leer la cuenta bancaria: {error}")
        cuenta = {"banco": "", "cuenta": ""}

    return render_template(
        "perfil.html",
        user=user,
        cuenta=cuenta,
        resumen=resumen,
        autor_id=session["user_id"],
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
        elif (error_contrasena := validar_contrasena(nueva)):
            error = error_contrasena
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


@profile.route("/perfil/eliminar", methods=["POST"])
def eliminar_cuenta():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    hash_actual = auth_service.get_password_hash_by_id(session["user_id"])
    if hash_actual is None or not check_password_hash(hash_actual, request.form.get("password", "")):
        flash("La contraseña es incorrecta. No se eliminó la cuenta.")
        return redirect(url_for("profile.perfil"))

    try:
        auth_service.delete_user(session["user_id"])
    except Exception as e:
        print(f"No se pudo eliminar la cuenta: {e}")
        flash("No se pudo eliminar la cuenta. Probá de nuevo.")
        return redirect(url_for("profile.perfil"))

    session.clear()
    flash("Tu cuenta se eliminó.", "success")
    return redirect(url_for("auth.login"))


@profile.route("/usuarios/<user_id>")
def perfil_publico(user_id):
    """Perfil de otro usuario: solo lectura, sin ningún formulario."""
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    # Si es el propio usuario, no tiene sentido la vista de solo lectura.
    if str(user_id) == str(session.get("user_id")):
        return redirect(url_for("profile.perfil"))

    usuario = getUser(user_id)
    if usuario is None:
        abort(404)

    try:
        avatar_v = AvatarService().version(user_id)
    except Exception as e:
        print(f"No se pudo leer la foto de perfil: {e}")
        avatar_v = None
    return render_template("perfil_publico.html", usuario=usuario, autor_id=user_id, avatar_v=avatar_v)
