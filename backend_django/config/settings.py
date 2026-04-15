"""
Django settings for AgentCrafter.

Replaces the FastAPI app configuration. Uses django-environ to load
environment variables from the project .env file (same file the FastAPI
backend used) so no environment changes are needed.
"""
import environ
from pathlib import Path

# ── Base paths ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Environment loading ───────────────────────────────────────────────────────
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["*"]),
    CORS_ALLOW_ALL_ORIGINS=(bool, True),
)
# Load .env from the project root (same .env used by the FastAPI backend)
environ.Env.read_env(BASE_DIR.parent / ".env")

# ── Core settings ─────────────────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-secret-key-change-in-production")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ── Installed apps ────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",   # required for JSONField GIN indexes
    # Third-party
    "rest_framework",
    "corsheaders",
    # Project apps
    "agents",
    "runs",
    "sessions.apps.SessionsConfig",  # custom label "agent_sessions" avoids clash with django.contrib.sessions
]

# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    # CorsMiddleware must be as high as possible, before any middleware that
    # generates responses (e.g. WhiteNoise or CommonMiddleware).
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Database ──────────────────────────────────────────────────────────────────
# Django ORM connects to the same PostgreSQL instance used by the FastAPI
# backend. It is used only for migrations and Django Admin. All service-layer
# data access still goes through SQLAlchemy (see db/session.py).
_db_url = env(
    "DATABASE_URL",
    default="postgresql://langgraph:langgraph_secret@localhost:5733/langgraph_builder",
)
DATABASES = {
    "default": env.db_url("DATABASE_URL", default=_db_url),
}

# ── Password validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── CORS ──────────────────────────────────────────────────────────────────────
# Mirrors the FastAPI CORSMiddleware(allow_origins=["*"]) setting so the
# React frontend can continue to talk to this server without changes.
CORS_ALLOW_ALL_ORIGINS = env("CORS_ALLOW_ALL_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# ── Django REST Framework ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    # Custom handler maps service-layer exceptions to correct HTTP status codes.
    # Replaces the @translate_service_errors decorator used in FastAPI routes.
    "EXCEPTION_HANDLER": "config.exceptions.custom_exception_handler",
}

# ── CSRF exemption for API views ──────────────────────────────────────────────
# The API is consumed by a React SPA (not a browser form), so CSRF is not
# needed. Individual APIView classes are already exempt via DRF's default
# behaviour (SessionAuthentication is not configured).
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
