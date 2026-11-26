from rest_framework import viewsets, permissions
from apps.accounts.models import UserRole
from apps.accounts.permissions import DRFRolePermission, roles_for_module

from .models import BlockchainDocument, BlockchainAuditLog
from .serializers import BlockchainDocumentSerializer, BlockchainAuditLogSerializer


class BlockchainDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BlockchainDocument.objects.select_related("document").order_by("-created_at")
    serializer_class = BlockchainDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, DRFRolePermission]
    allowed_roles = roles_for_module("blockchain")  # matches BlockchainDocumentListView

    def get_queryset(self):
        qs = super().get_queryset()
        verified = self.request.query_params.get("verified")
        if verified is not None:
            qs = qs.filter(verified=verified.lower() == "true")
        return qs


class BlockchainAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BlockchainAuditLog.objects.select_related("created_by").order_by("-created_at")
    serializer_class = BlockchainAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, DRFRolePermission]
    # Ledger audit is narrower than the module (no Documentation Officer), as in the HTML view.
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.TRADE_MANAGER, UserRole.AUDITOR]

    def get_queryset(self):
        qs = super().get_queryset()
        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)
        return qs
