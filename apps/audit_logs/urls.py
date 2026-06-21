"""
urls.py for the Audit_logs app.

This module contains the urls logic for the Audit_logs functionality.
"""
from django.urls import path
from . import views

app_name = "audit_logs"

urlpatterns = [
    path("", views.AuditLogListView.as_view(), name="list"),
    path("api/", views.AuditLogListAPIView.as_view(), name="api-list"),
]
