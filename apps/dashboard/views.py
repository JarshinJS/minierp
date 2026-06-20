from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .selectors import get_dashboard_summary
from apps.dashboard.services.dashboard_service import get_dashboard_data_for_user


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = get_dashboard_data_for_user(self.request.user)
        context.update(data)
        context["summary_partial_url"] = reverse("dashboard:summary_partial")
        return context


class DashboardRefreshView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/partials/dashboard_live.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = get_dashboard_data_for_user(self.request.user)
        context.update(data)
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

<<<<<<< HEAD

import json
import time
import hashlib
from django.http import StreamingHttpResponse
from django.template.loader import render_to_string
from django.views import View

class DashboardSSESummaryView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        def event_stream():
            try:
                last_hash = None
                while True:
                    summary_data = get_dashboard_summary()
                    # Hash of data to detect change
                    serialized = json.dumps(summary_data, default=str)
                    current_hash = hashlib.md5(serialized.encode("utf-8")).hexdigest()

                    if current_hash != last_hash:
                        last_hash = current_hash
                        html_content = render_to_string(
                            "dashboard/partials/dashboard_summary.html",
                            {"summary": summary_data},
                            request=request
                        )
                        single_line_html = html_content.replace("\n", " ").replace("\r", " ")
                        yield f"event: message\ndata: {single_line_html}\n\n"
                    else:
                        yield ": keepalive\n\n"

                    time.sleep(1)
            except (GeneratorExit, ConnectionResetError, BrokenPipeError):
                pass

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
=======
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

>>>>>>> rag-integration-ui
