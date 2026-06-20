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
        
        # Refresh product to get the updated reserved_qty
        product = line.product
        product.refresh_from_db()
        
        # 2. Check shortage: available quantity (available_qty)
        if product.available_qty < 0:
            shortage_qty = -product.available_qty
            procurement_services.handle_shortage(
                product=product,
                quantity_needed=shortage_qty,
                reference=order.order_number,
                created_by=order.created_by,
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
    Delivers quantities for a confirmed order by running the E2E Delivery Note workflow.
    'deliveries_data' is a dict mapping line IDs to quantities to deliver: {line_id: quantity}
    If deliveries_data is None, performs a full delivery of all remaining quantities.
    """
    if order.status not in [SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED]:
        raise WorkflowError("Only CONFIRMED or PARTIALLY_DELIVERED orders can be delivered.")

    from apps.delivery import services as delivery_services

    lines = order.lines.all()
    lines_list = []

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

        lines_list.append({
            "sales_order_line": line,
            "quantity": qty_to_deliver
        })

    if not lines_list:
        if deliveries_data is not None:
            raise DomainError("No valid quantities were specified for delivery.")
        return order

    # 1. Create PENDING delivery note
    dn = delivery_services.create_delivery_note(
        sales_order=order,
        lines_data=lines_list,
        created_by=order.created_by
    )

    # 2. Dispatch delivery note (issues stock)
    delivery_services.dispatch_delivery_note(dn)

    # 3. Complete delivery (marks delivered, updates sales order lines/status)
    delivery_services.deliver_delivery_note(dn)

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
