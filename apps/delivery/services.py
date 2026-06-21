"""
services.py for the Delivery app.

This module contains the services logic for the Delivery functionality.
"""
import datetime
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from core.exceptions import DomainError, WorkflowError
from apps.inventory import services as inventory_services
from apps.sales.models import SalesOrderStatus
from apps.audit_logs.services import log_event
from apps.audit_logs.models import AuditLogAction
from .models import DeliveryNote, DeliveryNoteLine, DeliveryNoteStatus

logger = logging.getLogger(__name__)

@transaction.atomic
def create_delivery_note(sales_order, lines_data, created_by, notes=""):
    """
    Creates a new Delivery Note in PENDING status.
    'lines_data' is a list of dicts: [{'sales_order_line': SalesOrderLine, 'quantity': Decimal}]
    """
    if sales_order.status not in [SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED]:
        raise WorkflowError("Only CONFIRMED or PARTIALLY_DELIVERED sales orders can have delivery notes.")
    if not lines_data:
        raise DomainError("A delivery note must have at least one line item.")

    # Generate sequential unique delivery number: DN-YYYYMMDD-COUNT
    today_str = datetime.date.today().strftime("%Y%m%d")
    count = DeliveryNote.objects.filter(delivery_number__startswith=f"DN-{today_str}").count() + 1
    delivery_number = f"DN-{today_str}-{count:04d}"

    delivery_note = DeliveryNote.objects.create(
        delivery_number=delivery_number,
        sales_order=sales_order,
        status=DeliveryNoteStatus.PENDING,
        created_by=created_by,
        notes=notes
    )

    for idx, line in enumerate(lines_data):
        so_line = line["sales_order_line"]
        quantity = Decimal(str(line["quantity"]))

        if quantity <= 0:
            raise DomainError(f"Line {idx+1}: Quantity must be positive.")
        if quantity > so_line.pending_delivery_qty:
            raise DomainError(
                f"Line {idx+1}: Cannot deliver {quantity} for {so_line.product.sku}. Only {so_line.pending_delivery_qty} pending."
            )

        DeliveryNoteLine.objects.create(
            delivery_note=delivery_note,
            sales_order_line=so_line,
            quantity=quantity
        )

    # Log delivery note created
    log_event(
        user=created_by,
        module="delivery",
        record=delivery_note,
        action=AuditLogAction.CREATED,
        field="status",
        old="",
        new=DeliveryNoteStatus.PENDING
    )

    return delivery_note



@transaction.atomic
def dispatch_delivery_note(delivery_note, user=None):
    """
    Dispatches the delivery note (items shipped).
    Reduces inventory stock.
    """
    if delivery_note.status != DeliveryNoteStatus.PENDING:
        raise WorkflowError("Only PENDING delivery notes can be dispatched.")

    for line in delivery_note.lines.all():
        so_line = line.sales_order_line
        # Issue stock from inventory (subtracts from on_hand_qty and deallocates from reserved_qty)
        inventory_services.issue_stock(
            product=so_line.product,
            quantity=line.quantity,
            reference=delivery_note.sales_order.order_number
        )

    delivery_note.status = DeliveryNoteStatus.DISPATCHED
    delivery_note.dispatch_date = timezone.now()
    delivery_note.save()

    # Log status changed
    log_event(
        user=user,
        module="delivery",
        record=delivery_note,
        action=AuditLogAction.STATUS_CHANGED,
        field="status",
        old=DeliveryNoteStatus.PENDING,
        new=DeliveryNoteStatus.DISPATCHED
    )
    logger.info(f"Delivery dispatched notification would have been sent for delivery note {delivery_note.id}")

    return delivery_note


@transaction.atomic
def deliver_delivery_note(delivery_note, user=None):
    """
    Marks delivery note as DELIVERED (received by customer).
    Updates delivered quantity on SalesOrderLines and completes SalesOrder if fully delivered.
    """
    if delivery_note.status != DeliveryNoteStatus.DISPATCHED:
        raise WorkflowError("Only DISPATCHED delivery notes can be marked as delivered.")

    delivery_note.status = DeliveryNoteStatus.DELIVERED
    delivery_note.save()

    sales_order = delivery_note.sales_order

    for line in delivery_note.lines.all():
        so_line = line.sales_order_line
        so_line.delivered_qty += line.quantity
        so_line.save()

    # Log delivery status changed
    log_event(
        user=user,
        module="delivery",
        record=delivery_note,
        action=AuditLogAction.STATUS_CHANGED,
        field="status",
        old=DeliveryNoteStatus.DISPATCHED,
        new=DeliveryNoteStatus.DELIVERED
    )

    # Re-evaluate parent Sales Order status
    old_so_status = sales_order.status
    all_lines = sales_order.lines.all()
    all_delivered = all(l.delivered_qty == l.quantity for l in all_lines)

    if all_delivered:
        sales_order.status = SalesOrderStatus.FULLY_DELIVERED
    else:
        sales_order.status = SalesOrderStatus.PARTIALLY_DELIVERED

    sales_order.save()

    if old_so_status != sales_order.status:
        log_event(
            user=user,
            module="sales",
            record=sales_order,
            action=AuditLogAction.STATUS_CHANGED,
            field="status",
            old=old_so_status,
            new=sales_order.status
        )

    return delivery_note
