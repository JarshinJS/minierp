import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, REST_FRAMEWORK, STORAGE_BUCKET, STORAGES, _csv

DEBUG = False

# --- Hosts -------------------------------------------------------------------
ALLOWED_HOSTS = _csv(os.getenv("ALLOWED_HOSTS", ""))
CSRF_TRUSTED_ORIGINS = _csv(os.getenv("CSRF_TRUSTED_ORIGINS", ""))

# Render injects the service's public hostname; trust it automatically.
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set in production.")

# --- HTTPS / security ----------------------------------------------------------
# Render terminates TLS at its proxy and forwards plain HTTP; without this header
# Django thinks every request is insecure and SECURE_SSL_REDIRECT loops forever.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True").lower() == "true"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "False").lower() == "true"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# --- Database ------------------------------------------------------------------
# DATABASE_URL is provided by Render Postgres (see render.yaml).
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set in production.")
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
        # Always TLS for Supabase, whatever DB_SSL_REQUIRE says.
        ssl_require=(
            os.getenv("DB_SSL_REQUIRE", "False").lower() == "true"
            or ".supabase." in DATABASE_URL
        ),
    )
}

# --- Static files (served by WhiteNoise) --------------------------------------
# WhiteNoise goes right after SecurityMiddleware.
_security = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
MIDDLEWARE = [
    *MIDDLEWARE[: _security + 1],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[_security + 1 :],
]
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
# Production must use private object storage: Render's disk is wiped on deploy and
# the Celery worker (a separate machine) can't read the web service's disk.
if not STORAGE_BUCKET:
    raise ImproperlyConfigured(
        "STORAGE_BUCKET (private Supabase Storage / S3 bucket) must be set in production. "
        "See docs/deployment.md, 'Document storage'."
    )
for _var in ("STORAGE_ACCESS_KEY_ID", "STORAGE_SECRET_ACCESS_KEY"):
    if not os.getenv(_var):
        raise ImproperlyConfigured(f"{_var} must be set when STORAGE_BUCKET is used.")

# --- REST Framework --------------------------------------------------------------
# No BasicAuthentication in production, to avoid sending credentials on every request.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "NUM_PROXIES": int(os.getenv("NUM_PROXIES", "1")),
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}

# --- Cache (shared by all gunicorn workers; used for API rate limiting) -------
if REDIS_CACHE_URL := os.getenv("CACHE_URL") or os.getenv("CELERY_BROKER_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_CACHE_URL}}

# --- Logging (stdout, picked up by Render's log stream) ------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
