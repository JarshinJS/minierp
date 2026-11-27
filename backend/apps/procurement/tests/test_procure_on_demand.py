"""
Regression tests: the product's "Procure on demand" flag decides whether a stock
shortage on sales-order confirmation raises a procurement request.

Bug: every shortage raised a request, whatever the flag said. Shortage handling
itself (confirm the order, reserve stock, flag low stock) must not change.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.dashboard.services.alert_service import get_low_stock_alerts
from apps.inventory import services as inventory_services
from apps.inventory.models import InventoryLedgerEntry
from apps.procurement.models import ProcurementRequest, ProcurementTrigger, ProcurementTriggerStatus
from apps.products.models import Category, Product, UnitOfMeasure
from apps.purchase.models import PurchaseOrder, PurchaseOrderStatus, Vendor
from apps.sales import services as sales_services
from apps.sales.models import SalesOrderStatus

User = get_user_model()


@pytest.fixture
def setup(db):
    category = Category.objects.create(name="Furniture")
    vendor = Vendor.objects.create(name="Timber Co", code="V-TMB")
    product = Product.objects.create(
        name="Oak Table", sku="OAK-POD", category=category, unit_of_measure=UnitOfMeasure.PCS,
        cost_price=Decimal("50.00"), selling_price=Decimal("150.00"),
        procurement_type="PURCHASE", default_vendor=vendor,
    )
    inventory_services.receive_stock(product, Decimal("2"), "Opening")
    user = User.objects.create_user(email="sales@example.com", password="pw-12345678", full_name="Sales", role="SALES_USER")
    return {"product": product, "user": user, "vendor": vendor}


def _order_and_confirm(setup, qty):
    order = sales_services.create_order(
        "Acme", setup["user"], [{"product": setup["product"], "quantity": Decimal(qty), "unit_price": Decimal("150")}],
    )
    sales_services.confirm_order(order)
    order.refresh_from_db()
    setup["product"].refresh_from_db()
    return order


def _shortage_is_handled(setup, order):
    """What must happen on a shortage regardless of the flag."""
    product = setup["product"]
    assert order.status == SalesOrderStatus.CONFIRMED
    assert product.on_hand_qty == Decimal("2.00")          # nothing issued
    assert product.reserved_qty == Decimal("5.00")         # full quantity reserved
    assert product.available_qty == Decimal("-3.00")       # shortage of 3
    assert not InventoryLedgerEntry.objects.filter(product=product, entry_type="ISSUE").exists()
    assert product.sku in {a["sku"] for a in get_low_stock_alerts()}  # still flagged


@pytest.mark.django_db
class TestProcureOnDemand:
    def test_flag_off_shortage_creates_no_procurement(self, setup):
        order = _order_and_confirm(setup, "5")
        _shortage_is_handled(setup, order)
        assert not ProcurementTrigger.objects.exists()
        assert not ProcurementRequest.objects.exists()
        assert not PurchaseOrder.objects.exists()

    def test_flag_on_shortage_creates_procurement_for_the_shortfall(self, setup):
        setup["product"].procure_on_demand = True
        setup["product"].save(update_fields=["procure_on_demand"])
        order = _order_and_confirm(setup, "5")
        _shortage_is_handled(setup, order)

        trigger = ProcurementTrigger.objects.get()
        assert trigger.product == setup["product"]
        assert trigger.quantity_needed == Decimal("3.00")
        assert trigger.reference == order.order_number
        assert trigger.status == ProcurementTriggerStatus.COMPLETED   # eager Celery in tests
        po = PurchaseOrder.objects.get(pk=trigger.document_id)
        assert po.vendor == setup["vendor"] and po.status == PurchaseOrderStatus.DRAFT
        assert ProcurementRequest.objects.filter(reference=order.order_number, quantity_needed=Decimal("3.00")).exists()

    def test_flag_on_without_shortage_creates_nothing(self, setup):
        setup["product"].procure_on_demand = True
        setup["product"].save(update_fields=["procure_on_demand"])
        order = _order_and_confirm(setup, "2")
        assert order.status == SalesOrderStatus.CONFIRMED
        assert setup["product"].available_qty == Decimal("0.00")
        assert not ProcurementTrigger.objects.exists()

    def test_flag_is_read_at_confirmation_time(self, setup):
        """Turning the flag on after the order was drafted still applies on confirm."""
        order = sales_services.create_order(
            "Acme", setup["user"], [{"product": setup["product"], "quantity": Decimal("5"), "unit_price": Decimal("150")}],
        )
        Product.objects.filter(pk=setup["product"].pk).update(procure_on_demand=True)
        sales_services.confirm_order(order)
        assert ProcurementTrigger.objects.count() == 1


@pytest.mark.django_db
def test_checkbox_round_trip_through_the_api_controls_procurement(setup):
    """The product form's PUT/PATCH persists the flag, and confirmation honours it."""
    manager = User.objects.create_user(email="inv@example.com", password="pw-12345678", full_name="Inv", role="INVENTORY_MANAGER")
    sales = APIClient()
    sales.force_login(setup["user"])
    inventory = APIClient()
    inventory.force_login(manager)
    product = setup["product"]

    def create_and_confirm():
        order = sales.post("/api/sales-orders/", {
            "customer_name": "Acme",
            "lines": [{"product": str(product.pk), "quantity": "5", "unit_price": "150"}],
        }, format="json")
        assert order.status_code == 201, order.content
        confirmed = sales.post(f"/api/sales-orders/{order.json()['id']}/confirm/")
        assert confirmed.status_code == 200, confirmed.content
        return order.json()["order_number"]

    assert inventory.patch(f"/api/products/{product.pk}/", {"procure_on_demand": False}, format="json").json()["procure_on_demand"] is False
    ref_off = create_and_confirm()
    assert not ProcurementTrigger.objects.filter(reference=ref_off).exists()

    assert inventory.patch(f"/api/products/{product.pk}/", {"procure_on_demand": True}, format="json").json()["procure_on_demand"] is True
    ref_on = create_and_confirm()
    assert ProcurementTrigger.objects.filter(reference=ref_on).exists()
