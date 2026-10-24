"""Django settings. Production secrets and hosts are supplied through environment."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
if not DEBUG and not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be configured when DEBUG is false.")
default_hosts = "localhost,127.0.0.1" if DEBUG else ""
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", default_hosts).split(",") if host.strip()]
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be configured when DEBUG is false.")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "foodwagon_site.apps.FoodwagonSiteConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "foodwagon_project.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "foodwagon_project.wsgi.application"
ASGI_APPLICATION = "foodwagon_project.asgi.application"
database_url = os.environ.get("DATABASE_URL", "")
if database_url.startswith(("postgres://", "postgresql://")):
    from urllib.parse import urlparse
    db = urlparse(database_url)
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": db.path.lstrip("/"), "USER": db.username or "", "PASSWORD": db.password or "", "HOST": db.hostname or "", "PORT": db.port or 5432, "CONN_MAX_AGE": 60, "CONN_HEALTH_CHECKS": True, "OPTIONS": {"sslmode": os.environ.get("DB_SSLMODE", "require")}}}
elif DEBUG:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    raise RuntimeError("A PostgreSQL DATABASE_URL must be configured when DEBUG is false.")
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE = "en-ng"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/assets/"
STATICFILES_DIRS = [BASE_DIR / "public" / "assets"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/admin/login/"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_SSL_REDIRECT = not DEBUG and os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    not DEBUG and os.environ.get("DJANGO_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
)
SECURE_HSTS_PRELOAD = not DEBUG and os.environ.get("DJANGO_HSTS_PRELOAD", "false").lower() == "true"
if SECURE_HSTS_PRELOAD and not SECURE_HSTS_INCLUDE_SUBDOMAINS:
    raise RuntimeError("DJANGO_HSTS_PRELOAD=true also requires DJANGO_HSTS_INCLUDE_SUBDOMAINS=true.")
# Forwarded HTTPS is trusted only when deployed behind a configured TLS-terminating proxy.
if os.environ.get("DJANGO_TRUST_X_FORWARDED_PROTO") == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Live checkout requires all environment, key-prefix, and owner-verified profile gates.
LIVE_ORDERING_ENABLED = os.environ.get("LIVE_ORDERING_ENABLED", "false").lower() == "true"
LIVE_PAYMENTS_ENABLED = os.environ.get("LIVE_PAYMENTS_ENABLED", "false").lower() == "true"
FOODWAGON_LIVE_CHECKOUT_APPROVED = os.environ.get("FOODWAGON_LIVE_CHECKOUT_APPROVED", "false").lower() == "true"
PAYMENT_MODE = os.environ.get("FOODWAGON_PAYMENT_MODE", "demo" if DEBUG else "disabled").lower()
if PAYMENT_MODE not in {"demo", "test", "live", "disabled"}:
    raise RuntimeError("FOODWAGON_PAYMENT_MODE must be demo, test, live, or disabled.")
PAYSTACK_TEST_SECRET_KEY = os.environ.get("PAYSTACK_TEST_SECRET_KEY", "")
PAYSTACK_LIVE_SECRET_KEY = os.environ.get("PAYSTACK_LIVE_SECRET_KEY", "")
PAYSTACK_API_TIMEOUT_SECONDS = max(1, min(int(os.environ.get("PAYSTACK_API_TIMEOUT_SECONDS", "10")), 30))
