"""Django settings for the Aarogyam Pathology lab dashboard.

All environment-specific values come from environment variables / `.env`
(see `.env.example`). Nothing secret lives in code.
"""
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CSRF_TRUSTED_ORIGINS=(list, ["https://localhost"]),
    SECURE_SSL_REDIRECT=(bool, True),
    USE_CDN_ASSETS=(bool, False),
    USE_X_ACCEL_REDIRECT=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-change-me" if DEBUG else environ.Env.NOTSET)
# As TGMA's ProductionConfig.validate(): a guessable key lets anyone forge a session
# cookie, and this app is reachable from the internet through the tunnel.
if not DEBUG and (len(SECRET_KEY) < 32 or SECRET_KEY.startswith(("change-me", "insecure-", "dev-only"))):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "SECRET_KEY is a placeholder or shorter than 32 characters. Generate one with: "
        'python -c "import secrets;print(secrets.token_urlsafe(50))"'
    )
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_filters",
    "import_export",
    "axes",
    "apps.core",
    "apps.audit",
    "apps.accounts",
    "apps.centres",
    "apps.patients",
    "apps.followups",
    "apps.retest",
    "apps.pricing",
    "apps.dashboard",
]

MIDDLEWARE = [
    "apps.core.middleware.HealthCheckMiddleware",  # must stay first (container healthcheck)
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
    "apps.core.middleware.RequestContextMiddleware",
    "apps.core.middleware.LoginRequiredMiddleware",
    "apps.core.middleware.ForcePasswordChangeMiddleware",
    "apps.core.middleware.NoIndexMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.app_context",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "apps.accounts.backends.UsernameOrPhoneBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"

# --- Sessions: 30 minute idle timeout -------------------------------------
SESSION_COOKIE_AGE = env.int("SESSION_IDLE_SECONDS", default=30 * 60)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# Own cookie names (TGMA uses tgma_session): several apps share the PowerEdge, and over an
# SSH port-forward they all live on localhost, where cookies are shared across ports.
SESSION_COOKIE_NAME = "aarogyam_session"
CSRF_COOKIE_NAME = "aarogyam_csrftoken"

# --- django-axes: lock after 5 failures ------------------------------------
AXES_FAILURE_LIMIT = 5
# 15-minute lock, as on TGMA. Admins can unlock sooner from the Users page.
AXES_COOLOFF_TIME = env.float("AXES_COOLOFF_HOURS", default=0.25)
# Lock per account. IP-based lockout is deliberately off: front-desk PCs share one
# office IP, so one typo-prone user would lock out the whole centre.
AXES_LOCKOUT_PARAMETERS = ["username"]
SILENCED_SYSTEM_CHECKS = ["axes.W006"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "accounts/locked.html"
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]

# --- Locale -----------------------------------------------------------------
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
DATE_FORMAT = "d-m-Y"
DATETIME_FORMAT = "d-m-Y H:i"
SHORT_DATE_FORMAT = "d-m-Y"
DATE_INPUT_FORMATS = ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"]
USE_THOUSAND_SEPARATOR = False

# --- Static & media ------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"]
_build_dir = Path(env("STATIC_BUILD_DIR", default=str(BASE_DIR / "static_build")))
if _build_dir.exists():
    STATICFILES_DIRS.append(_build_dir)
# Patient reports and import uploads live OUTSIDE the web root and are only
# served through authenticated, centre-scoped views.
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media")))
MEDIA_ROOT = PRIVATE_MEDIA_ROOT
MEDIA_URL = "/protected/"  # never served directly by Nginx
USE_X_ACCEL_REDIRECT = env("USE_X_ACCEL_REDIRECT")
USE_CDN_ASSETS = env("USE_CDN_ASSETS")
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --- Security ------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
if not DEBUG:
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False

# --- Celery ------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BEAT_SCHEDULE = {
    "generate-retest-candidates": {
        "task": "apps.retest.tasks.generate_retest_candidates_task",
        "schedule": crontab(hour=6, minute=0),
    },
    "daily-reminders": {
        "task": "apps.followups.tasks.send_daily_reminders",
        "schedule": crontab(hour=8, minute=30),
    },
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
if env("REDIS_URL", default=None):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@localhost")

# --- Business rules (defaults; Admins can override most in Site Settings) ---
MAX_ACTIVE_ADMINS = 3
DEFAULT_MAX_ACTIVE_EMPLOYEES = env.int("MAX_ACTIVE_EMPLOYEES", default=10)
# Usernames of the site developer(s): full Admin + superuser rights, but not counted
# against the 3-Admin cap, so the lab keeps all of its own Admin slots.
DEVELOPER_ACCOUNTS = env.list("DEVELOPER_ACCOUNTS", default=[])
DEFAULT_RETEST_LOOKAHEAD_DAYS = 7
PRICE_STALE_DAYS = 90

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
