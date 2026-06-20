from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class InventoryHomeView(LoginRequiredMixin, TemplateView):
	template_name = "inventory/home.html"
