from django.contrib.auth import get_user_model
from django_filters import rest_framework as filters

from .models import AuditLog


class AuditLogFilterSet(filters.FilterSet):
    user = filters.ModelChoiceFilter(queryset=get_user_model().objects.all())
    module = filters.CharFilter(field_name="module")
    action = filters.CharFilter(field_name="action")
    record_type = filters.CharFilter(field_name="record_type")
    record_id = filters.UUIDFilter(field_name="record_id")
    date_from = filters.DateFilter(method="filter_date_from")
    date_to = filters.DateFilter(method="filter_date_to")

    class Meta:
        model = AuditLog
        fields = ["module", "user", "action", "record_type", "record_id", "date_from", "date_to"]

    def filter_date_from(self, queryset, name, value):
        return queryset.filter(timestamp__date__gte=value)

    def filter_date_to(self, queryset, name, value):
        return queryset.filter(timestamp__date__lte=value)