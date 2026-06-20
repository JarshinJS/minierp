import datetime
from decimal import Decimal
from django.db import transaction
from core.exceptions import DomainError, WorkflowError
from apps.inventory import services as inventory_services
from apps.procurement import services as procurement_services
from apps.audit_logs.services import log_event
from apps.audit_logs.models import AuditLogAction
from .models import SalesOrder, SalesOrderLine, SalesOrderStatus

@transaction.atomic
def create_order(customer_name, created_by, lines_data, notes=""):
    """
    Creates a new Sales Order in DRAFT status.
    'lines_data' is a list of dicts: [{'product': Product, 'quantity': Decimal, 'unit_price': Decimal}]
    """
    if not customer_name:
        raise DomainError("Customer name is required.")
    if not lines_data:
        raise DomainError("An order must have at least one line item.")

    # Generate sequential unique order number: SO-YYYYMMDD-COUNT
    today_str = datetime.date.today().strftime("%Y%m%d")
    count = SalesOrder.objects.filter(order_number__startswith=f"SO-{today_str}").count() + 1
    order_number = f"SO-{today_str}-{count:04d}"

    order = SalesOrder.objects.create(
        order_number=order_number,
        customer_name=customer_name,
        created_by=created_by,
        notes=notes,
        status=SalesOrderStatus.DRAFT
    )

    for idx, line in enumerate(lines_data):
        product = line["product"]
        quantity = Decimal(str(line["quantity"]))
        unit_price = Decimal(str(line["unit_price"]))

        if quantity <= 0:
            raise DomainError(f"Line {idx+1}: Quantity must be positive.")
        if unit_price < 0:
            raise DomainError(f"Line {idx+1}: Unit price cannot be negative.")

        SalesOrderLine.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            unit_price=unit_price
        )

    return order


@transaction.atomic
def confirm_order(order):
    """
    Confirms the order. Reserves stock. Triggers procurement if there is a shortage.
    """
    if order.status != SalesOrderStatus.DRAFT:
        raise WorkflowError("Only DRAFT sales orders can be confirmed.")

    for line in order.lines.all():
        # 1. Reserve stock
        inventory_services.reserve_stock(line.product, line.quantity)
        
        # 2. Check shortage: available quantity (available_qty)
        if line.product.on_hand_qty < line.quantity:
            shortage_qty = line.quantity - line.product.on_hand_qty
            procurement_services.trigger_procurement(
                product=line.product,
                quantity_needed=shortage_qty,
                reference=order.order_number
            )

    order.status = SalesOrderStatus.CONFIRMED
    order.save()

    # Log status changed
    log_event(
        user=None,
        module="sales",
        record=order,
        action=AuditLogAction.STATUS_CHANGED,
        field="status",
        old=SalesOrderStatus.DRAFT,
        new=SalesOrderStatus.CONFIRMED
    )
    return order


@transaction.atomic
def deliver_order(order, deliveries_data=None):
    """
    Delivers quantities for a confirmed order.
    'deliveries_data' is a dict mapping line IDs to quantities to deliver: {line_id: quantity}
    If deliveries_data is None, performs a full delivery of all remaining quantities.
    """
    if order.status not in [SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED]:
        raise WorkflowError("Only CONFIRMED or PARTIALLY_DELIVERED orders can be delivered.")

    delivered_any = False
    
    # Pre-fetch lines
    lines = order.lines.all()

    for line in lines:
        qty_to_deliver = Decimal("0.0")
        
        if deliveries_data is None:
            # Deliver all remaining quantities
            qty_to_deliver = line.pending_delivery_qty
        else:
            # Deliver specified quantities
            line_id_str = str(line.id)
            if line_id_str in deliveries_data:
                qty_to_deliver = Decimal(str(deliveries_data[line_id_str]))
            elif line.id in deliveries_data:
                qty_to_deliver = Decimal(str(deliveries_data[line.id]))

        if qty_to_deliver <= 0:
            continue

        if qty_to_deliver > line.pending_delivery_qty:
            raise DomainError(
                f"Cannot deliver {qty_to_deliver} for {line.product.sku}. Only {line.pending_delivery_qty} pending."
            )

        # 1. Issue stock from inventory (reduces on_hand_qty, updates reserved_qty and records ledger entry)
        inventory_services.issue_stock(line.product, qty_to_deliver, reference=order.order_number)

        # 2. Update line delivered quantity
        line.delivered_qty += qty_to_deliver
        line.save()
        delivered_any = True

    if not delivered_any and deliveries_data is not None:
        raise DomainError("No valid quantities were specified for delivery.")

    # Re-evaluate order status
    old_status = order.status
    all_delivered = all(l.delivered_qty == l.quantity for l in lines)
    if all_delivered:
        order.status = SalesOrderStatus.FULLY_DELIVERED
    else:
        order.status = SalesOrderStatus.PARTIALLY_DELIVERED

    order.save()

    # Log status changed if it changed
    if old_status != order.status:
        log_event(
            user=None,
            module="sales",
            record=order,
            action=AuditLogAction.STATUS_CHANGED,
            field="status",
            old=old_status,
            new=order.status
        )

    return order


@transaction.atomic
def cancel_order(order):
    """
    Cancels the sales order. Releases any active stock reservations.
    """
    if order.status not in [SalesOrderStatus.DRAFT, SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED]:
        raise WorkflowError("Only DRAFT, CONFIRMED, or PARTIALLY_DELIVERED orders can be cancelled.")

    old_status = order.status

    # Release any outstanding stock reservations
    if order.status in [SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED]:
        for line in order.lines.all():
            remaining_reserved = line.pending_delivery_qty
            if remaining_reserved > 0:
                inventory_services.release_stock(line.product, remaining_reserved)

    order.status = SalesOrderStatus.CANCELLED
    order.save()

    # Log status changed
    log_event(
        user=None,
        module="sales",
        record=order,
        action=AuditLogAction.STATUS_CHANGED,
        field="status",
        old=old_status,
        new=SalesOrderStatus.CANCELLED
    )
    return order
