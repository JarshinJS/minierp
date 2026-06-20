import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.manufacturing.models import ManufacturingOrder
from apps.products.models import Category, Product, UnitOfMeasure
from apps.purchase.models import PurchaseOrder
from apps.purchase.models import Vendor
from apps.procurement import services
from apps.procurement.models import ProcurementDocumentType, ProcurementTrigger, ProcurementTriggerStatus

User = get_user_model()


@pytest.fixture
def procurement_setup(db):
    category = Category.objects.create(name="Panels")
    vendor = Vendor.objects.create(name="Supply House", code="VEN-100")
    user = User.objects.create_user(email="planner@example.com", password="password", full_name="Planner", role="PURCHASE_USER")

    purchase_product = Product.objects.create(
        name="Shelf Bracket",
        sku="BRK-001",
        category=category,
        cost_price=Decimal("1.50"),
        selling_price=Decimal("3.00"),
        unit_of_measure=UnitOfMeasure.PCS,
        procurement_type="PURCHASE",
        default_vendor=vendor,
    )
    manufacturing_product = Product.objects.create(
        name="Cabinet Door",
        sku="DR-001",
        category=category,
        cost_price=Decimal("10.00"),
        selling_price=Decimal("24.00"),
        unit_of_measure=UnitOfMeasure.PCS,
        procurement_type="MANUFACTURING",
    )

    return {
        "category": category,
        "vendor": vendor,
        "user": user,
        "purchase_product": purchase_product,
        "manufacturing_product": manufacturing_product,
    }


@pytest.mark.django_db
class TestProcurementHandling:
    def test_handle_shortage_creates_purchase_order(self, procurement_setup):
        product = procurement_setup["purchase_product"]
        user = procurement_setup["user"]

        trigger = services.handle_shortage(product, Decimal("5.00"), reference="SO-123", created_by=user)
        trigger.refresh_from_db()

        assert trigger.status == ProcurementTriggerStatus.COMPLETED
        assert trigger.document_type == ProcurementDocumentType.PURCHASE_ORDER
        assert trigger.document_number.startswith("PO-")
        assert PurchaseOrder.objects.filter(order_number=trigger.document_number).exists()

    def test_handle_shortage_creates_manufacturing_order(self, procurement_setup):
        product = procurement_setup["manufacturing_product"]
        user = procurement_setup["user"]

        trigger = services.handle_shortage(product, Decimal("3.00"), reference="SO-456", created_by=user)
        trigger.refresh_from_db()

        assert trigger.status == ProcurementTriggerStatus.COMPLETED
        assert trigger.document_type == ProcurementDocumentType.MANUFACTURING_ORDER
        assert trigger.document_number.startswith("MO-")
        assert ManufacturingOrder.objects.filter(order_number=trigger.document_number).exists()

    def test_trigger_dashboard_records(self, procurement_setup):
        product = procurement_setup["purchase_product"]
        user = procurement_setup["user"]

        trigger = ProcurementTrigger.objects.create(product=product, quantity_needed=Decimal("2.00"), reference="SO-999", created_by=user)
        assert trigger.status == ProcurementTriggerStatus.QUEUED