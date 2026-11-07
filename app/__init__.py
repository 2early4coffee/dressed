import os
import logging
from flask import Flask, render_template

from app.extensions import db, migrate, csrf , compress
from config import config

def create_app(env: str = None) -> Flask:

    env = env or os.getenv("FLASK_ENV", "development")
    cfg = config.get(env, config["default"])

    if env == "production":
        cfg.validate()

    app = Flask(
        __name__,

        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )

    app.config.from_object(cfg)

    from whitenoise import WhiteNoise
    app.wsgi_app = WhiteNoise(app.wsgi_app, root=app.static_folder, prefix="static", max_age=31536000, autorefresh=app.debug)

    # Initialise extensions

    db.init_app(app)



    # Bind Migrate to both the app and db so `flask db` commands work.
    migrate.init_app(app, db)

    csrf.init_app(app)

    compress.init_app(app)

    # Import models

    with app.app_context():
        from app import models  # noqa: F401 -- imported for side effects

    # Register blueprints

    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.auth.routes import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    # Configure logging
    _configure_logging(app)


    logging.getLogger('urllib3').setLevel(logging.WARNING)

    # Shell context
    @app.shell_context_processor
    def make_shell_context() -> dict:
        from app.models import (
            User,
            AnonymousSession,
            Profile,
            Trip,
            TripLeg,
            PackingItem,
            ForecastCache,
            Feedback,
            LoginAttempt,
        )
        return {
            "db":               db,
            "User":             User,
            "AnonymousSession": AnonymousSession,
            "Profile":          Profile,
            "Trip":             Trip,
            "TripLeg":          TripLeg,
            "PackingItem":      PackingItem,
            "ForecastCache":    ForecastCache,
            "Feedback":         Feedback,
            "LoginAttempt":     LoginAttempt,
        }

    return app

# Logging

def _configure_logging(app: Flask) -> None:

    if app.debug:
        log_level = logging.DEBUG
        fmt = "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    else:
        log_level = logging.WARNING
        fmt = "%(asctime)s %(levelname)s: %(message)s"

    logging.basicConfig(level=log_level, format=fmt)
    app.logger.setLevel(log_level)

    app.logger.info(
        "Dressed starting — env=%s debug=%s db_set=%s",
        os.getenv("FLASK_ENV", "development"),
        app.debug,
        bool(app.config.get("SQLALCHEMY_DATABASE_URI")),
    )