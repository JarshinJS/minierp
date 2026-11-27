"""
Open-redirect regression tests for the backend (Phase 0.6).

The backend never redirects to a user-supplied URL: post-login navigation (`?next=`)
is validated by the frontend (frontend/src/lib/safe-redirect.ts, tested with
`npm test`). These tests pin down that every backend redirect stays internal.
"""
from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory

from core.views import FrontendPageView

User = get_user_model()

MALICIOUS = [
    "https://evil.com",
    "//evil.com",
    "///evil.com",
    "/\\evil.com",
    "\\\\evil.com",
    "https:evil.com",
    "javascript:alert(1)",
    "/%2F%2Fevil.com",
    "%2F%2Fevil.com",
    "http://testserver@evil.com/",
]


def _is_internal(location, allowed_netlocs=("", "testserver")):
    parsed = urlparse(location.replace("\\", "/"))
    return parsed.scheme in ("", "http", "https") and parsed.netloc in allowed_netlocs \
        and not location.replace("\\", "/").startswith("//")


@pytest.fixture
def staff(db):
    return User.objects.create_superuser(email="root@redirect.test", password="Root-pass-123", full_name="Root")


@pytest.mark.django_db
@pytest.mark.parametrize("target", MALICIOUS)
def test_admin_login_ignores_external_next(staff, target):
    client = Client()
    response = client.post("/admin/login/", {
        "username": staff.email, "password": "Root-pass-123", "next": target,
    })
    assert response.status_code == 302
    assert _is_internal(response["Location"]), response["Location"]


@pytest.mark.django_db
@pytest.mark.parametrize("target", MALICIOUS)
def test_logout_ignores_next(staff, target):
    client = Client()
    client.force_login(staff)
    response = client.post(f"/accounts/logout/?next={target}", {"next": target})
    assert response.status_code == 302
    assert response["Location"] == "/login/"


@pytest.mark.django_db
def test_login_required_redirects_are_relative():
    response = Client().get("/accounts/users/")
    assert response.status_code == 302
    location = response["Location"]
    assert location.startswith("/login/?next=/")
    assert _is_internal(location)


@pytest.mark.parametrize("path", ["//evil.com", "//evil.com/x", "/@evil.com", "/\\evil.com", "/dashboard/?next=https://evil.com"])
def test_frontend_page_redirect_stays_on_frontend_host(settings, path):
    settings.FRONTEND_URL = "https://app.example.com"
    request = RequestFactory().get(path)
    response = FrontendPageView.as_view()(request)
    assert response.status_code == 302
    location = response["Location"]
    assert location.startswith("https://app.example.com/")
    assert urlparse(location).netloc == "app.example.com"


def test_frontend_page_without_frontend_url_is_404(settings):
    settings.FRONTEND_URL = ""
    response = FrontendPageView.as_view()(RequestFactory().get("//evil.com"))
    assert response.status_code == 404
