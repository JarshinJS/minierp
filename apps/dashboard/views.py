"""
views.py for the Dashboard app.

This module contains the views logic for the Dashboard functionality.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import connection
from django.http import HttpResponse

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


class RunSmartDemoView(LoginRequiredMixin, APIView):
    def post(self, request, *args, **kwargs):
        from django.core.management import call_command
        try:
            call_command("generate_sample_data")
            return Response({"status": "success", "message": "Smart Demo Scenario executed successfully! UI will now reflect real-time business activity."})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)

class SystemStatusView(View):
    def get(self, request, *args, **kwargs):
        try:
            connection.ensure_connection()
            is_ok = True
        except Exception:
            is_ok = False
            
        color = "emerald" if is_ok else "red"
        message = "All Systems Operational" if is_ok else "System Degraded"
        
        url = reverse('dashboard:system_status')
        html = f'''
            <div class="flex items-center gap-2.5" hx-get="{url}" hx-trigger="every 30s" hx-swap="outerHTML">
                <!-- System status indicator -->
                <span class="relative flex h-2.5 w-2.5">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-{color}-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-{color}-500"></span>
                </span>
                <span class="text-xs font-semibold text-slate-500 tracking-wide">{message}</span>
            </div>
        '''
        return HttpResponse(html)
