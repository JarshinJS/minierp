import pytest

from apps.inventory.models import StockDirection, StockMovementType
from apps.inventory.selectors import get_ledger_entries, get_stock_summary
from apps.inventory.services import post_ledger_entry
from apps.inventory.tests.factories import ProductFactory


@pytest.mark.django_db
class TestInventorySelectors:
    def test_get_ledger_entries_filters_by_supported_params(self):
        product_one = ProductFactory(on_hand_qty=0)
        product_two = ProductFactory(on_hand_qty=5)

        entry_one = post_ledger_entry(
            product=product_one,
            movement_type=StockMovementType.PURCHASE_RECEIPT,
            quantity=5,
            direction=StockDirection.IN,
            reference_type="purchase_receipt",
        )
        entry_two = post_ledger_entry(
            product=product_two,
            movement_type=StockMovementType.SALE_DELIVERY,
            quantity=2,
            direction=StockDirection.OUT,
            reference_type="sale_delivery",
        )

        assert list(get_ledger_entries({"product": product_one.pk})) == [entry_one]
        assert list(get_ledger_entries({"movement_type": StockMovementType.SALE_DELIVERY})) == [entry_two]
        assert list(get_ledger_entries({"direction": StockDirection.IN})) == [entry_one]
        assert list(get_ledger_entries({"reference_type": "sale_delivery"})) == [entry_two]

    def test_get_stock_summary_returns_expected_counts(self):
        product = ProductFactory(on_hand_qty=0)
        post_ledger_entry(
            product=product,
            movement_type=StockMovementType.PURCHASE_RECEIPT,
            quantity=3,
            direction=StockDirection.IN,
            reference_type="purchase_receipt",
        )

        summary = get_stock_summary()

        assert summary["total_products"] == 1
        assert summary["ledger_entries"] == 1
        assert summary["total_movement"] == 3