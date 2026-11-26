import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit_logs.models import AuditLogAction
from apps.audit_logs.selectors import get_audit_logs, get_audit_summary
from apps.audit_logs.services import log_event
from apps.audit_logs.tests.factories import UserFactory


class DummyRecord:
    audit_module = "sales"
    audit_record_type = "SalesOrder"

    def __init__(self, pk):
        self.pk = pk


def _log(action, module, record_type, user=None):
    record = DummyRecord(uuid.uuid4())
    record.audit_module = module
    record.audit_record_type = record_type
    return log_event(user=user, module=None, record=record, action=action)


@pytest.mark.django_db
class TestAuditSelectors:
    def test_get_audit_logs_filters_by_every_supported_param(self):
        user_one = UserFactory()
        user_two = UserFactory()

        created = _log(AuditLogAction.CREATED, "sales", "SalesOrder", user_one)
        updated = _log(AuditLogAction.UPDATED, "inventory", "StockMove", user_two)
        deleted = _log(AuditLogAction.DELETED, "sales", "SalesOrder", user_one)

        type(created).objects.filter(pk=created.pk).update(timestamp=timezone.now() - timedelta(days=2))
        type(updated).objects.filter(pk=updated.pk).update(timestamp=timezone.now() - timedelta(days=1))
        type(deleted).objects.filter(pk=deleted.pk).update(timestamp=timezone.now())

        assert list(get_audit_logs({"module": "sales"})) == [deleted, created]
        assert list(get_audit_logs({"user": user_two.pk})) == [updated]
        assert list(get_audit_logs({"action": AuditLogAction.UPDATED})) == [updated]
        assert list(get_audit_logs({"record_type": "SalesOrder"})) == [deleted, created]
        assert list(get_audit_logs({"record_id": str(created.record_id)})) == [created]
        assert list(get_audit_logs({"date_from": (timezone.now() - timedelta(days=1)).date()})) == [deleted, updated]
        assert list(get_audit_logs({"date_to": (timezone.now() - timedelta(days=1)).date()})) == [updated, created]

        # Test invalid UUID values do not crash and return empty
        assert list(get_audit_logs({"user": "qqq"})) == []
        assert list(get_audit_logs({"record_id": "invalid-uuid"})) == []

    def test_get_audit_summary_counts_expected_actions(self):
        _log(AuditLogAction.CREATED, "sales", "SalesOrder")
        _log(AuditLogAction.CREATED, "sales", "SalesOrder")
        _log(AuditLogAction.UPDATED, "sales", "SalesOrder")
        _log(AuditLogAction.DELETED, "sales", "SalesOrder")

        summary = get_audit_summary()

        assert summary == {"total": 4, "created": 2, "updated": 1, "deleted": 1}