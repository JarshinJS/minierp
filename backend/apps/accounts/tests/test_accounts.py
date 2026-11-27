import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.test import APIRequestFactory
from core.exceptions import DomainError, WorkflowError
from apps.accounts.models import UserRole
from apps.accounts import services
from apps.accounts.permissions import RoleRequiredMixin, DRFRolePermission

User = get_user_model()

@pytest.mark.django_db
class TestUserServices:
    def test_create_user_success(self):
        user = services.create_user(
            email="test@example.com",
            password="securepassword123",
            full_name="Test User",
            role=UserRole.SALES_USER
        )
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.role == UserRole.SALES_USER
        assert user.is_active is True
        assert user.check_password("securepassword123") is True

    def test_create_user_duplicate_email(self):
        services.create_user(
            email="dup@example.com",
            password="password",
            full_name="Original"
        )
        with pytest.raises(DomainError) as exc:
            services.create_user(
                email="dup@example.com",
                password="password",
                full_name="Duplicate"
            )
        assert "already exists" in str(exc.value)

    def test_create_user_invalid_role(self):
        with pytest.raises(DomainError) as exc:
            services.create_user(
                email="invalid@example.com",
                password="password",
                full_name="Invalid",
                role="SUPERADMIN"
            )
        assert "Invalid user role" in str(exc.value)

    def test_activate_deactivate_user(self):
        # Create an admin user first to ensure we don't hit the "last active admin" error
        admin = services.create_user(
            email="admin@example.com",
            password="password",
            full_name="Admin",
            role=UserRole.ADMIN
        )
        
        user = services.create_user(
            email="test@example.com",
            password="password",
            full_name="Test"
        )
        assert user.is_active is True

        # Deactivate
        services.deactivate_user(user)
        assert user.is_active is False

        # Attempting duplicate deactivation
        with pytest.raises(WorkflowError):
            services.deactivate_user(user)

        # Activate
        services.activate_user(user)
        assert user.is_active is True

        # Attempting duplicate activation
        with pytest.raises(WorkflowError):
            services.activate_user(user)

    def test_deactivate_last_active_admin(self):
        admin = services.create_user(
            email="admin@example.com",
            password="password",
            full_name="Admin",
            role=UserRole.ADMIN
        )
        with pytest.raises(WorkflowError) as exc:
            services.deactivate_user(admin)
        assert "Cannot deactivate the last active Admin" in str(exc.value)

    def test_change_role_success(self):
        # Admin for safety bypasses
        services.create_user(
            email="admin@example.com",
            password="password",
            full_name="Admin",
            role=UserRole.ADMIN
        )
        user = services.create_user(
            email="user@example.com",
            password="password",
            full_name="User",
            role=UserRole.SALES_USER
        )
        services.change_role(user, UserRole.INVENTORY_MANAGER)
        assert user.role == UserRole.INVENTORY_MANAGER

    def test_change_role_last_admin(self):
        admin = services.create_user(
            email="admin@example.com",
            password="password",
            full_name="Admin",
            role=UserRole.ADMIN
        )
        with pytest.raises(WorkflowError) as exc:
            services.change_role(admin, UserRole.SALES_USER)
        assert "Cannot change the role of the last active Admin" in str(exc.value)


