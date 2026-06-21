"""
views.py for the Audit_logs app.

This module contains the views logic for the Audit_logs functionality.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import ListView
from rest_framework.generics import ListAPIView

from .filters import AuditLogFilterSet
from .models import AuditLog
from .selectors import get_audit_logs, get_audit_summary
from .serializers import AuditLogSerializer


class AuditLogListView(LoginRequiredMixin, ListView):
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
		return context

	def render_to_response(self, context, **response_kwargs):
		if getattr(self.request, "htmx", False):
			return render(self.request, "audit_logs/partials/audit_table.html", context)
		return super().render_to_response(context, **response_kwargs)


class AuditLogListAPIView(ListAPIView):
	serializer_class = AuditLogSerializer
	queryset = AuditLog.objects.select_related("user").all().order_by("-timestamp", "-created_at")
	filterset_class = AuditLogFilterSet
