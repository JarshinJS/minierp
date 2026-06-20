import datetime
import logging
from decimal import Decimal

from django.db import transaction

from apps.audit_logs.models import AuditLogAction
from apps.audit_logs.services import log_event
from apps.inventory import services as inventory_services
from core.exceptions import DomainError, WorkflowError

from .models import PurchaseOrder, PurchaseOrderLine, PurchaseOrderStatus

logger = logging.getLogger(__name__)


def _generate_order_number():
    today_str = datetime.date.today().strftime("%Y%m%d")
    count = PurchaseOrder.objects.filter(order_number__startswith=f"PO-{today_str}").count() + 1
    return f"PO-{today_str}-{count:04d}"


def _normalize_lines(lines_data):
    if not lines_data:
        raise DomainError("A purchase order must have at least one line item.")

    normalized_lines = []
    for idx, line in enumerate(lines_data):
        product = line["product"]
        quantity = Decimal(str(line["quantity"]))
        unit_price = Decimal(str(line["unit_price"]))

        if quantity <= 0:
            raise DomainError(f"Line {idx + 1}: Quantity must be positive.")
        if unit_price < 0:
            raise DomainError(f"Line {idx + 1}: Unit price cannot be negative.")

        normalized_lines.append({
            "product": product,
            "quantity": quantity,
            "unit_price": unit_price,
        })

    return normalized_lines


def _write_lines(order, lines_data):
    order.lines.all().delete()
    for line in _normalize_lines(lines_data):
        PurchaseOrderLine.objects.create(
            purchase_order=order,
            product=line["product"],
            quantity=line["quantity"],
            unit_price=line["unit_price"],
        )


@transaction.atomic
def create_order(vendor, created_by, lines_data, notes=""):
    if not vendor:
        raise DomainError("Vendor is required.")

    order = PurchaseOrder.objects.create(
        order_number=_generate_order_number(),
        vendor=vendor,
        created_by=created_by,
        notes=notes,
        status=PurchaseOrderStatus.DRAFT,
    )
    _write_lines(order, lines_data)
    return order


@transaction.atomic
def update_order(order, vendor=None, lines_data=None, notes=None):
    if order.status != PurchaseOrderStatus.DRAFT:
        raise WorkflowError("Only DRAFT purchase orders can be edited.")

    if vendor is not None:
        order.vendor = vendor
    if notes is not None:
        order.notes = notes

    order.save()

    if lines_data is not None:
        _write_lines(order, lines_data)

    return order


@transaction.atomic
def confirm_order(order):
    if order.status != PurchaseOrderStatus.DRAFT:
        raise WorkflowError("Only DRAFT purchase orders can be confirmed.")

    old_status = order.status
    order.status = PurchaseOrderStatus.CONFIRMED
    order.save()

    log_event(
        user=None,
        module="purchase",
        record=order,
        action=AuditLogAction.STATUS_CHANGED,
        field="status",
        old=old_status,
        new=order.status,
    )

    logger.info(f"Purchase order notification would have been sent for purchase order {order.id}")

    return order


@transaction.atomic
def receive_order(order, receipts_data=None):
    if order.status not in [PurchaseOrderStatus.CONFIRMED, PurchaseOrderStatus.PARTIALLY_RECEIVED]:
        raise WorkflowError("Only CONFIRMED or PARTIALLY_RECEIVED purchase orders can be received.")

    delivered_any = False
    lines = order.lines.all()

    for line in lines:
        qty_to_receive = Decimal("0.0")

        if receipts_data is None:
            qty_to_receive = line.pending_receive_qty
        else:
            line_id_str = str(line.id)
            if line_id_str in receipts_data:
                qty_to_receive = Decimal(str(receipts_data[line_id_str]))
            elif line.id in receipts_data:
                qty_to_receive = Decimal(str(receipts_data[line.id]))

        if qty_to_receive <= 0:
            continue

        if qty_to_receive > line.pending_receive_qty:
            raise DomainError(
                f"Cannot receive {qty_to_receive} for {line.product.sku}. Only {line.pending_receive_qty} pending."
            )

        inventory_services.receive_stock(line.product, qty_to_receive, reference=order.order_number)
        line.received_qty += qty_to_receive
        line.save()
        delivered_any = True

    if not delivered_any and receipts_data is not None:
        raise DomainError("No valid quantities were specified for receipt.")

    old_status = order.status
    all_received = all(line.received_qty == line.quantity for line in lines)
    order.status = PurchaseOrderStatus.FULLY_RECEIVED if all_received else PurchaseOrderStatus.PARTIALLY_RECEIVED
    order.save()

    if old_status != order.status:
        log_event(
            user=None,
            module="purchase",
            record=order,
            action=AuditLogAction.STATUS_CHANGED,
            field="status",
            old=old_status,
            new=order.status,
        )

    return order


@transaction.atomic
def cancel_order(order):
    if order.status in [PurchaseOrderStatus.FULLY_RECEIVED, PurchaseOrderStatus.CANCELLED]:
        raise WorkflowError("Only DRAFT, CONFIRMED, or PARTIALLY_RECEIVED purchase orders can be cancelled.")

    old_status = order.status
    order.status = PurchaseOrderStatus.CANCELLED
    order.save()

    log_event(
        user=None,
        module="purchase",
        record=order,
        action=AuditLogAction.STATUS_CHANGED,
        field="status",
        old=old_status,
        new=order.status,
    )
    return order