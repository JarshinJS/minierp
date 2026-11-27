"""
Foreign-trade workflow steps: the domain service call plus its blockchain audit
event, in one place so the HTML views and the REST API behave identically.

Blockchain anchoring runs in Celery tasks after the transaction commits, never
inside the request (a live submit waits for the transaction to be mined).
"""
import logging

from apps.blockchain.models import BlockchainAuditLog
from apps.blockchain.services.verification_service import verify_document
from apps.blockchain.tasks import enqueue_audit_event, enqueue_document_registration
from . import services

logger = logging.getLogger(__name__)
Event = BlockchainAuditLog.EventType


def _log(event_type, record, model_name, user, **metadata):
    enqueue_audit_event(
        event_type=event_type, reference_id=str(record.id), reference_model=model_name,
        user=user, metadata=metadata,
    )


# --- Export orders ------------------------------------------------------------

def create_export(user, customer, country, currency, lines_data, **fields):
    order = services.create_export_order(
        customer=customer, country=country, currency=currency,
        lines_data=lines_data, created_by=user, **fields,
    )
    _log(Event.ORDER_CREATED, order, "ExportOrder", user, order_number=order.order_number)
    return order


def confirm_export(order, user):
    services.confirm_export_order(order, user=user)
    _log(Event.ORDER_CONFIRMED, order, "ExportOrder", user, order_number=order.order_number)
    return order


def ship_export(order, shipment_data, user):
    order, shipment = services.ship_export_order(order, shipment_data, user=user)
    _log(Event.SHIPMENT_DISPATCHED, order, "ExportOrder", user,
         order_number=order.order_number, shipment=shipment.shipment_number)
    return order, shipment


def deliver_export(order, user):
    services.deliver_export_order(order, user=user)
    _log(Event.SHIPMENT_DELIVERED, order, "ExportOrder", user, order_number=order.order_number)
    return order


def cancel_export(order, user):
    services.cancel_export_order(order, user=user)
    return order


def create_invoice(order, user, amount=None, due_date=None, notes=""):
    kwargs = {"due_date": due_date, "notes": notes}
    if amount is not None:
        kwargs["amount"] = amount
    invoice = services.create_export_invoice(order, user=user, **kwargs)
    _log(Event.INVOICE_GENERATED, invoice, "ExportInvoice", user,
         invoice_number=invoice.invoice_number, order_number=order.order_number)
    return invoice


# --- Import orders ------------------------------------------------------------

def create_import(user, supplier, country, currency, lines_data, **fields):
    order = services.create_import_order(
        supplier=supplier, country=country, currency=currency,
        lines_data=lines_data, created_by=user, **fields,
    )
    _log(Event.ORDER_CREATED, order, "ImportOrder", user, order_number=order.order_number)
    return order


def confirm_import(order, user):
    services.confirm_import_order(order, user=user)
    _log(Event.ORDER_CONFIRMED, order, "ImportOrder", user, order_number=order.order_number)
    return order


def transit_import(order, shipment_data, user):
    order, shipment = services.transit_import_order(order, shipment_data, user=user)
    _log(Event.SHIPMENT_DISPATCHED, order, "ImportOrder", user, order_number=order.order_number)
    return order, shipment


def customs_import(order, user):
    services.customs_import_order(order, user=user)
    return order


def receive_import(order, user):
    services.receive_import_order(order, user=user)
    _log(Event.CUSTOMS_CLEARED, order, "ImportOrder", user, order_number=order.order_number)
    return order


def cancel_import(order, user):
    services.cancel_import_order(order, user=user)
    return order


# --- Documents ----------------------------------------------------------------

def upload_document(order, user, file, document_type, title, notes=""):
    """Save a new document version, then anchor it on the blockchain in the background.

    The document stays PENDING until the task registers it (and logs DOCUMENT_UPLOADED).
    """
    doc = services.upload_document(
        file=file, document_type=document_type, related_order=order,
        uploaded_by=user, title=title, notes=notes,
    )
    enqueue_document_registration(doc, user)
    return doc


def verify(doc, user):
    result = verify_document(doc)
    if result.get("verified"):
        _log(Event.DOCUMENT_VERIFIED, doc, "TradeDocument", user, title=doc.title, status="verified")
    return result
