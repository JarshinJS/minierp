from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "blockchain"

urlpatterns = [
    path("", views.BlockchainDashboardView.as_view(), name="dashboard"),
    path("audit-logs/", views.BlockchainAuditListView.as_view(), name="audit_log_list"),
    path("documents/", views.BlockchainDocumentListView.as_view(), name="document_list"),
]

# API Router
try:
    from . import api_views
    router = DefaultRouter()
    router.register("docs", api_views.BlockchainDocumentViewSet, basename="api_blockchain_doc")
    router.register("audit", api_views.BlockchainAuditLogViewSet, basename="api_blockchain_audit")
    urlpatterns.append(path("api/", include(router.urls)))
except (ImportError, AttributeError):
    pass
