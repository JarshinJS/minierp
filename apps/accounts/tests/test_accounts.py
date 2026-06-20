import pytest
from django.contrib.auth import get_user_model
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
        user = User.objects.create(email="sales@example.com", role=UserRole.SALES_USER)
        
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
        user = User.objects.create(email="sales@example.com", role=UserRole.SALES_USER)
        
        request = factory.get("/dummy/")
        request.user = user

        class DummyView(RoleRequiredMixin):
            allowed_roles = [UserRole.ADMIN]

        view = DummyView()
        with pytest.raises(PermissionDenied):
            view.dispatch(request)

    def test_drf_role_permission_allows_correct_role(self):
        factory = APIRequestFactory()
        user = User.objects.create(email="sales@example.com", role=UserRole.SALES_USER)
        
        request = factory.get("/dummy/")
        request.user = user

        class DummyDRFView:
            allowed_roles = [UserRole.SALES_USER]

        permission = DRFRolePermission()
        assert permission.has_permission(request, DummyDRFView()) is True

    def test_drf_role_permission_denies_wrong_role(self):
        factory = APIRequestFactory()
        user = User.objects.create(email="sales@example.com", role=UserRole.SALES_USER)
        
        request = factory.get("/dummy/")
        request.user = user

        class DummyDRFView:
            allowed_roles = [UserRole.ADMIN]

        permission = DRFRolePermission()
        assert permission.has_permission(request, DummyDRFView()) is False


@pytest.mark.django_db
class TestAuthenticationFlows:
    def test_signup_view_creates_user(self, client):
        url = reverse("accounts:signup")
        data = {
            "email": "signup@example.com",
            "full_name": "New Signup",
            "role": UserRole.SALES_USER,
            "password": "strongpassword123",
            "confirm_password": "strongpassword123"
        }
        response = client.post(url, data)
        # Should redirect to login on success
        assert response.status_code == 302
        assert User.objects.filter(email="signup@example.com").exists() is True

    def test_login_logout_flows(self, client):
        # Create a user to log in
        services.create_user(
            email="login@example.com",
            password="mypassword",
            full_name="Login User",
            role=UserRole.ADMIN  # Admin will redirect to user_list
        )

        login_url = reverse("accounts:login")
        
        # Test GET
        response = client.get(login_url)
        assert response.status_code == 200

        # Test POST Login
        response = client.post(login_url, {"email": "login@example.com", "password": "mypassword"})
        assert response.status_code == 302
        assert response.url == reverse("accounts:user_list")

        # Test Logout
        logout_url = reverse("accounts:logout")
        response = client.post(logout_url)
        assert response.status_code == 302
        assert response.url == reverse("accounts:login")
