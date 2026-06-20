import json
import uuid
from datetime import date

import pytest

from apps.audit_logs.models import AuditLog, AuditLogAction
from apps.audit_logs.services import log_create, log_delete, log_event
from apps.audit_logs.tests.factories import UserFactory


class DummyRecord:
    audit_module = "sales"
    audit_record_type = "SalesOrder"

    def __init__(self, pk):
        self.pk = pk


@pytest.mark.django_db
class TestAuditLogServices:
    def test_log_event_writes_expected_fields(self):
        user = UserFactory()
        record = DummyRecord(uuid.uuid4())

        log = log_event(
            user=user,
            module=None,
            record=record,
            action=AuditLogAction.STATUS_CHANGED,
            field="status",
            old="draft",
            new="confirmed",
        )

        assert log.user == user
        assert log.module == "sales"
        assert log.record_type == "SalesOrder"
        assert log.record_id == record.pk
        assert log.action == AuditLogAction.STATUS_CHANGED
        assert log.field_changed == "status"
        assert log.old_value == "draft"
        assert log.new_value == "confirmed"

    def test_log_event_serializes_non_scalar_values(self):
        record = DummyRecord(uuid.uuid4())

        log = log_event(
            user=None,
            module="inventory",
            record=record,
            action=AuditLogAction.UPDATED,
            field="payload",
            old={"quantity": 2, "tags": ["a", "b"]},
            new=[1, 2, 3],
        )

        assert json.loads(log.old_value) == {"quantity": 2, "tags": ["a", "b"]}
        assert json.loads(log.new_value) == [1, 2, 3]

    def test_log_event_serializes_scalars_and_string_pk(self):
        record = DummyRecord(str(uuid.uuid4()))

        log = log_event(
            user=None,
            module="inventory",
            record=record,
            action=AuditLogAction.PRICE_CHANGED,
            field="price",
            old=12.5,
            new=date(2026, 1, 1),
        )

        assert log.record_id == uuid.UUID(record.pk)
        assert log.old_value == "12.5"
        assert log.new_value == "2026-01-01"

    def test_log_event_raises_for_unsaved_records(self):
        record = DummyRecord(None)

        with pytest.raises(ValueError):
            log_event(user=None, module="inventory", record=record, action=AuditLogAction.CREATED)

    def test_log_event_falls_back_to_string_for_custom_objects(self):
        class CustomPayload:
            def __str__(self):
                return "custom-payload"

        record = DummyRecord(uuid.uuid4())

        log = log_event(
            user=None,
            module="inventory",
            record=record,
            action=AuditLogAction.UPDATED,
            field="metadata",
            old=CustomPayload(),
            new=CustomPayload(),
        )

        assert log.old_value == "custom-payload"
        assert log.new_value == "custom-payload"

    def test_log_create_and_delete_wrap_log_event(self):
        record = DummyRecord(uuid.uuid4())

        created_log = log_create(None, record)
        deleted_log = log_delete(None, record)

        assert created_log.action == AuditLogAction.CREATED
        assert deleted_log.action == AuditLogAction.DELETED
        assert AuditLog.objects.count() == 2