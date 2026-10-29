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
        static_folder="../static",
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

    # Register error handlers

    _register_error_handlers(app)

    # Configure logging

    _configure_logging(app)

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

# Error handlers

def _register_error_handlers(app: Flask) -> None:

    from flask import request, jsonify

    @app.errorhandler(400)
    def bad_request(e):
        if _wants_json(request):
            return jsonify({"error": "Bad request", "detail": str(e)}), 400
        return render_template("400.html"), 400

    @app.errorhandler(403)
    def forbidden(e):
        if _wants_json(request):
            return jsonify({"error": "Forbidden"}), 403
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if _wants_json(request):
            return jsonify({"error": "Not found"}), 404
        return render_template("404.html"), 404

    @app.errorhandler(429)
    def rate_limited(e):
        if _wants_json(request):
            return jsonify({"error": "Too many requests. Please slow down."}), 429
        return render_template("429.html"), 429

    @app.errorhandler(500)
    def internal_error(e):

        db.session.rollback()

        if _wants_json(request):
            return jsonify({"error": "Something went wrong on our end."}), 500

        # Log the actual exception server-side
        app.logger.error("Internal server error: %s", e, exc_info=True)

        return render_template("500.html"), 500

    @app.errorhandler(503)
    def service_unavailable(e):
        if _wants_json(request):
            return jsonify({"error": "Service temporarily unavailable."}), 503
        return render_template("503.html"), 503


def _wants_json(request) -> bool:
    if request.content_type and "application/json" in request.content_type:
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"

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