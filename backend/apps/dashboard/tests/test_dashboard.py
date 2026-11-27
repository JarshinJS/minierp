import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestDashboardViews:
    def test_dashboard_page_is_handed_to_frontend(self, client, settings):
        """The page lives in Next.js; Django keeps the URL name and redirects there."""
        User.objects.create_user(email="admin@example.com", password="password", full_name="Admin User", role="ADMIN")
        client.login(email="admin@example.com", password="password")

        settings.FRONTEND_URL = ""
        assert client.get(reverse("dashboard:home")).status_code == 404

        settings.FRONTEND_URL = "https://app.example.com"
        response = client.get(reverse("dashboard:home") + "?x=1")
        assert response.status_code == 302
        assert response.url == "https://app.example.com/dashboard/?x=1"

    def test_dashboard_overview_api(self, client):
        User.objects.create_user(email="user@example.com", password="password", full_name="Normal User", role="BUSINESS_OWNER")
        client.login(email="user@example.com", password="password")
        data = client.get(reverse("api:dashboard-overview")).json()
        assert data["widgets"] and "recent_activities" in data and "low_stock" in data

    def test_dashboard_summary_api_returns_json(self, client):
        user = User.objects.create_user(
            email="apiuser@example.com",
            password="password",
            full_name="API User",
            role="BUSINESS_OWNER"
        )
        client.login(email="apiuser@example.com", password="password")

        response = client.get(reverse("api:dashboard-summary"))

        assert response.status_code == 200
        data = response.json()
        assert "sales" in data
        assert "purchase" in data
        assert "manufacturing" in data
        assert "inventory" in data
        assert "procurement" in data
        assert "recent_activities" in data
        assert "low_stock_products" in data
