import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

User = get_user_model()

@pytest.fixture
def reports_setup(db):
    user = User.objects.create_user(
        email="accountant@example.com",
        password="password",
        full_name="Accountant User",
        role="ACCOUNTANT"
    )
    return {"user": user}


@pytest.mark.django_db
class TestReportsUI:
    def test_reports_views_and_exports(self, client, reports_setup):
        user = reports_setup["user"]
        client.force_login(user)

        # 1. Reports Home View
        url_home = reverse("reports:home")
        response = client.get(url_home)
        assert response.status_code == status.HTTP_200_OK
        assert "Reports & Analytics" in response.content.decode()

        # 2. Export Sales Daily Report
        url_sales_daily = reverse("reports:sales") + "?type=daily"
        response = client.get(url_sales_daily)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"
        assert "Date,Orders Count,Total Revenue" in response.content.decode()

        # 3. Export Sales Monthly Report
        url_sales_monthly = reverse("reports:sales") + "?type=monthly"
        response = client.get(url_sales_monthly)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"
        assert "Month,Orders Count,Total Revenue" in response.content.decode()

        # 4. Export Purchase Summary Report
        url_purchase_summary = reverse("reports:purchase") + "?type=summary"
        response = client.get(url_purchase_summary)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"
        assert "Month,PO Count,Total Purchase Value" in response.content.decode()

        # 5. Export Manufacturing Efficiency Report
        url_mo_efficiency = reverse("reports:manufacturing") + "?type=efficiency"
        response = client.get(url_mo_efficiency)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"
        assert "MO Number,Product SKU,Product Name,Qty Produced,Status,Created At" in response.content.decode()

        # 6. Export Inventory Valuation Report
        url_inv_valuation = reverse("reports:inventory") + "?type=valuation"
        response = client.get(url_inv_valuation)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"
        assert "SKU,Product Name,On Hand,Cost Price,Total Valuation" in response.content.decode()
