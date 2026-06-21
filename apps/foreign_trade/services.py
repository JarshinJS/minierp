"""
services.py for the Foreign_trade app.

This module contains the services logic for the Foreign_trade functionality.
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from core.exceptions import DomainError, WorkflowError
from apps.audit_logs.services import log_event
from apps.audit_logs.models import AuditLogAction

from .models import (
    ExportOrder, ExportOrderLine, ExportOrderStatus,
    ImportOrder, ImportOrderLine, ImportOrderStatus,
    ExportInvoice, InvoiceStatus,
    Shipment, ShipmentStatus,
    TradeDocument, DocumentVerificationStatus,
    CustomsStatus,
)


# ===========================================================================
# Order Number Generation
# ===========================================================================

def _generate_order_number(prefix, model_class):
    today_str = datetime.date.today().strftime("%Y%m%d")
    count = model_class.objects.filter(order_number__startswith=f"{prefix}-{today_str}").count() + 1
    return f"{prefix}-{today_str}-{count:04d}"


def _generate_number(prefix, model_class, field="shipment_number"):
    today_str = datetime.date.today().strftime("%Y%m%d")
    lookup = {f"{field}__startswith": f"{prefix}-{today_str}"}
    count = model_class.objects.filter(**lookup).count() + 1
    return f"{prefix}-{today_str}-{count:04d}"


# ===========================================================================
# Export Order Services
# ===========================================================================

@transaction.atomic
def create_export_order(customer, country, currency, lines_data, created_by, **kwargs):
    """
    Creates a new Export Order in DRAFT status.
    lines_data: list of dicts [{'description': str, 'quantity': Decimal, 'unit_price': Decimal, 'hs_code': str}]
    """
    if not customer:
        raise DomainError("Customer is required.")
    if not lines_data:
        raise DomainError("An export order must have at least one line item.")

    order_number = _generate_order_number("EXP", ExportOrder)

    order = ExportOrder.objects.create(
        order_number=order_number,
        customer=customer,
        country=country,
        currency=currency,
        incoterm=kwargs.get("incoterm"),
        shipping_method=kwargs.get("shipping_method", "SEA"),
        port_of_loading=kwargs.get("port_of_loading", ""),
        port_of_destination=kwargs.get("port_of_destination", ""),
        container_details=kwargs.get("container_details", ""),
        notes=kwargs.get("notes", ""),
        created_by=created_by,
        status=ExportOrderStatus.DRAFT,
    )

    for idx, line in enumerate(lines_data):
        quantity = Decimal(str(line["quantity"]))
        unit_price = Decimal(str(line["unit_price"]))
        if quantity <= 0:
            raise DomainError(f"Line {idx + 1}: Quantity must be positive.")
        if unit_price < 0:
            raise DomainError(f"Line {idx + 1}: Unit price cannot be negative.")

        ExportOrderLine.objects.create(
            export_order=order,
            description=line["description"],
            hs_code=line.get("hs_code", ""),
            quantity=quantity,
            unit_price=unit_price,
        )

    log_event(user=created_by, module="foreign_trade", record=order, action=AuditLogAction.CREATED)
    return order


@transaction.atomic
def confirm_export_order(order, user=None):
    if order.status not in (ExportOrderStatus.DRAFT, ExportOrderStatus.QUOTATION):
        raise WorkflowError("Only DRAFT or QUOTATION export orders can be confirmed.")

    old_status = order.status
    order.status = ExportOrderStatus.CONFIRMED
    order.save()

    log_event(user=user, module="foreign_trade", record=order,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=ExportOrderStatus.CONFIRMED)
    return order


@transaction.atomic
def ship_export_order(order, shipment_data=None, user=None):
    if order.status != ExportOrderStatus.CONFIRMED:
        raise WorkflowError("Only CONFIRMED export orders can be shipped.")

    shipment_data = shipment_data or {}
    ct = ContentType.objects.get_for_model(ExportOrder)
    shipment_number = _generate_number("SHP", Shipment)

    shipment = Shipment.objects.create(
        shipment_number=shipment_number,
        content_type=ct,
        object_id=order.id,
        carrier=shipment_data.get("carrier", ""),
        tracking_number=shipment_data.get("tracking_number", ""),
        vessel_name=shipment_data.get("vessel_name", ""),
        port_of_loading=shipment_data.get("port_of_loading", order.port_of_loading),
        port_of_destination=shipment_data.get("port_of_destination", order.port_of_destination),
        departure_date=shipment_data.get("departure_date"),
        arrival_date=shipment_data.get("arrival_date"),
        status=ShipmentStatus.IN_TRANSIT,
        created_by=user or order.created_by,
    )

    old_status = order.status
    order.status = ExportOrderStatus.SHIPPED
    order.save()

    log_event(user=user, module="foreign_trade", record=order,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=ExportOrderStatus.SHIPPED)
    return order, shipment


@transaction.atomic
def deliver_export_order(order, user=None):
    if order.status != ExportOrderStatus.SHIPPED:
        raise WorkflowError("Only SHIPPED export orders can be marked as delivered.")

    old_status = order.status
    order.status = ExportOrderStatus.DELIVERED
    order.save()

    # Update related shipments to DELIVERED
    ct = ContentType.objects.get_for_model(ExportOrder)
    Shipment.objects.filter(content_type=ct, object_id=order.id).exclude(
        status=ShipmentStatus.DELIVERED
    ).update(status=ShipmentStatus.DELIVERED)

    log_event(user=user, module="foreign_trade", record=order,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=ExportOrderStatus.DELIVERED)
    return order


@transaction.atomic
def cancel_export_order(order, user=None):
    if order.status in (ExportOrderStatus.DELIVERED, ExportOrderStatus.CANCELLED):
        raise WorkflowError("DELIVERED or already CANCELLED export orders cannot be cancelled.")

    old_status = order.status
    order.status = ExportOrderStatus.CANCELLED
    order.save()

    log_event(user=user, module="foreign_trade", record=order,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=ExportOrderStatus.CANCELLED)
    return order


@transaction.atomic
def create_export_invoice(order, user=None, **kwargs):
    if order.status not in (ExportOrderStatus.CONFIRMED, ExportOrderStatus.SHIPPED, ExportOrderStatus.DELIVERED):
        raise WorkflowError("Invoices can only be created for CONFIRMED, SHIPPED, or DELIVERED orders.")

    today_str = datetime.date.today().strftime("%Y%m%d")
    count = ExportInvoice.objects.filter(invoice_number__startswith=f"EINV-{today_str}").count() + 1
    invoice_number = f"EINV-{today_str}-{count:04d}"

    invoice = ExportInvoice.objects.create(
        invoice_number=invoice_number,
        export_order=order,
        amount=kwargs.get("amount", order.total_amount),
        currency=order.currency,
        status=InvoiceStatus.DRAFT,
        due_date=kwargs.get("due_date"),
        notes=kwargs.get("notes", ""),
    )

    log_event(user=user, module="foreign_trade", record=invoice, action=AuditLogAction.CREATED)
    return invoice


# ===========================================================================
# Import Order Services
# ===========================================================================

@transaction.atomic
def create_import_order(supplier, country, currency, lines_data, created_by, **kwargs):
    if not supplier:
        raise DomainError("Supplier is required.")
    if not lines_data:
        raise DomainError("An import order must have at least one line item.")

    order_number = _generate_order_number("IMP", ImportOrder)

    order = ImportOrder.objects.create(
        order_number=order_number,
        supplier=supplier,
        country=country,
        currency=currency,
        container_number=kwargs.get("container_number", ""),
        eta=kwargs.get("eta"),
        notes=kwargs.get("notes", ""),
        created_by=created_by,
        status=ImportOrderStatus.DRAFT,
    )

    for idx, line in enumerate(lines_data):
        quantity = Decimal(str(line["quantity"]))
        unit_price = Decimal(str(line["unit_price"]))
        if quantity <= 0:
            raise DomainError(f"Line {idx + 1}: Quantity must be positive.")
        if unit_price < 0:
            raise DomainError(f"Line {idx + 1}: Unit price cannot be negative.")

        ImportOrderLine.objects.create(
            import_order=order,
            description=line["description"],
            hs_code=line.get("hs_code", ""),
            quantity=quantity,
            unit_price=unit_price,
        )

    log_event(user=created_by, module="foreign_trade", record=order, action=AuditLogAction.CREATED)
    return order


@transaction.atomic
def confirm_import_order(order, user=None):
    if order.status != ImportOrderStatus.DRAFT:
        raise WorkflowError("Only DRAFT import orders can be confirmed.")

    old_status = order.status
    order.status = ImportOrderStatus.CONFIRMED
    order.save()

    log_event(user=user, module="foreign_trade", record=order,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=ImportOrderStatus.CONFIRMED)
    return order


@transaction.atomic
def transit_import_order(order, shipment_data=None, user=None):
    if order.status != ImportOrderStatus.CONFIRMED:
        raise WorkflowError("Only CONFIRMED import orders can be moved to IN TRANSIT.")

    shipment_data = shipment_data or {}
    ct = ContentType.objects.get_for_model(ImportOrder)
    shipment_number = _generate_number("SHP", Shipment)

    shipment = Shipment.objects.create(
        shipment_number=shipment_number,
        content_type=ct,
        object_id=order.id,
        carrier=shipment_data.get("carrier", ""),
        tracking_number=shipment_data.get("tracking_number", ""),
        vessel_name=shipment_data.get("vessel_name", ""),
        port_of_loading=shipment_data.get("port_of_loading", ""),
        port_of_destination=shipment_data.get("port_of_destination", ""),
        departure_date=shipment_data.get("departure_date"),
        arrival_date=shipment_data.get("arrival_date"),
        status=ShipmentStatus.IN_TRANSIT,
        created_by=user or order.created_by,
    )

    old_status = order.status
    order.status = ImportOrderStatus.IN_TRANSIT
    order.save()

    log_event(user=user, module="foreign_trade", record=order,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=ImportOrderStatus.IN_TRANSIT)
    return order, shipment


@transaction.atomic
def customs_import_order(order, user=None):
    if order.status != ImportOrderStatus.IN_TRANSIT:
        raise WorkflowError("Only IN TRANSIT import orders can enter CUSTOMS.")

    old_status = order.status
    order.status = ImportOrderStatus.CUSTOMS
    order.customs_status = CustomsStatus.DOCUMENTS_SUBMITTED
    order.save()

    log_event(user=user, module="foreign_trade", record=order,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=ImportOrderStatus.CUSTOMS)
    return order


@transaction.atomic
def receive_import_order(order, user=None):
    if order.status != ImportOrderStatus.CUSTOMS:
        raise WorkflowError("Only orders in CUSTOMS can be marked as RECEIVED.")

    old_status = order.status
    order.status = ImportOrderStatus.RECEIVED
    order.customs_status = CustomsStatus.CLEARED
    order.save()

    # Mark related shipments as delivered
    ct = ContentType.objects.get_for_model(ImportOrder)
    Shipment.objects.filter(content_type=ct, object_id=order.id).exclude(
        status=ShipmentStatus.DELIVERED
    ).update(status=ShipmentStatus.DELIVERED)

    log_event(user=user, module="foreign_trade", record=order,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=ImportOrderStatus.RECEIVED)
    return order


@transaction.atomic
def cancel_import_order(order, user=None):
    if order.status in (ImportOrderStatus.RECEIVED, ImportOrderStatus.CANCELLED):
        raise WorkflowError("RECEIVED or already CANCELLED import orders cannot be cancelled.")

    old_status = order.status
    order.status = ImportOrderStatus.CANCELLED
    order.save()

    log_event(user=user, module="foreign_trade", record=order,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=ImportOrderStatus.CANCELLED)
    return order


# ===========================================================================
# Document Services
# ===========================================================================

@transaction.atomic
def upload_document(file, document_type, related_order, uploaded_by, **kwargs):
    """Upload a trade document with auto-versioning."""
    ct = ContentType.objects.get_for_model(related_order)

    # Determine next version number
    latest = TradeDocument.objects.filter(
        content_type=ct,
        object_id=related_order.id,
        document_type=document_type,
    ).order_by("-version").first()
    next_version = (latest.version + 1) if latest else 1

    title = kwargs.get("title", f"{document_type} v{next_version}")

    doc = TradeDocument.objects.create(
        document_type=document_type,
        title=title,
        file=file,
        version=next_version,
        content_type=ct,
        object_id=related_order.id,
        verification_status=DocumentVerificationStatus.PENDING,
        uploaded_by=uploaded_by,
        notes=kwargs.get("notes", ""),
    )

    log_event(user=uploaded_by, module="foreign_trade", record=doc, action=AuditLogAction.CREATED)
    return doc


def get_document_history(related_order, document_type=None):
    """Get all document versions for an order, optionally filtered by type."""
    ct = ContentType.objects.get_for_model(related_order)
    qs = TradeDocument.objects.filter(content_type=ct, object_id=related_order.id)
    if document_type:
        qs = qs.filter(document_type=document_type)
    return qs.order_by("document_type", "-version")


def get_order_documents(related_order):
    """Get all documents for a specific order."""
    ct = ContentType.objects.get_for_model(related_order)
    return TradeDocument.objects.filter(content_type=ct, object_id=related_order.id).order_by("-created_at")


# ===========================================================================
# Shipment Services
# ===========================================================================

@transaction.atomic
def update_shipment_status(shipment, new_status, user=None):
    valid_transitions = {
        ShipmentStatus.PENDING: [ShipmentStatus.IN_TRANSIT],
        ShipmentStatus.IN_TRANSIT: [ShipmentStatus.AT_PORT, ShipmentStatus.CUSTOMS, ShipmentStatus.DELIVERED],
        ShipmentStatus.AT_PORT: [ShipmentStatus.CUSTOMS, ShipmentStatus.DELIVERED],
        ShipmentStatus.CUSTOMS: [ShipmentStatus.DELIVERED],
    }

    allowed = valid_transitions.get(shipment.status, [])
    if new_status not in allowed:
        raise WorkflowError(
            f"Cannot transition shipment from {shipment.get_status_display()} to {new_status}."
        )

    old_status = shipment.status
    shipment.status = new_status
    shipment.save()

    log_event(user=user, module="foreign_trade", record=shipment,
              action=AuditLogAction.STATUS_CHANGED, field="status",
              old=old_status, new=new_status)
    return shipment
