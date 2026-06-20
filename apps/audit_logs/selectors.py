import uuid
from django.db.models import Count, Q

from .models import AuditLog, AuditLogAction


def _value(filters_data, key):
    if filters_data is None:
        return None
    if hasattr(filters_data, "get"):
        return filters_data.get(key)
    return filters_data[key] if key in filters_data else None


def _apply_filters(queryset, filters_data):
    module = _value(filters_data, "module")
    if module:
        queryset = queryset.filter(module=module)

    user = _value(filters_data, "user")
    if user:
        try:
            uuid.UUID(str(user))
            queryset = queryset.filter(user_id=user)
        except ValueError:
            queryset = queryset.none()

    action = _value(filters_data, "action")
    if action:
        queryset = queryset.filter(action=action)

    record_type = _value(filters_data, "record_type")
    if record_type:
        queryset = queryset.filter(record_type=record_type)

    record_id = _value(filters_data, "record_id")
    if record_id:
        try:
            uuid.UUID(str(record_id))
            queryset = queryset.filter(record_id=record_id)
        except ValueError:
            queryset = queryset.none()

    date_from = _value(filters_data, "date_from")
    if date_from:
        queryset = queryset.filter(timestamp__date__gte=date_from)

    date_to = _value(filters_data, "date_to")
    if date_to:
        queryset = queryset.filter(timestamp__date__lte=date_to)

    return queryset


def get_audit_logs(filters_data=None):
    queryset = AuditLog.objects.select_related("user").all()
    queryset = _apply_filters(queryset, filters_data)
    return queryset.order_by("-timestamp", "-created_at")


def get_audit_summary(filters_data=None):
    queryset = _apply_filters(AuditLog.objects.all(), filters_data)
    summary = queryset.aggregate(
        total=Count("id"),
        created=Count("id", filter=Q(action=AuditLogAction.CREATED)),
        updated=Count("id", filter=Q(action=AuditLogAction.UPDATED)),
        deleted=Count("id", filter=Q(action=AuditLogAction.DELETED)),
    )
    return {
        "total": summary["total"] or 0,
        "created": summary["created"] or 0,
        "updated": summary["updated"] or 0,
        "deleted": summary["deleted"] or 0,
    }