"""
Settings for the Playwright end-to-end suite (frontend/e2e).

The suite drives a real browser against a real Django + Next.js pair, so it needs
a real server with real data, but completely isolated from anything you care about:

* its own SQLite file under backend/.e2e/ (DATABASE_URL in .env is ignored, so a
  Supabase/Postgres dev database can never be touched);
* e-mails written to files, so tests can read the signup code (OTP);
* uploads to a local directory, never to object storage;
* blockchain in persistent mock mode, Celery tasks inline;
* `E2E = True`, which is what allows `seed_demo --reset` to wipe the database.
"""
import os
from pathlib import Path

from .dev import *  # noqa: F401,F403
from .dev import BASE_DIR, REST_FRAMEWORK

E2E = True
E2E_DIR = Path(os.getenv("E2E_STATE_DIR", BASE_DIR / ".e2e"))
E2E_DIR.mkdir(parents=True, exist_ok=True)

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:3100", "http://127.0.0.1:3100"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": E2E_DIR / "e2e.sqlite3",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = E2E_DIR / "mail"

STORAGE_BUCKET = ""
MEDIA_ROOT = E2E_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

BLOCKCHAIN_MOCK_MODE = True
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# The suite signs in dozens of times from one IP; the production limits are
# covered by backend tests (core/tests), not here.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "auth": "10000/min",
        "auth_account": "10000/min",
    },
}

# Fast hashing: the seed creates a user per role on every run.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
