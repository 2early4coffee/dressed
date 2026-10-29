import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class BaseConfig:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    @classmethod
    def validate(cls) -> None:
        if not cls.SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY environment variable is not set. "
            )
        if cls.SECRET_KEY in ("changeme", "dev", "secret", "password"):
            raise RuntimeError(
                f"SECRET_KEY is set to a weak placeholder value: '{cls.SECRET_KEY}'. "
            )

    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 55,        # recycle connections every 55 seconds
        "pool_size": 5,             # max persistent connections in pool
        "max_overflow": 10,         # extra connections allowed above pool_size
        "connect_args": {
            "connect_timeout": 10,  # seconds before giving up on a new connection
        },
    }

      # Session + cookies
    SESSION_PERMANENT: bool = True
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(days=30)

    SESSION_COOKIE_NAME: str = "dressed_session"

    WTF_CSRF_ENABLED: bool = True

    # CSRF token expires after 1 hour of inactivity.
    WTF_CSRF_TIME_LIMIT: int = 3600


    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024   # 16 MB upload limit
    ALLOWED_IMAGE_EXTENSIONS: set = {"jpg", "jpeg", "png", "webp"}

    FORECAST_CACHE_TTL_SECONDS: int = 3600        # 1 hour

    # Timer for how long anonymous session tokens live before expiry cleanup.
    ANONYMOUS_SESSION_TTL_DAYS: int = 30

    # Rate limiting — max requests per window per user/session.
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 3600         # per hour

    # Login brute-force protection.
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 10

    NOMINATIM_USER_AGENT: str = "Dressed/1.0 (walteniumroy@gmail.com)"

    # Open-Meteo request timeout in seconds.
    WEATHER_REQUEST_TIMEOUT: int = 8

    # Altitude threshold in metres above which high_altitude context flag is set.
    HIGH_ALTITUDE_THRESHOLD_M: int = 2500


class DevelopmentConfig(BaseConfig):

    DEBUG: bool = True
    TESTING: bool = False

    WTF_CSRF_ENABLED: bool = False

    SQLALCHEMY_ECHO: bool = False

    # Relax cookie security for localhost (HTTP, not HTTPS).
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # Shorter cache TTL in dev so you see fresh data quickly.
    FORECAST_CACHE_TTL_SECONDS: int = 300          # 5 minutes in dev


class TestingConfig(BaseConfig):

    TESTING: bool = True
    DEBUG: bool = False
    WTF_CSRF_ENABLED: bool = False
    SQLALCHEMY_ECHO: bool = False

    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://localhost/dressed_test",
    )

    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
        "pool_size": 1,
        "max_overflow": 0,
    }

    SECRET_KEY: str = "test-secret-key-not-for-production"

    # Disable rate limiting in tests so tests don't need to artificially space out API requests.
    RATE_LIMIT_REQUESTS: int = 10_000

    # Very short session lifetime for session expiry tests.
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(minutes=5)

    # Reduce anonymous session TTL for cleanup tests.
    ANONYMOUS_SESSION_TTL_DAYS: int = 1

class ProductionConfig(BaseConfig):

    DEBUG: bool = False
    TESTING: bool = False

    # CSRF must be on in production — no exceptions.
    WTF_CSRF_ENABLED: bool = True

    # No SQL logging in production this keeps logs clean and avoids accidentally logging query parameters that contain user data.
    SQLALCHEMY_ECHO: bool = False

    # Hardened cookie settings.
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # Render sets PORT automatically. Gunicorn binds to it.
    PORT: int = int(os.environ.get("PORT", 10000))

config: dict = {
    "development": DevelopmentConfig,
    "testing":     TestingConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}