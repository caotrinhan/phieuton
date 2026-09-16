from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user

from ..models import User


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, is_active_user=True).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("main.dashboard"))
        flash("Email hoặc mật khẩu không đúng.", "error")
    return render_template("login.html")


@auth_bp.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
