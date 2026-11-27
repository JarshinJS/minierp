"""
views.py for the Dashboard app.

The dashboard page itself is served by the Next.js frontend (data from
dashboard.api). What remains here are the JSON summary endpoint and the two
header widgets (alerts menu, system status) used by the remaining Django pages.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from apps.accounts.models import UserRole
from apps.accounts.permissions import DRFRolePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from django.db import connection

from .selectors import get_dashboard_summary


class DashboardSummaryAPIView(APIView):
    """Company-wide aggregate of every module (CEO KPIs, full activity feed): owners only."""
    permission_classes = [DRFRolePermission]
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER]

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
