from datetime import datetime
import hashlib
import secrets

import psycopg2
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from models import user
from models.user import User
from services.auth_service import AuthService
from services.password_policy import validar_contrasena
from services.mail_service import MailService
from werkzeug.security import check_password_hash,generate_password_hash

auth = Blueprint("auth", __name__)
auth_service = AuthService()

@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        form_data = request.form.to_dict()
        username_or_email = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        resultado = auth_service.getUserAndId(username_or_email)

        user_id = resultado[1] if resultado else None
        if not auth_service.registrar_intento_login(username_or_email, user_id):
            return render_template(
                "login.html",
                mensaje="Alcanzaste el límite de 5 intentos. Probá de nuevo en 30 minutos.",
            ), 429

        if resultado is None:
            return render_template(
                "login.html",
                mensaje="Usuario o contraseña incorrectos."
            )

        user_login, id_login = resultado

        hash_pass = user_login.get_password_hash()

        if hash_pass is not None and check_password_hash(hash_pass, password):
            session.permanent = True
            session["user_id"] = id_login
            session["user"] = {
                "id": id_login,
                "name": user_login.get_name(),
                "username": user_login.get_username(),
                "email": user_login.get_email(),
                "descripcion": user_login.get_descripcion(),
            }
            return redirect("/dashboard")
        else:
            return render_template("login.html", mensaje="Usuario o contraseña incorrectos.")

    return render_template("login.html",mensaje = "")


########################################################################################################################
########################################################################################################################
########################################################################################################################

########################################################################################################################
########################################################################################################################
########################################################################################################################


@auth.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        form_data = request.form.to_dict()
        name = form_data.get("name", "").strip()
        birth_date_input = form_data.get("birth_date", "").strip()
        username = form_data.get("username", "").strip()
        email = form_data.get("email", "").strip()
        password = form_data.get("password", "")

        error_contrasena = validar_contrasena(password)
        if error_contrasena:
            return render_template(
                "register.html", error=error_contrasena, form_data=form_data
            ), 400

        if form_data.get("accept_terms") != "on":
            return render_template(
                "register.html",
                error="Tenés que aceptar los términos y condiciones para crear una cuenta.",
                form_data=form_data,
            ), 400

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
        # Guardamos una cuenta pendiente; Usuarios se escribe solo al confirmar.
        codigo = secrets.token_urlsafe(32)
        codigo_hash = hashlib.sha256(codigo.encode("utf-8")).hexdigest()
        pending_user_id = None
        try:
            pending_user_id = auth_service.create_pending_registration(
                User(name, birth_date, username, email, password_hash), codigo_hash
            )
            link_confirmacion = url_for(
                "auth.confirmar_email", codigo=codigo, _external=True
            )
            cuerpo = (
                f"Hola {name},\n\n"
                "Para confirmar tu correo y terminar de crear tu cuenta en Ahora Qué, "
                f"abrí este enlace:\n{link_confirmacion}\n\n"
                "El enlace vence en 24 horas. Si no pediste crear esta cuenta, podés ignorar este mensaje."
            )
            try:
                MailService().enviar(email, "Confirmá tu correo — Ahora Qué", cuerpo)
            except Exception:
                current_app.logger.exception("No se pudo enviar el correo de confirmación")
                auth_service.discard_pending_registration(pending_user_id)
                return render_template(
                    "register.html",
                    error="No pudimos enviar el correo de confirmación. Revisá tu dirección e intentá de nuevo.",
                    form_data=form_data,
                ), 503

            return redirect(url_for("auth.estado_confirmacion", user_id=pending_user_id))
        except ValueError:
            return render_template(
                "register.html",
                error="El mail o el nombre de usuario ya está en uso.",
                form_data=form_data,
            ), 400
        except psycopg2.errors.UniqueViolation as uv:
            constraint_name = uv.diag.constraint_name or ""
            if constraint_name.endswith("Username_key"):
                return render_template(
                    "register.html",
                    error="El nombre de usuario ya está en uso.",
                    form_data=form_data,
                ), 400
            else:
                return render_template(
                    "register.html",
                    error="El mail ingresado ya está en uso.",
                    form_data=form_data,
                ), 400
        except psycopg2.errors.UndefinedTable:
            current_app.logger.exception("Falta una tabla necesaria para completar el registro")
            return render_template(
                "register.html",
                error="Falta preparar la base de datos para confirmar registros. Ejecutá la migración de confirmación de correo.",
                form_data=form_data,
            ), 503
        except Exception:
            current_app.logger.exception("Error al registrar usuario")
            return render_template(
                "register.html",
                error="Hubo un error. Intenta nuevamente más tarde.",
                form_data=form_data,
            ), 400

    
    # El usuario simplemente entró a /register
    return render_template("register.html",error=None, form_data={})


@auth.route("/registro/confirmar/<codigo>")
def confirmar_email(codigo):
    codigo_hash = hashlib.sha256(codigo.encode("utf-8")).hexdigest()
    try:
        estado, user_id = auth_service.confirm_registration(codigo_hash)
    except psycopg2.errors.UniqueViolation:
        auth_service.discard_pending_by_code_hash(codigo_hash)
        estado, user_id = "conflicto", None

    if estado == "confirmado":
        return redirect(url_for("auth.estado_confirmacion", user_id=user_id))
    return render_template("confirmar_email.html", estado=estado, user_id=None)


@auth.route("/registro/estado/<uuid:user_id>")
def estado_confirmacion(user_id):
    estado = auth_service.get_registration_status(user_id)
    return render_template(
        "confirmar_email.html",
        estado=estado,
        user_id=user_id if estado == "pendiente" else None,
    )


@auth.route("/terminos-y-condiciones")
def terminos_y_condiciones():
    return render_template("terminos.html")

@auth.route("/logout")
def logout():
    session.clear()
    return redirect("/")
