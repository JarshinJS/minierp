import datetime
from decimal import Decimal

from django.db import transaction

from core.exceptions import DomainError, WorkflowError

from .models import ManufacturingOrder, ManufacturingOrderStatus


def _generate_order_number():
    today_str = datetime.date.today().strftime("%Y%m%d")
    count = ManufacturingOrder.objects.filter(order_number__startswith=f"MO-{today_str}").count() + 1
    return f"MO-{today_str}-{count:04d}"


@transaction.atomic
def create_order(product, quantity, reference="", created_by=None, notes=""):
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise DomainError("Manufacturing quantity must be positive.")

    order = ManufacturingOrder.objects.create(
        order_number=_generate_order_number(),
        product=product,
        bom=product.default_bom,
        quantity=quantity,
        reference=reference,
        notes=notes,
        created_by=created_by,
        status=ManufacturingOrderStatus.DRAFT,
    )
    return order


@transaction.atomic
def confirm_order(order):
    if order.status != ManufacturingOrderStatus.DRAFT:
        raise WorkflowError("Only DRAFT manufacturing orders can be confirmed.")
    order.status = ManufacturingOrderStatus.CONFIRMED
    order.save(update_fields=["status", "updated_at"])
    return order


@transaction.atomic
def complete_order(order):
    if order.status not in [ManufacturingOrderStatus.DRAFT, ManufacturingOrderStatus.CONFIRMED]:
        raise WorkflowError("Only DRAFT or CONFIRMED manufacturing orders can be completed.")
    order.status = ManufacturingOrderStatus.COMPLETED
    order.save(update_fields=["status", "updated_at"])
    return order


@transaction.atomic
def cancel_order(order):
    if order.status == ManufacturingOrderStatus.COMPLETED:
        raise WorkflowError("Completed manufacturing orders cannot be cancelled.")
    order.status = ManufacturingOrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    return order