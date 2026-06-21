"""
services.py for the Audit_logs app.

This module contains the services logic for the Audit_logs functionality.
"""
import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from .models import AuditLog, AuditLogAction


def _resolve_context(record, module=None):
    record_class = record.__class__
    resolved_module = (
        module
        or getattr(record, "audit_module", None)
        or getattr(record_class, "audit_module", None)
        or getattr(getattr(record, "_meta", None), "app_label", None)
        or "unknown"
    )
    resolved_record_type = getattr(record, "audit_record_type", None) or getattr(record_class, "audit_record_type", None) or record_class.__name__
    record_id = getattr(record, "pk", None)
    if record_id is None:
        raise ValueError("Audit records require a persisted record with a primary key.")
    if not isinstance(record_id, uuid.UUID):
        record_id = uuid.UUID(str(record_id))
    return resolved_module, resolved_record_type, record_id


def _serialize_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool, uuid.UUID, Decimal, date, datetime)):
        return str(value)
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, default=str, sort_keys=True)
    return str(value)


def log_event(user, module, record, action, field=None, old=None, new=None):
    resolved_module, record_type, record_id = _resolve_context(record, module)
    return AuditLog.objects.create(
        user=user,
        module=resolved_module,
        record_type=record_type,
        record_id=record_id,
        action=action,
        field_changed=field or "",
        old_value=_serialize_value(old),
        new_value=_serialize_value(new),
    )


def log_create(user, record):
    return log_event(user, None, record, AuditLogAction.CREATED)


def log_delete(user, record):
    return log_event(user, None, record, AuditLogAction.DELETED)