"""
urls.py for the Blockchain app.

This module contains the urls logic for the Blockchain functionality.
"""
from django.urls import path
from . import views

app_name = "blockchain"

urlpatterns = [
    path("", views.BlockchainDashboardView.as_view(), name="dashboard"),
    path("audit-logs/", views.BlockchainAuditListView.as_view(), name="audit_log_list"),
    path("documents/", views.BlockchainDocumentListView.as_view(), name="document_list"),
]
