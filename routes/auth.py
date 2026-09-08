from flask import Blueprint, render_template, request, redirect
from models.user import User
from werkzeug.security import generate_password_hash

auth = Blueprint("auth", __name__)

@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return redirect("/")
    return render_template("login.html")

@auth.route("/register")
def register():
    return render_template("register.html")

@auth.route("/logout")
def logout():
    return redirect("/")
