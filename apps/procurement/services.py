from decimal import Decimal
from django.db import transaction
from django.conf import settings
from django.utils import timezone

from core.exceptions import DomainError
from apps.manufacturing import services as manufacturing_services
from .models import (
    ProcurementDocumentType,
    ProcurementRequest,
    ProcurementStatus,
    ProcurementTrigger,
    ProcurementTriggerStatus,
)


def _normalize_quantity(quantity_needed):
    quantity_needed = Decimal(str(quantity_needed))
    if quantity_needed <= 0:
        raise DomainError("Procurement quantity must be positive.")
    return quantity_needed

def trigger_procurement(product, quantity_needed, reference=""):
    """
    Creates a new pending ProcurementRequest for the given product.
    Called when a Sales Order experiences stock shortages during confirmation.
    """
    quantity_needed = _normalize_quantity(quantity_needed)

    request = ProcurementRequest.objects.create(
        product=product,
        quantity_needed=quantity_needed,
        reference=reference,
        status=ProcurementStatus.PENDING
    )
    return request


@transaction.atomic
def handle_shortage(product, quantity_needed, reference="", created_by=None):
    quantity_needed = _normalize_quantity(quantity_needed)

    trigger = ProcurementTrigger.objects.create(
        product=product,
        quantity_needed=quantity_needed,
        reference=reference,
        created_by=created_by,
        status=ProcurementTriggerStatus.QUEUED,
    )

    # Preserve the legacy procurement request record while the new trigger pipeline runs.
    trigger_procurement(product=product, quantity_needed=quantity_needed, reference=reference)

    from .tasks import create_procurement_document

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        create_procurement_document.delay(str(trigger.id))
    else:
        transaction.on_commit(lambda: create_procurement_document.delay(str(trigger.id)))
    return trigger


@transaction.atomic
def create_procurement_document(trigger):
    if isinstance(trigger, (str,)):
        trigger = ProcurementTrigger.objects.select_for_update().select_related("product", "created_by").get(pk=trigger)
    else:
        trigger = ProcurementTrigger.objects.select_for_update().select_related("product", "created_by").get(pk=trigger.pk)

    if trigger.status == ProcurementTriggerStatus.COMPLETED and trigger.document_id:
        return trigger

    trigger.status = ProcurementTriggerStatus.PROCESSING
    trigger.error_message = ""
    trigger.save(update_fields=["status", "error_message", "updated_at"])

    try:
        if trigger.product.procurement_type == "PURCHASE":
            if not trigger.product.default_vendor:
                raise DomainError(f"Product {trigger.product.sku} requires a default vendor for purchase procurement.")
            from apps.purchase import services as purchase_services

            order = purchase_services.create_order(
                vendor=trigger.product.default_vendor,
                created_by=trigger.created_by,
                lines_data=[{
                    "product": trigger.product,
                    "quantity": trigger.quantity_needed,
                    "unit_price": trigger.product.cost_price,
                }],
                notes=f"Auto-generated from shortage reference {trigger.reference}",
            )
            trigger.document_type = ProcurementDocumentType.PURCHASE_ORDER
            trigger.document_id = order.id
            trigger.document_number = order.order_number
        elif trigger.product.procurement_type == "MANUFACTURING":
            order = manufacturing_services.create_mo(
                product=trigger.product,
                qty_to_produce=trigger.quantity_needed,
                notes=f"Auto-generated from shortage reference {trigger.reference}",
            )
            trigger.document_type = ProcurementDocumentType.MANUFACTURING_ORDER
            trigger.document_id = order.id
            trigger.document_number = order.reference
        else:
            raise DomainError(f"Unsupported procurement type: {trigger.product.procurement_type}")

        trigger.status = ProcurementTriggerStatus.COMPLETED
        trigger.processed_at = timezone.now()
        trigger.error_message = ""
        trigger.save()
        return trigger
    except Exception as exc:
        trigger.status = ProcurementTriggerStatus.FAILED
        trigger.error_message = str(exc)
        trigger.processed_at = timezone.now()
        trigger.save(update_fields=["status", "error_message", "processed_at", "updated_at"])
        return trigger
