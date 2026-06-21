from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView

from apps.accounts.permissions import RoleRequiredMixin
from .models import BlockchainDocument, BlockchainAuditLog
from .services.web3_service import get_web3_service


class BlockchainDashboardView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    template_name = "blockchain/dashboard.html"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "AUDITOR"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        web3_svc = get_web3_service()
        ctx["network_info"] = web3_svc.get_network_info()
        ctx["is_connected"] = web3_svc.is_connected()
        ctx["total_documents"] = BlockchainDocument.objects.count()
        ctx["verified_documents"] = BlockchainDocument.objects.filter(verified=True).count()
        ctx["total_audit_logs"] = BlockchainAuditLog.objects.count()
        ctx["recent_documents"] = BlockchainDocument.objects.select_related("document").order_by("-created_at")[:5]
        ctx["recent_audit_logs"] = BlockchainAuditLog.objects.select_related("created_by").order_by("-created_at")[:10]
        return ctx


class BlockchainAuditListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = BlockchainAuditLog
    template_name = "blockchain/audit_log_list.html"
    context_object_name = "audit_logs"
    paginate_by = 10
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "AUDITOR"]

    def get_queryset(self):
        qs = BlockchainAuditLog.objects.select_related("created_by").order_by("-created_at")
        event_filter = self.request.GET.get("event_type", "")
        if event_filter:
            qs = qs.filter(event_type=event_filter)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["event_types"] = BlockchainAuditLog.EventType.choices
        ctx["current_event_type"] = self.request.GET.get("event_type", "")
        return ctx


class BlockchainDocumentListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = BlockchainDocument
    template_name = "blockchain/document_list.html"
    context_object_name = "blockchain_docs"
    paginate_by = 10
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "AUDITOR"]

    def get_queryset(self):
        qs = BlockchainDocument.objects.select_related("document").order_by("-created_at")
        verified_filter = self.request.GET.get("verified", "")
        if verified_filter == "true":
            qs = qs.filter(verified=True)
        elif verified_filter == "false":
            qs = qs.filter(verified=False)
        return qs
