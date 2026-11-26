"""
views.py for the Audit_logs app.

This module contains the views logic for the Audit_logs functionality.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import ListView
from rest_framework.generics import ListAPIView

from .filters import AuditLogFilterSet
from .models import AuditLog
from .selectors import get_audit_logs, get_audit_summary
from .serializers import AuditLogSerializer
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import DRFRolePermission, RoleRequiredMixin, roles_for_module

MODULE_ROLES = roles_for_module("audit_logs")


class AuditLogListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
	allowed_roles = MODULE_ROLES
	model = AuditLog
	template_name = "audit_logs/audit_list.html"
	context_object_name = "audit_logs"
	paginate_by = 10

	def get_queryset(self):
		return get_audit_logs(self.request.GET)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["summary"] = get_audit_summary()
		context["filters"] = self.request.GET
		context["action_choices"] = AuditLog._meta.get_field("action").choices
		context["module_choices"] = AuditLog.objects.order_by("module").values_list("module", flat=True).distinct()
		context["record_type_choices"] = AuditLog.objects.order_by("record_type").values_list("record_type", flat=True).distinct()
		context["user_choices"] = get_user_model().objects.filter(audit_logs__isnull=False).distinct().order_by("full_name")
		return context

	def render_to_response(self, context, **response_kwargs):
		if getattr(self.request, "htmx", False):
			return render(self.request, "audit_logs/partials/audit_table.html", context)
		return super().render_to_response(context, **response_kwargs)


class AuditLogListAPIView(ListAPIView):
	permission_classes = [IsAuthenticated, DRFRolePermission]
	allowed_roles = MODULE_ROLES
	serializer_class = AuditLogSerializer
	queryset = AuditLog.objects.select_related("user").all().order_by("-timestamp", "-created_at")
	filterset_class = AuditLogFilterSet
