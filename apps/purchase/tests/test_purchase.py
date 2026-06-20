import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.models import InventoryLedgerEntry, LedgerEntryType
from apps.products.models import Category, Product, UnitOfMeasure
from apps.purchase.models import PurchaseOrder, PurchaseOrderStatus, Vendor
from apps.purchase import services

User = get_user_model()


@pytest.fixture
def purchase_setup(db):
    category = Category.objects.create(name="Hardware")
    product = Product.objects.create(
        name="Steel Hinge",
        sku="HNG-001",
        category=category,
        cost_price=Decimal("2.50"),
        selling_price=Decimal("5.00"),
        unit_of_measure=UnitOfMeasure.PCS,
    )
    vendor = Vendor.objects.create(name="Fasteners Co", code="VEN-001", contact_name="Buyer", email="buyer@example.com")
    user = User.objects.create_user(email="buyer@example.com", password="password", full_name="Buyer", role="PURCHASE_USER")
    return {"category": category, "product": product, "vendor": vendor, "user": user}


@pytest.mark.django_db
class TestPurchaseServices:
    def test_purchase_workflow_receives_stock(self, purchase_setup):
        product = purchase_setup["product"]
        vendor = purchase_setup["vendor"]
        user = purchase_setup["user"]

        order = services.create_order(
            vendor=vendor,
            created_by=user,
            lines_data=[{"product": product, "quantity": Decimal("10.00"), "unit_price": Decimal("2.25")}],
            notes="Urgent restock",
        )

        assert order.status == PurchaseOrderStatus.DRAFT
        services.confirm_order(order)
        order.refresh_from_db()
        assert order.status == PurchaseOrderStatus.CONFIRMED

        services.receive_order(order, {str(order.lines.first().id): Decimal("4.00")})
        order.refresh_from_db()
        product.refresh_from_db()
        line = order.lines.first()

        assert order.status == PurchaseOrderStatus.PARTIALLY_RECEIVED
        assert line.received_qty == Decimal("4.00")
        assert product.on_hand_qty == Decimal("4.00")

        services.receive_order(order)
        order.refresh_from_db()
        product.refresh_from_db()
        line.refresh_from_db()

        assert order.status == PurchaseOrderStatus.FULLY_RECEIVED
        assert line.received_qty == Decimal("10.00")
        assert product.on_hand_qty == Decimal("10.00")

        ledger_entries = InventoryLedgerEntry.objects.filter(
            product=product,
            entry_type=LedgerEntryType.RECEIPT,
            reference=order.order_number,
        )
        assert ledger_entries.exists()
        assert sum(entry.quantity for entry in ledger_entries) == Decimal("10.00")

    def test_cancel_purchase_order(self, purchase_setup):
        product = purchase_setup["product"]
        vendor = purchase_setup["vendor"]
        user = purchase_setup["user"]

        order = services.create_order(
            vendor=vendor,
            created_by=user,
            lines_data=[{"product": product, "quantity": Decimal("3.00"), "unit_price": Decimal("2.00")}],
        )
        services.confirm_order(order)
        services.cancel_order(order)

        order.refresh_from_db()
        assert order.status == PurchaseOrderStatus.CANCELLED


@pytest.mark.django_db
class TestPurchaseAPI:
    def test_vendor_and_order_api(self, purchase_setup):
        product = purchase_setup["product"]
        user = User.objects.create_user(email="admin@example.com", password="password", full_name="Admin", role="ADMIN")
        client = APIClient()
        client.force_authenticate(user=user)

        vendor_url = reverse("purchase:api_vendor-list")
        vendor_response = client.post(
            vendor_url,
            {"name": "Supply Hub", "code": "VEN-002", "contact_name": "Maya", "email": "maya@example.com"},
            format="json",
        )
        assert vendor_response.status_code == status.HTTP_201_CREATED

        order_url = reverse("purchase:api_purchase_order-list")
        order_response = client.post(
            order_url,
            {
                "vendor": str(purchase_setup["vendor"].id),
                "notes": "API order",
                "lines": [
                    {
                        "product": str(product.id),
                        "quantity": "2.00",
                        "unit_price": "2.10",
                    }
                ],
            },
            format="json",
        )
        assert order_response.status_code == status.HTTP_201_CREATED
        order_id = order_response.data["id"]

        confirm_url = reverse("purchase:api_purchase_order-confirm", args=[order_id])
        confirm_response = client.post(confirm_url)
        assert confirm_response.status_code == status.HTTP_200_OK
        assert confirm_response.data["status"] == PurchaseOrderStatus.CONFIRMED

        receive_url = reverse("purchase:api_purchase_order-receive", args=[order_id])
        receive_response = client.post(receive_url, {"receipts": {str(order_response.data["lines"][0]["id"]): "2.00"}}, format="json")
        assert receive_response.status_code == status.HTTP_200_OK
        assert receive_response.data["status"] == PurchaseOrderStatus.FULLY_RECEIVED