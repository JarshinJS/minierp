"""
Background blockchain anchoring.

A live submit blocks until the transaction is mined (up to 120 s), so it must not
run inside an HTTP request. Callers use ``enqueue_*`` helpers, which dispatch the
task once the surrounding DB transaction commits (so the worker can see the rows).
"""
import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction

from .services.web3_service import Web3ServiceError

logger = logging.getLogger(__name__)

RETRY_OPTIONS = {
    "autoretry_for": (Web3ServiceError,),
    "retry_backoff": 30,        # 30 s, 60 s, 120 s, ...
    "retry_backoff_max": 600,
    "retry_jitter": True,
    "max_retries": 5,
}


def _user(user_id):
    if not user_id:
        return None
    return get_user_model().objects.filter(pk=user_id).first()


@shared_task(bind=True, name="apps.blockchain.register_document", **RETRY_OPTIONS)
def register_document_task(self, document_id, user_id=None):
    """Anchor a trade document's hash on-chain and record the DOCUMENT_UPLOADED event."""
    from apps.blockchain.models import BlockchainAuditLog
    from apps.blockchain.services.verification_service import log_audit_event, register_document
    from apps.foreign_trade.models import TradeDocument

    doc = TradeDocument.objects.filter(pk=document_id).first()
    if doc is None:
        logger.warning("register_document_task: document %s no longer exists", document_id)
        return None

    bc_doc = register_document(doc)  # idempotent for an already-registered file hash

    event = BlockchainAuditLog.EventType.DOCUMENT_UPLOADED
    if not BlockchainAuditLog.objects.filter(event_type=event, reference_id=str(doc.pk)).exists():
        log_audit_event(
            event_type=event, reference_id=str(doc.pk), reference_model="TradeDocument",
            user=_user(user_id), metadata={"title": doc.title, "type": doc.document_type},
        )
    return str(bc_doc.pk)


@shared_task(bind=True, name="apps.blockchain.log_audit_event", **RETRY_OPTIONS)
def log_audit_event_task(self, event_type, reference_id, reference_model="", user_id=None, metadata=None):
    """Anchor a business event's hash on-chain."""
    from apps.blockchain.services.verification_service import log_audit_event

    log = log_audit_event(
        event_type=event_type, reference_id=reference_id, reference_model=reference_model,
        user=_user(user_id), metadata=metadata or {},
    )
    return str(log.pk)


def _dispatch_on_commit(task, *args):
    def send():
        try:
            task.delay(*args)
        except Exception:
            # Broker down, or (in eager mode) the task failed after all retries.
            # The business action already committed; anchoring can be re-run later.
            logger.exception("Could not run blockchain task %s%r", task.name, args)

    transaction.on_commit(send)


def enqueue_document_registration(document, user=None):
    _dispatch_on_commit(register_document_task, str(document.pk), str(user.pk) if user else None)


def enqueue_audit_event(event_type, reference_id, reference_model="", user=None, metadata=None):
    _dispatch_on_commit(
        log_audit_event_task, str(event_type), str(reference_id), reference_model,
        str(user.pk) if user else None, metadata or {},
    )
