"""
Settings for the test suite (pytest.ini). Same as dev, but ALWAYS SQLite: tests
create, flush and drop tables, so they must never run against DATABASE_URL
(e.g. the Supabase dev database) even if it is set in backend/.env.
backend/conftest.py turns this into a temporary file-backed test database.
"""
from .dev import *  # noqa: F401,F403
from .dev import BASE_DIR

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # never opened: the test DB is a temp file
    }
}

# Tests never touch real object storage, even if STORAGE_BUCKET is set in .env:
# files go to a per-test temp directory (see the media fixtures). The S3 code path
# is exercised separately against a local S3-compatible server (opt-in test).
STORAGE_BUCKET = ""
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Fast password hashing for tests only (thousands of test users). Production and
# development keep Django's default PBKDF2/Argon2 hashers.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Optional PostgreSQL run (CI uses a throwaway Postgres service container). Opt in
# with TEST_DATABASE_URL, deliberately NOT DATABASE_URL, so backend/.env can never
# redirect the test suite. Only local/CI hosts are accepted; pytest-django creates
# a separate "test_<name>" database there and drops it after the run.
import os as _os

if _os.getenv("TEST_DATABASE_URL"):
    import dj_database_url as _dj_database_url
    from django.core.exceptions import ImproperlyConfigured as _ImproperlyConfigured

    DATABASES = {"default": _dj_database_url.parse(_os.environ["TEST_DATABASE_URL"])}
    if DATABASES["default"].get("HOST") not in {"localhost", "127.0.0.1", "postgres"}:
        raise _ImproperlyConfigured(
            "TEST_DATABASE_URL must point at a local or CI Postgres (localhost, 127.0.0.1 or the "
            "'postgres' service), never a shared or hosted database."
        )
