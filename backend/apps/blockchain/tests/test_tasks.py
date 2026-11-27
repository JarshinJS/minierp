"""
Blockchain anchoring used to run inside the HTTP request: a live submit waits up to
120 s for the receipt, for every document upload and every order event. It now runs
in Celery tasks dispatched after the surrounding transaction commits.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile

from apps.blockchain import tasks
from apps.blockchain.models import BlockchainAuditLog, BlockchainDocument
from apps.blockchain.services.web3_service import Web3ServiceError
from apps.foreign_trade import workflows
from apps.foreign_trade.models import DocumentVerificationStatus

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_mode(settings):
    settings.BLOCKCHAIN_MOCK_MODE = True
    settings.CELERY_TASK_ALWAYS_EAGER = True


def _upload(order, user):
    return workflows.upload_document(
        order, user, file=ContentFile(b"bill of lading", name="bol.pdf"),
        document_type="BILL_OF_LADING", title="BoL",
    )


def test_upload_does_not_touch_chain_before_commit(export_order, user, django_capture_on_commit_callbacks):
    with patch("apps.blockchain.services.verification_service.get_web3_service") as svc:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            doc = _upload(export_order, user)
        svc.assert_not_called()

    assert callbacks, "registration should be deferred to on_commit"
    assert BlockchainDocument.objects.count() == 0
    doc.refresh_from_db()
    assert doc.verification_status == DocumentVerificationStatus.PENDING


def test_upload_registers_document_after_commit(export_order, user, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        doc = _upload(export_order, user)

    doc.refresh_from_db()
    assert BlockchainDocument.objects.filter(document=doc).count() == 1
    assert doc.verification_status == DocumentVerificationStatus.VERIFIED
    assert BlockchainAuditLog.objects.filter(
        event_type=BlockchainAuditLog.EventType.DOCUMENT_UPLOADED, reference_id=str(doc.pk),
    ).exists()


def test_upload_enqueues_task_with_ids(export_order, user, django_capture_on_commit_callbacks):
    with patch.object(tasks.register_document_task, "delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            doc = _upload(export_order, user)
    delay.assert_called_once_with(str(doc.pk), str(user.pk))


def test_upload_survives_chain_failure(export_order, user, django_capture_on_commit_callbacks):
    with patch("apps.blockchain.services.verification_service.register_document", side_effect=Web3ServiceError("node down")):
        with django_capture_on_commit_callbacks(execute=True):
            doc = _upload(export_order, user)
    doc.refresh_from_db()
    assert doc.verification_status == DocumentVerificationStatus.PENDING
    assert BlockchainDocument.objects.count() == 0


def test_order_audit_event_deferred_to_task(user, export_order, django_capture_on_commit_callbacks):
    from apps.foreign_trade.models import Country, Currency, TradeCustomer

    customer = TradeCustomer.objects.first()
    with patch.object(tasks.log_audit_event_task, "delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            order = workflows.create_export(
                user, customer, Country.objects.first(), Currency.objects.first(),
                [{"description": "x", "quantity": 1, "unit_price": Decimal("1.00")}],
            )
    delay.assert_called_once()
    args = delay.call_args.args
    assert args[0] == BlockchainAuditLog.EventType.ORDER_CREATED
    assert args[1] == str(order.pk)
    assert BlockchainAuditLog.objects.count() == 0


def test_register_document_task_runs_and_is_idempotent(trade_document, user):
    tasks.register_document_task.apply(args=[str(trade_document.pk), str(user.pk)]).get()
    tasks.register_document_task.apply(args=[str(trade_document.pk), str(user.pk)]).get()
    assert BlockchainDocument.objects.filter(document=trade_document).count() == 1
    assert BlockchainAuditLog.objects.filter(
        event_type=BlockchainAuditLog.EventType.DOCUMENT_UPLOADED).count() == 1


def test_register_document_task_missing_document():
    assert tasks.register_document_task.apply(
        args=["00000000-0000-0000-0000-000000000000", None]).get() is None


def test_log_audit_event_task(user):
    tasks.log_audit_event_task.apply(
        args=["ORDER_CONFIRMED", "ref-1", "ExportOrder", str(user.pk), {"order_number": "EXP-1"}]).get()
    log = BlockchainAuditLog.objects.get()
    assert log.created_by == user
    assert log.metadata == {"order_number": "EXP-1"}


def test_tasks_retry_on_chain_errors():
    for task in (tasks.register_document_task, tasks.log_audit_event_task):
        assert Web3ServiceError in task.autoretry_for
        assert task.max_retries >= 3
