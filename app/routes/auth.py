from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user

from ..models import User, LoginLog
from ..extensions import db
from ..time_utils import local_now


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        # Lấy địa chỉ IP máy tính truy cập
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()

        user = User.query.filter_by(email=email, is_active_user=True).first()
        
        if user and user.check_password(password):
            login_user(user)
            # Ghi log thành công
            db.session.add(LoginLog(
                user_id=user.id,
                email_attempt=email,
                ip_address=ip_address or "Unknown",
                status="SUCCESS",
                logged_at=local_now()
            ))
            db.session.commit()
            return redirect(url_for("main.dashboard"))
            
        # Ghi log thất bại
        db.session.add(LoginLog(
            user_id=user.id if user else None,
            email_attempt=email,
            ip_address=ip_address or "Unknown",
            status="FAILED",
            logged_at=local_now()
        ))
        db.session.commit()
        
        flash("Email hoặc mật khẩu không đúng.", "error")
    return render_template("login.html")


@auth_bp.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))