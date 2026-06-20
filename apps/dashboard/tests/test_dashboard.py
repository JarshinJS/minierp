import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestDashboardViews:
    def test_dashboard_home_loads_for_authenticated_user(self, client):
        user = User.objects.create_user(
            email="admin@example.com",
            password="password",
            full_name="Admin User",
            role="ADMIN"
        )
        client.login(email="admin@example.com", password="password")

        url = reverse("dashboard:home")
        response = client.get(url)

        assert response.status_code == 200
        assert b"Dashboard" in response.content
        assert b"Loading dashboard" in response.content

    def test_dashboard_summary_partial_renders(self, client):
        user = User.objects.create_user(
            email="user@example.com",
            password="password",
            full_name="Normal User",
            role="BUSINESS_OWNER"
        )
        client.login(email="user@example.com", password="password")

        url = reverse("dashboard:summary_partial")
        response = client.get(url)

        assert response.status_code == 200
        assert b"Sales Orders" in response.content
        assert b"Low Stock Products" in response.content

    def test_dashboard_summary_api_returns_json(self, client):
        user = User.objects.create_user(
            email="apiuser@example.com",
            password="password",
            full_name="API User",
            role="BUSINESS_OWNER"
        )
        client.login(email="apiuser@example.com", password="password")

        response = client.get(reverse("dashboard_api_summary"))

        assert response.status_code == 200
        data = response.json()
        assert "sales" in data
        assert "purchase" in data
        assert "manufacturing" in data
        assert "inventory" in data
        assert "procurement" in data
        assert "recent_activities" in data
        assert "low_stock_products" in data
