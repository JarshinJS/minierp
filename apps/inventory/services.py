from decimal import Decimal
from django.db import transaction
from core.exceptions import DomainError
from apps.products.models import Product
from apps.audit_logs.services import log_event
from apps.audit_logs.models import AuditLogAction
from .models import InventoryLedgerEntry, LedgerEntryType

@transaction.atomic
def post_ledger_entry(product, entry_type, quantity, reference=""):
    """
    Core function to post inventory ledger entries and modify product stock.
    This is the ONLY function allowed to modify Product.on_hand_qty and Product.reserved_qty.
    """
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise DomainError("Quantity must be positive.")

    # Select product with lock to prevent race conditions
    product_locked = Product.objects.select_for_update().get(pk=product.id)

    old_on_hand = product_locked.on_hand_qty
    old_reserved = product_locked.reserved_qty

    if entry_type == LedgerEntryType.RECEIPT:
        product_locked.on_hand_qty += quantity
    elif entry_type == LedgerEntryType.ISSUE:
        if product_locked.on_hand_qty < quantity:
            raise DomainError(f"Cannot issue {quantity} stock; only {product_locked.on_hand_qty} on hand for {product_locked.name}.")
        product_locked.on_hand_qty -= quantity
        # Also adjust reserved quantity by the amount issued
        product_locked.reserved_qty = max(Decimal("0.0"), product_locked.reserved_qty - quantity)
    elif entry_type == LedgerEntryType.RESERVATION:
        product_locked.reserved_qty += quantity
    elif entry_type == LedgerEntryType.RELEASE:
        if product_locked.reserved_qty < quantity:
            raise DomainError(f"Cannot release {quantity} stock; only {product_locked.reserved_qty} reserved.")
        product_locked.reserved_qty -= quantity
    else:
        raise DomainError(f"Unknown ledger entry type: {entry_type}")

    product_locked.save()

    # Sync back to memory reference if they are different objects
    product.on_hand_qty = product_locked.on_hand_qty
    product.reserved_qty = product_locked.reserved_qty

    entry = InventoryLedgerEntry.objects.create(
        product=product_locked,
        quantity=quantity,
        entry_type=entry_type,
        reference=reference
    )

    # Log inventory movement as STOCK_ADJUSTED
    if entry_type in [LedgerEntryType.RECEIPT, LedgerEntryType.ISSUE]:
        log_event(
            user=None,
            module="inventory",
            record=product_locked,
            action=AuditLogAction.STOCK_ADJUSTED,
            field="on_hand_qty",
            old=old_on_hand,
            new=product_locked.on_hand_qty
        )
    elif entry_type in [LedgerEntryType.RESERVATION, LedgerEntryType.RELEASE]:
        log_event(
            user=None,
            module="inventory",
            record=product_locked,
            action=AuditLogAction.STOCK_ADJUSTED,
            field="reserved_qty",
            old=old_reserved,
            new=product_locked.reserved_qty
        )

    return entry


@transaction.atomic
def reserve_stock(product, quantity):
    """
    Reserves stock for a sales order. Increments product's reserved quantity.
    """
    post_ledger_entry(product, LedgerEntryType.RESERVATION, quantity, reference="Sales Order Reservation")
    return product


@transaction.atomic
def release_stock(product, quantity):
    """
    Releases reserved stock (e.g. on order cancellation).
    """
    post_ledger_entry(product, LedgerEntryType.RELEASE, quantity, reference="Sales Order Release")
    return product


@transaction.atomic
def issue_stock(product, quantity, reference=""):
    """
    Issues stock (delivery). Subtracts from on_hand_qty, and deallocates from reserved_qty.
    """
    post_ledger_entry(product, LedgerEntryType.ISSUE, quantity, reference=reference)
    return product


@transaction.atomic
def receive_stock(product, quantity, reference=""):
    """
    Receives stock (e.g. purchase receipt or manufacturing input).
    """
    post_ledger_entry(product, LedgerEntryType.RECEIPT, quantity, reference=reference)
    return product
