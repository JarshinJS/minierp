from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .selectors import get_dashboard_summary


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary_partial_url"] = reverse("dashboard:summary_partial")
        return context


class DashboardSummaryPartialView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/partials/dashboard_summary.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary"] = get_dashboard_summary()
        return context


class DashboardSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(get_dashboard_summary())

from django.views import View
from apps.inventory.services import InventoryRAGService

class DashboardRAGView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        query = request.POST.get("query", "").strip()
        if not query:
            return render(request, "dashboard/partials/rag_message.html", {"user_query": "", "bot_response": "Please enter a query."})
        
        try:
            rag_service = InventoryRAGService()
            # If no model configured, it handles failures gracefully inside generate()
            answer = rag_service.generate(user_instruction=query)
        except Exception as e:
            answer = "Sorry, I encountered an error connecting to the AI."
            
        return render(request, "dashboard/partials/rag_message.html", {
            "user_query": query,
            "bot_response": answer
        })