@pytest.mark.django_db
class TestRolePermissions:
    def test_role_required_mixin_allows_correct_role(self):
        factory = RequestFactory()
        user = User.objects.create(email="sales@example.com", role=UserRole.SALES_USER, account_status="APPROVED")  # approved account: only the role is under test
        
        request = factory.get("/dummy/")
        request.user = user

        # Dummy View subclass
        class DummyView(RoleRequiredMixin):
            allowed_roles = [UserRole.SALES_USER]
            def dispatch(self, request, *args, **kwargs):
                return "Allowed"

        view = DummyView()
        response = view.dispatch(request)
        assert response == "Allowed"

    def test_role_required_mixin_denies_wrong_role(self):
        factory = RequestFactory()
        user = User.objects.create(email="sales@example.com", role=UserRole.SALES_USER, account_status="APPROVED")  # approved account: only the role is under test
        
        request = factory.get("/dummy/")
        request.user = user

        class DummyView(RoleRequiredMixin):
            allowed_roles = [UserRole.ADMIN]

        view = DummyView()
        with pytest.raises(PermissionDenied):
            view.dispatch(request)

    def test_drf_role_permission_allows_correct_role(self):
        factory = APIRequestFactory()
        user = User.objects.create(email="sales@example.com", role=UserRole.SALES_USER, account_status="APPROVED")  # approved account: only the role is under test
        
        request = factory.get("/dummy/")
        request.user = user

        class DummyDRFView:
            allowed_roles = [UserRole.SALES_USER]

        permission = DRFRolePermission()
        assert permission.has_permission(request, DummyDRFView()) is True

    def test_drf_role_permission_denies_wrong_role(self):
        factory = APIRequestFactory()
        user = User.objects.create(email="sales@example.com", role=UserRole.SALES_USER, account_status="APPROVED")  # approved account: only the role is under test
        
        request = factory.get("/dummy/")
        request.user = user

        class DummyDRFView:
            allowed_roles = [UserRole.ADMIN]

        permission = DRFRolePermission()
        assert permission.has_permission(request, DummyDRFView()) is False


@pytest.mark.django_db
class TestAuthenticationFlows:
    """Signup/OTP/login now run through the API used by the Next.js frontend."""

    def _pending(self, client, **overrides):
        session = client.session
        session["signup_data"] = {
            "email": "verify@example.com",
            "password_hash": make_password("strongpassword123"),
            "full_name": "Verify Me",
            "otp": "123456",
            "otp_expiry": 9999999999,  # far in future
            **overrides,
        }
        session.save()

    def test_signup_starts_otp_flow(self, client):
        response = client.post(reverse("api:auth-signup"), {
            "email": "signup@example.com",
            "full_name": "New Signup",
            "password": "strongpassword123",
            "confirm_password": "strongpassword123",
        }, content_type="application/json")
        assert response.status_code == 202
        # User is NOT created until the OTP is verified
        assert User.objects.filter(email="signup@example.com").exists() is False
        session = client.session
        assert session["signup_data"]["email"] == "signup@example.com"
        assert "otp" in session["signup_data"]

    def test_verify_otp_success_creates_user(self, client):
        self._pending(client)
        response = client.post(reverse("api:auth-signup-verify"), {"otp": "123456"}, content_type="application/json")
        assert response.status_code == 201
        assert User.objects.filter(email="verify@example.com").exists() is True
        assert "signup_data" not in client.session

    def test_verify_otp_invalid_error(self, client):
        self._pending(client)
        response = client.post(reverse("api:auth-signup-verify"), {"otp": "654321"}, content_type="application/json")
        assert response.status_code == 400
        assert response.json()["otp"] == ["Invalid OTP. Please try again."]
        assert User.objects.filter(email="verify@example.com").exists() is False

    def test_verify_otp_expired_error(self, client):
        self._pending(client, otp_expiry=0)
        response = client.post(reverse("api:auth-signup-verify"), {"otp": "123456"}, content_type="application/json")
        assert response.status_code == 400
        assert "expired" in response.json()["otp"][0]
        assert User.objects.filter(email="verify@example.com").exists() is False

    def test_resend_otp_generates_new_otp(self, client):
        self._pending(client, otp="111111", otp_expiry=100)
        response = client.post(reverse("api:auth-signup-resend"))
        assert response.status_code == 200
        data = client.session["signup_data"]
        assert data["otp"] != "111111"
        assert data["otp_expiry"] > 100

    def test_login_logout_flows(self, client):
        services.create_user(email="login@example.com", password="mypassword", full_name="Login User", role=UserRole.ADMIN)
        response = client.post(reverse("api:auth-login"), {"email": "login@example.com", "password": "mypassword"},
                               content_type="application/json")
        assert response.status_code == 200
        assert client.get(reverse("api:auth-me")).status_code == 200

        # Django-side logout (used by the remaining Django pages) is POST-only.
        assert client.get(reverse("accounts:logout")).status_code == 405
        response = client.post(reverse("accounts:logout"))
        assert response.status_code == 302
        assert response.url == "/login/"
        assert client.get(reverse("api:auth-me")).status_code == 403
