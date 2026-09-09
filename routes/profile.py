from flask import Blueprint, redirect, render_template, session, url_for


profile = Blueprint("profile", __name__)


@profile.route("/perfil")
def perfil():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    user = session.get("user", {})
    return render_template(
        "perfil.html",
        user=user,
        groups=[],
        published_plans=[],
        saved_plans=[],
    )
