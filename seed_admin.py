import os

from dotenv import load_dotenv

from app import create_app
from app.extensions import db
from app.models import User

load_dotenv()
app = create_app()
with app.app_context():
    email = input("Email admin: ").strip().lower()
    full_name = input("Họ tên: ").strip()
    unit = input("Đơn vị: ").strip()
    password = input("Mật khẩu: ")
    user = User(email=email, full_name=full_name, unit=unit, is_admin=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print("Đã tạo tài khoản admin.")
