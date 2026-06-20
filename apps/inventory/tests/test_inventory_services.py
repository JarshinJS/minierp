import pytest

from apps.inventory.exceptions import InsufficientStockError
from apps.inventory.models import StockDirection, StockMovementType, StockLedger
from apps.inventory.services import post_ledger_entry, release_stock, reserve_stock
from apps.inventory.tests.factories import ProductFactory


@pytest.mark.django_db
class TestInventoryServices:
    def test_post_ledger_entry_increases_stock_for_inbound_movement(self):
        product = ProductFactory(on_hand_qty=5)

        ledger = post_ledger_entry(
            product=product,
            movement_type=StockMovementType.PURCHASE_RECEIPT,
            quantity=3,
            direction=StockDirection.IN,
            reference_type="purchase_order",
        )

        product.refresh_from_db()
        assert product.on_hand_qty == 8
        assert ledger.quantity == 3
        assert ledger.direction == StockDirection.IN

    def test_post_ledger_entry_decreases_stock_for_outbound_movement(self):
        product = ProductFactory(on_hand_qty=5)

        ledger = post_ledger_entry(
            product=product,
            movement_type=StockMovementType.SALE_DELIVERY,
            quantity=2,
            direction=StockDirection.OUT,
            reference_type="sales_order",
        )

        product.refresh_from_db()
        assert product.on_hand_qty == 3
        assert ledger.direction == StockDirection.OUT

    def test_reserve_stock_raises_and_rolls_back_when_insufficient(self):
        product = ProductFactory(on_hand_qty=4)

        with pytest.raises(InsufficientStockError):
            reserve_stock(product=product, quantity=5, reference_type="sales_order")

        product.refresh_from_db()
        assert product.on_hand_qty == 4
        assert StockLedger.objects.count() == 0

    def test_release_stock_restores_stock(self):
        product = ProductFactory(on_hand_qty=2)

        ledger = release_stock(product=product, quantity=4, reference_type="sales_order")

        product.refresh_from_db()
        assert product.on_hand_qty == 6
        assert ledger.direction == StockDirection.IN

    def test_post_ledger_entry_requires_positive_quantity(self):
        product = ProductFactory(on_hand_qty=1)

        with pytest.raises(ValueError):
            post_ledger_entry(
                product=product,
                movement_type=StockMovementType.ADJUSTMENT,
                quantity=0,
                direction=StockDirection.IN,
            )