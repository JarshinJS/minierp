import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.accounts.models import UserRole
from apps.dashboard.services.widget_service import get_allowed_widgets_for_user
from apps.dashboard.services.alert_service import get_all_alerts
from apps.dashboard.services.dashboard_service import get_dashboard_data_for_user

User = get_user_model()


@pytest.mark.django_db
class TestDashboardUpgrade:
    def test_widget_role_authorization_admin(self):
        admin = User.objects.create_user(
            email="admin@example.com",
            password="password",
            full_name="Admin",
            role=UserRole.ADMIN
        )
        widgets = get_allowed_widgets_for_user(admin)
        assert len(widgets) == 9
        class_names = [w["class_name"] for w in widgets]
        assert "ProductWidget" in class_names
        assert "AuditWidget" in class_names

    def test_widget_role_authorization_sales(self):
        sales = User.objects.create_user(
            email="sales@example.com",
            password="password",
            full_name="Sales User",
            role=UserRole.SALES_USER
        )
        widgets = get_allowed_widgets_for_user(sales)
        # Sales sees ProductWidget, SalesWidget, DeliveryWidget
        assert len(widgets) == 3
        class_names = [w["class_name"] for w in widgets]
        assert "SalesWidget" in class_names
        assert "ProductWidget" in class_names
        assert "DeliveryWidget" in class_names
        assert "AuditWidget" not in class_names

    def test_widget_role_authorization_accountant(self):
        accountant = User.objects.create_user(
            email="acc@example.com",
            password="password",
            full_name="Accountant",
            role=UserRole.ACCOUNTANT
        )
        widgets = get_allowed_widgets_for_user(accountant)
        # Accountant sees ReportsWidget only
        assert len(widgets) == 1
        assert widgets[0]["class_name"] == "ReportsWidget"

    def test_get_all_alerts_structure(self):
        alerts = get_all_alerts()
        assert "low_stock" in alerts
        assert "pending_deliveries" in alerts
        assert "delayed_manufacturing" in alerts
        assert "pending_procurement" in alerts

    def test_get_dashboard_data_for_user(self):
        admin = User.objects.create_user(
            email="admin2@example.com",
            password="password",
            full_name="Admin 2",
            role=UserRole.ADMIN
        )
        data = get_dashboard_data_for_user(admin)
        assert "widgets" in data
        assert "alerts" in data
        assert "recent_activities" in data
        assert len(data["widgets"]) == 9

    def test_dashboard_refresh_view(self, client):
        user = User.objects.create_user(
            email="refresh@example.com",
            password="password",
            full_name="Refresh User",
            role=UserRole.BUSINESS_OWNER
        )
        client.login(email="refresh@example.com", password="password")
        url = reverse("dashboard:refresh")
        response = client.get(url)
        assert response.status_code == 200
        assert b"dashboard-live-container" in response.content

    def test_dashboard_analytics_api(self, client):
        user = User.objects.create_user(
            email="analytics@example.com",
            password="password",
            full_name="Analytics User",
            role=UserRole.BUSINESS_OWNER
        )
        client.login(email="analytics@example.com", password="password")
        url = reverse("dashboard:analytics")
        response = client.get(url)
        assert response.status_code == 200
        json_data = response.json()
        assert "sales_trend" in json_data
        assert "purchase_trend" in json_data
        assert "manufacturing_progress" in json_data
        assert "inventory_movement" in json_data
