from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from .models import ProcurementTrigger


class TriggerDashboardView(LoginRequiredMixin, ListView):
	model = ProcurementTrigger
	template_name = "procurement/trigger_dashboard.html"
	context_object_name = "triggers"

	def get_queryset(self):
		return ProcurementTrigger.objects.select_related("product", "created_by").order_by("-created_at")

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		triggers = self.get_queryset()
		context["queued_count"] = triggers.filter(status="QUEUED").count()
		context["processing_count"] = triggers.filter(status="PROCESSING").count()
		context["completed_count"] = triggers.filter(status="COMPLETED").count()
		context["failed_count"] = triggers.filter(status="FAILED").count()
		return context
