import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate tests from each other's cached state (e.g. API rate-limit counters)."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
