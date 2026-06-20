from django.urls import path
from . import views

app_name = "audit_logs"

urlpatterns = [
	path("audit-logs/", views.AuditLogListView.as_view(), name="list"),
	path("api/audit-logs/", views.AuditLogListAPIView.as_view(), name="api-list"),
]
