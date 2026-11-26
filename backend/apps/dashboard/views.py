"""
views.py for the Dashboard app.

This module contains the views logic for the Dashboard functionality.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
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

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, *args, **kwargs):
        return Response(get_dashboard_summary())

class SystemStatusView(View):
    def get(self, request, *args, **kwargs):
        try:
            connection.ensure_connection()
            is_ok = True
        except Exception:
            is_ok = False

        return render(request, "dashboard/partials/system_status.html", {
            "is_ok": is_ok,
            "message": "All systems operational" if is_ok else "System degraded",
        })


class DashboardAlertsMenuView(LoginRequiredMixin, View):
    """Header bell dropdown: live operational alerts from the alert service."""

    def get(self, request, *args, **kwargs):
        from apps.dashboard.services.alert_service import get_alert_summary_for_user

        summary = get_alert_summary_for_user(request.user)
        items = [
            {**item, "url": reverse(item["url_name"]) if item["can_open"] else None}
            for item in summary["items"]
        ]
        return render(request, "dashboard/partials/alerts_menu.html", {"items": items, "total": summary["total"]})
