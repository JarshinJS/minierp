import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate tests from each other's cached state (e.g. API rate-limit counters)."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_parallel_suffix, tmp_path_factory):
    """
    Use a file-backed SQLite test database instead of the shared-cache in-memory one.

    In-memory shared-cache SQLite fails immediately ("database table is locked")
    instead of waiting on another connection's lock, so tests that use several
    connections at once (e.g. the blockchain nonce concurrency tests) can't run on it.
    A file in pytest's temp dir behaves like a real database and is removed afterwards.
    """
    from django.conf import settings

    db = settings.DATABASES["default"]
    # Hard stop: tests create, flush and drop databases. They must never run against
    # a hosted (Supabase) database, whatever settings module or .env is in use.
    host = str(db.get("HOST") or "").lower()
    if "supabase." in host or "pooler.supabase" in host:
        pytest.exit(f"Refusing to run tests against hosted database host {host!r}. "
                    "Use config.settings.test (pytest.ini) or a local Postgres.", returncode=2)
    if db["ENGINE"] == "django.db.backends.sqlite3":
        db.setdefault("TEST", {})["NAME"] = str(tmp_path_factory.mktemp("db") / "test.sqlite3")
