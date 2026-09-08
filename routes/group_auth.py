from flask import Blueprint, render_template, request, redirect
from models.user import User
from werkzeug.security import generate_password_hash

group_auth = Blueprint("group_auth", __name__)

@group_auth.route("/register_group", methods=["GET", "POST"])
def register_group():
    if request.method == "POST":
        return redirect("/")
    return render_template("register_group.html")
