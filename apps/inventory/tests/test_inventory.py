import pytest
from decimal import Decimal
from django.db import transaction
from core.exceptions import DomainError
from apps.products.models import Product, Category, UnitOfMeasure
from apps.inventory.models import InventoryLedgerEntry, LedgerEntryType
from apps.inventory import services as inventory_services
from apps.audit_logs.models import AuditLog, AuditLogAction

@pytest.fixture
def inventory_setup(db):
    category = Category.objects.create(name="Boxes")
    product = Product.objects.create(
        name="Cardboard Box",
        sku="BOX-001",
        category=category,
        cost_price=Decimal("1.50"),
        selling_price=Decimal("3.00"),
        unit_of_measure=UnitOfMeasure.BOX
    )
    return {"product": product, "category": category}

@pytest.mark.django_db
class TestInventoryServices:
    def test_post_ledger_entry_receipt_and_issue(self, inventory_setup):
        product = inventory_setup["product"]

        # 1. Receive stock
        inventory_services.receive_stock(product, Decimal("50.00"), reference="Purchase PO-001")
        assert product.on_hand_qty == Decimal("50.00")
        assert product.reserved_qty == Decimal("0.00")

        # Verify receipt ledger entry
        entry = InventoryLedgerEntry.objects.filter(product=product, entry_type=LedgerEntryType.RECEIPT).first()
        assert entry is not None
        assert entry.quantity == Decimal("50.00")
        assert entry.reference == "Purchase PO-001"

        # Verify receipt audit log
        audit_log = AuditLog.objects.filter(record_id=product.id, action=AuditLogAction.STOCK_ADJUSTED, field_changed="on_hand_qty").first()
        assert audit_log is not None
        assert audit_log.old_value == "0.00"
        assert audit_log.new_value == "50.00"

        # 2. Issue stock
        inventory_services.issue_stock(product, Decimal("10.00"), reference="Delivery SO-001")
        assert product.on_hand_qty == Decimal("40.00")

        # Verify issue ledger entry
        entry_issue = InventoryLedgerEntry.objects.filter(product=product, entry_type=LedgerEntryType.ISSUE).first()
        assert entry_issue is not None
        assert entry_issue.quantity == Decimal("10.00")
        assert entry_issue.reference == "Delivery SO-001"

    def test_negative_stock_prevention(self, inventory_setup):
        product = inventory_setup["product"]

        # Try to issue 10 when we have 0 on hand
        with pytest.raises(DomainError) as exc:
            inventory_services.issue_stock(product, Decimal("10.00"))
        assert "Cannot issue 10.00 stock; only 0.00 on hand" in str(exc.value)

    def test_reservations_and_releases(self, inventory_setup):
        product = inventory_setup["product"]

        # Reserve stock
        inventory_services.reserve_stock(product, Decimal("20.00"))
        assert product.reserved_qty == Decimal("20.00")

        # Release stock
        inventory_services.release_stock(product, Decimal("5.00"))
        assert product.reserved_qty == Decimal("15.00")

        # Over-release (fail)
        with pytest.raises(DomainError) as exc:
            inventory_services.release_stock(product, Decimal("30.00"))
        assert "Cannot release 30.00 stock; only 15.00 reserved" in str(exc.value)

    def test_transaction_rollback_safety(self, inventory_setup):
        product = inventory_setup["product"]
        
        # Test that if ledger entry fails or negative stock triggers, no quantity updates persist
        assert product.on_hand_qty == Decimal("0.0")

        try:
            with transaction.atomic():
                # This will fail and rollback because on_hand_qty is 0
                inventory_services.issue_stock(product, Decimal("50.00"))
        except DomainError:
            pass

        product.refresh_from_db()
        assert product.on_hand_qty == Decimal("0.0")
