import os

from .base import *

DEBUG = os.getenv("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",") if host.strip()]

# The Next.js dev server (frontend/) proxies to Django, so the browser's Origin
# is :3000. Trust it for CSRF checks.
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]

# Database: Postgres (e.g. a Supabase dev project) when DATABASE_URL is set in
# backend/.env, otherwise the local SQLite file. Tests never use this; they run on
# config.settings.test (see pytest.ini).
if os.getenv("DATABASE_URL"):
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            os.environ["DATABASE_URL"],
            conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
            conn_health_checks=True,
            # Hosted Postgres (Supabase) requires TLS; set DB_SSL_REQUIRE=False for a
            # plain local Postgres.
            ssl_require=os.getenv("DB_SSL_REQUIRE", "True").lower() == "true",
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Print emails (including signup OTPs) to the runserver console in development.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

# Dev specific settings
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
