"""
Regression tests for the security fixes: role enforcement on HTML views and
APIs, no hard-deletes through the API, removed dangerous endpoints, signup
role escalation, OTP hardening and BOM form script escaping.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.manufacturing import services as manufacturing_services
from apps.products.models import Category, Product

User = get_user_model()


def make_user(role, email=None):
    return User.objects.create_user(
        email=email or f"{role.lower()}@example.com",
        password="Str0ng-pass-123",
        full_name=role.title(),
        role=role,
    )


def api_client(user):
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def product(db):
    category = Category.objects.create(name="General")
    return Product.objects.create(
        name="Oak Chair", sku="OAK-1", category=category,
        cost_price=Decimal("10.00"), selling_price=Decimal("20.00"), is_active=True,
    )


# --- Role enforcement -------------------------------------------------------

@pytest.mark.django_db
class TestModuleAccess:
    @pytest.mark.parametrize("url", [
        "/api/products/",
        "/api/purchase-orders/",
        "/api/boms/",
        "/api/audit-logs/",
    ])
    def test_accountant_blocked_from_operational_apis(self, url):
        user = make_user(UserRole.ACCOUNTANT)
        assert api_client(user).get(url).status_code == 403

    def test_sales_user_can_use_sales_and_products_api(self):
        user = make_user(UserRole.SALES_USER)
        client = api_client(user)
        assert client.get("/api/sales-orders/").status_code == 200
        assert client.get("/api/products/").status_code == 200

    def test_sales_user_blocked_from_purchase_api_and_pages(self):
        user = make_user(UserRole.SALES_USER)
        client = api_client(user)
        assert client.get("/api/purchase-orders/").status_code == 403
        assert client.get(reverse("purchase:purchase_order_list")).status_code == 403

    def test_auditor_blocked_from_creating_products(self, product):
        user = make_user(UserRole.AUDITOR)
        response = api_client(user).post("/api/categories/", {"name": "Hacked"})
        assert response.status_code == 403

    def test_api_delete_is_not_allowed(self, product):
        admin = make_user(UserRole.ADMIN)
        response = api_client(admin).delete(f"/api/products/{product.pk}/")
        assert response.status_code == 405
        assert Product.objects.filter(pk=product.pk).exists()

    def test_voice_assistant_checks_module_access(self, product):
        user = make_user(UserRole.ACCOUNTANT)
        response = api_client(user).post(
            "/api/voice/assistant/",
            {"transcript": "increase stock of Oak Chair by 5"},
            format="json",
        )
        assert response.status_code == 403
        product.refresh_from_db()
        assert product.on_hand_qty == 0


@pytest.mark.django_db
def test_demo_and_sse_endpoints_removed():
    admin = make_user(UserRole.ADMIN)
    client = api_client(admin)
    assert client.post("/dashboard/run-demo/").status_code == 404
    assert client.get("/dashboard/sse-summary/").status_code == 404


# --- Signup / OTP -----------------------------------------------------------

SIGNUP_DATA = {
    "email": "newbie@example.com",
    "full_name": "New Bie",
    "role": UserRole.ADMIN,  # attacker-supplied; must be ignored
    "password": "Str0ng-pass-123",
    "confirm_password": "Str0ng-pass-123",
}


@pytest.mark.django_db
class TestSignupHardening:
    """Exercised through the signup API used by the Next.js frontend."""

    def _post(self, client, name, body=None):
        return client.post(reverse(name), body or {}, content_type="application/json")

    def _signup(self, client):
        assert self._post(client, "api:auth-signup", SIGNUP_DATA).status_code == 202
        return client.session["signup_data"]

    def test_otp_is_emailed_and_password_not_stored_in_plaintext(self, client):
        data = self._signup(client)
        assert len(mail.outbox) == 1
        assert data["otp"] in mail.outbox[0].body
        assert "password" not in data
        assert SIGNUP_DATA["password"] not in str(data)

    def test_signup_cannot_choose_admin_role(self, client):
        data = self._signup(client)
        assert self._post(client, "api:auth-signup-verify", {"otp": data["otp"]}).status_code == 201
        user = User.objects.get(email=SIGNUP_DATA["email"])
        assert user.role == UserRole.SALES_USER
        assert not user.is_staff and not user.is_superuser
        assert user.check_password(SIGNUP_DATA["password"])

    def test_otp_locks_out_after_max_attempts(self, client):
        data = self._signup(client)
        wrong = "000000" if data["otp"] != "000000" else "111111"
        for _ in range(5):
            assert self._post(client, "api:auth-signup-verify", {"otp": wrong}).status_code == 400
        response = self._post(client, "api:auth-signup-verify", {"otp": data["otp"]})
        assert response.status_code == 400 and response.json()["restart"] is True
        assert not User.objects.filter(email=SIGNUP_DATA["email"]).exists()

    def test_resend_has_cooldown(self, client):
        data = self._signup(client)
        assert self._post(client, "api:auth-signup-resend").status_code == 400
        assert client.session["signup_data"]["otp"] == data["otp"]
        assert len(mail.outbox) == 1

    def test_weak_password_rejected(self, client):
        response = self._post(client, "api:auth-signup", {**SIGNUP_DATA, "password": "12345678", "confirm_password": "12345678"})
        assert response.status_code == 400
        assert "password" in response.json()


# --- XSS --------------------------------------------------------------------

@pytest.mark.django_db
def test_bom_form_escapes_script_in_component_names():
    category = Category.objects.create(name="Raw")
    evil = Product.objects.create(
        name="</script><script>alert(1)</script>", sku="EVIL-1", category=category,
        cost_price=Decimal("1.00"), selling_price=Decimal("1.00"), is_active=True,
    )
    bom = manufacturing_services.create_bom(
        name="Evil BOM", reference="BOM-EVIL",
        components=[{"component_id": str(evil.pk), "quantity": "1", "uom": "PCS", "sequence": 1}],
    )
    user = make_user(UserRole.MANUFACTURING_USER)
    client = api_client(user)
    html = client.get(reverse("manufacturing:bom_edit", args=[bom.pk])).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "\\u003C/script\\u003E" in html


# --- Health check -----------------------------------------------------------

@pytest.mark.django_db
def test_healthz_ok_even_with_unknown_host(client):
    response = client.get("/healthz/", HTTP_HOST="10.0.0.7:10000")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_unknown_host_still_rejected_elsewhere(client):
    assert client.get("/accounts/login/", HTTP_HOST="evil.example.com").status_code == 400
