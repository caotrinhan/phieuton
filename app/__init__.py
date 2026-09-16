from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from .extensions import db, login_manager

load_dotenv()

from config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["UPLOAD_DIR"] = Path(app.config["UPLOAD_DIR"])
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from . import models
    from .routes.auth import auth_bp
    from .routes.main import main_bp

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(models.User, int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

    return app
