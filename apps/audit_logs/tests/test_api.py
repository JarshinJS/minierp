import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit_logs.models import AuditLogAction
from apps.audit_logs.services import log_event
from apps.audit_logs.tests.factories import UserFactory


class DummyRecord:
    audit_module = "sales"
    audit_record_type = "SalesOrder"

    def __init__(self, pk):
        self.pk = pk


@pytest.mark.django_db
class TestAuditLogAPI:
    def test_list_endpoint_requires_authentication(self):
        client = APIClient()
        response = client.get(reverse("audit_logs:api-list"))
        assert response.status_code in (401, 403)

    def test_list_endpoint_returns_filtered_results(self):
        user = UserFactory()
        other_user = UserFactory()

        record_one = DummyRecord(user.pk)
        record_two = DummyRecord(other_user.pk)

        log_event(user=user, module="sales", record=record_one, action=AuditLogAction.CREATED)
        log_event(user=other_user, module="inventory", record=record_two, action=AuditLogAction.DELETED)

        client = APIClient()
        client.force_login(user)

        response = client.get(reverse("audit_logs:api-list"), {"module": "sales", "action": AuditLogAction.CREATED})

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["module"] == "sales"