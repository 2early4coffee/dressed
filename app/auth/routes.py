import logging
from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint, render_template, request, session,
    redirect, url_for, flash, g, current_app,
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import User, Profile, Trip, Feedback, LoginAttempt, AnonymousSession

logger = logging.getLogger(__name__)

auth = Blueprint("auth", __name__)

# Helpers
def _check_rate_limit(ip_address: str) -> bool:
    max_attempts    = current_app.config.get("LOGIN_MAX_ATTEMPTS",    5)
    lockout_minutes = current_app.config.get("LOGIN_LOCKOUT_MINUTES", 10)
    cutoff          = datetime.now(timezone.utc) - timedelta(minutes=lockout_minutes)

    failure_count = LoginAttempt.query.filter(
        LoginAttempt.ip_address  == ip_address,
        LoginAttempt.success     == False,
        LoginAttempt.attempted_at >= cutoff,
        ).count()

    return failure_count >= max_attempts


def _log_attempt(ip_address: str, username: str, success: bool) -> None:
    attempt = LoginAttempt(
        ip_address   = ip_address,
        username     = username,
        success      = success,
        attempted_at = datetime.now(timezone.utc),
    )
    db.session.add(attempt)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


def _migrate_anon_data(anon_token: str, user_id: int) -> None:
    try:
        # Migrate trips
        Trip.query.filter_by(session_token=anon_token).update(
            {"user_id": user_id, "session_token": None},
            synchronize_session="fetch",
        )

        # Migrate profile
        Profile.query.filter_by(session_token=anon_token).update(
            {"user_id": user_id, "session_token": None},
            synchronize_session="fetch",
        )

        # Migrate feedback
        Feedback.query.filter_by(session_token=anon_token).update(
            {"user_id": user_id, "session_token": None},
            synchronize_session="fetch",
        )

        # Delete the anonymous session record
        AnonymousSession.query.filter_by(token=anon_token).delete(
            synchronize_session="fetch"
        )

        db.session.commit()
        logger.info("Migrated anon session %s... to user %d", anon_token[:8], user_id)

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Anon migration failed: %s", e)


def _validate_password(password: str) -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number.")
    if not any(not c.isalnum() for c in password):
        errors.append("Password must contain at least one special character.")
    return errors

# Register

@auth.route("/register", methods=["GET"])
def register():
    if g.user_id:
        return redirect(url_for("main.index"))
    return render_template("register.html")


@auth.route("/register", methods=["POST"])
def register_post():
    username    = request.form.get("username", "").strip().lower()
    password    = request.form.get("password", "")
    confirm     = request.form.get("confirm",  "")

    errors = []

    # Username validation
    if not username:
        errors.append("Username is required.")
    elif len(username) < 3:
        errors.append("Username must be at least 3 characters.")
    elif len(username) > 80:
        errors.append("Username must be 80 characters or fewer.")
    elif not all(c.isalnum() or c == "_" for c in username):
        errors.append("Username may only contain letters, numbers, and underscores.")
    elif User.query.filter_by(username=username).first():
        errors.append("That username is already taken.")

    # Password validation
    if not password:
        errors.append("Password is required.")
    else:
        errors.extend(_validate_password(password))

    if password and password != confirm:
        errors.append("Passwords do not match.")

    if errors:
        return render_template("register.html", errors=errors, username=username)

    # Create user
    new_user = User(
        username = username,
        hash     = generate_password_hash(password),
    )
    db.session.add(new_user)

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("User creation failed: %s", e)
        return render_template(
            "register.html",
            errors   = ["Account creation failed. Please try again."],
            username = username,
        )

    # Migrate anonymous session data
    anon_token = request.cookies.get("dressed_anon_token")
    if anon_token:
        _migrate_anon_data(anon_token, new_user.id)

    # Log the user in
    session.clear()
    session["user_id"] = new_user.id
    session.permanent  = True

    logger.info("New user registered: %s", username)
    flash("Welcome to Dressed! Your account has been created.", "success")

    # Redirect to profile setup so they can set preferences immediately
    return redirect(url_for("main.profile"))

# Login

@auth.route("/login", methods=["GET"])
def login():
    # Login form.
    if g.user_id:
        return redirect(url_for("main.index"))
    return render_template("login.html")


@auth.route("/login", methods=["POST"])
def login_post():
    ip_address = request.remote_addr
    username   = request.form.get("username", "").strip().lower()
    password   = request.form.get("password", "")

    # Rate limit check - before any DB query
    if _check_rate_limit(ip_address):
        return render_template(
            "login.html",
            error    = "Too many failed attempts. Please try again in 10 minutes.",
            username = username,
        )

    # Generic error message
    GENERIC_ERROR = "Invalid username or password."

    if not username or not password:
        return render_template("login.html", error=GENERIC_ERROR, username=username)

    # Look up user
    user = User.query.filter_by(username=username, deleted_at=None).first()

    if user is None or not check_password_hash(user.hash, password):
        _log_attempt(ip_address, username, success=False)
        return render_template("login.html", error=GENERIC_ERROR, username=username)

    # Success
    _log_attempt(ip_address, username, success=True)

    # Clear old session before setting new user_id (session fixation prevention)
    session.clear()
    session["user_id"] = user.id
    session.permanent  = True

    logger.info("User logged in: %s", username)

    # Redirect to the page they were trying to reach, or home
    next_url = request.args.get("next") or url_for("main.index")

    # Security: only redirect to relative URLs (prevent open redirect)
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)

    return redirect(url_for("main.index"))

# Logout
@auth.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))