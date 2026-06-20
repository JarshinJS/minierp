from decimal import Decimal

from django.db import transaction

from apps.products.models import Product

from .exceptions import InsufficientStockError
from .models import StockDirection, StockLedger, StockMovementType


def _normalize_quantity(quantity):
    decimal_quantity = Decimal(str(quantity))
    if decimal_quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    return decimal_quantity


def _movement_sign(direction):
    if direction == StockDirection.IN:
        return Decimal("1")
    if direction == StockDirection.OUT:
        return Decimal("-1")
    raise ValueError(f"Invalid stock direction: {direction}")


def post_ledger_entry(*, product, movement_type, quantity, direction, reference_type="", reference_id=None):
    normalized_quantity = _normalize_quantity(quantity)

    with transaction.atomic():
        locked_product = Product.objects.select_for_update().get(pk=product.pk)
        new_quantity = locked_product.on_hand_qty + (normalized_quantity * _movement_sign(direction))
        if new_quantity < 0:
            raise InsufficientStockError("Insufficient stock for this operation.")

        locked_product.on_hand_qty = new_quantity
        locked_product.save(update_fields=["on_hand_qty"])

        return StockLedger.objects.create(
            product=locked_product,
            movement_type=movement_type,
            quantity=normalized_quantity,
            direction=direction,
            reference_type=reference_type or "",
            reference_id=reference_id,
        )


def reserve_stock(*, product, quantity, reference_type="stock_reservation", reference_id=None):
    return post_ledger_entry(
        product=product,
        movement_type=StockMovementType.ADJUSTMENT,
        quantity=quantity,
        direction=StockDirection.OUT,
        reference_type=reference_type,
        reference_id=reference_id,
    )


def release_stock(*, product, quantity, reference_type="stock_reservation", reference_id=None):
    return post_ledger_entry(
        product=product,
        movement_type=StockMovementType.ADJUSTMENT,
        quantity=quantity,
        direction=StockDirection.IN,
        reference_type=reference_type,
        reference_id=reference_id,
    )