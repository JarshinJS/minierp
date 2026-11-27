"""
urls.py for the Dashboard app.

This module contains the urls logic for the Dashboard functionality.
"""
# pyrefly: ignore [missing-import]
from django.urls import path

from . import views
from core.views import FrontendPageView

app_name = "dashboard"

urlpatterns = [
    # Page served by the Next.js frontend; the name stays for {% url %} links.
    path("", FrontendPageView.as_view(), name="home"),
    path("system-status/", views.SystemStatusView.as_view(), name="system_status"),
    path("alerts-menu/", views.DashboardAlertsMenuView.as_view(), name="alerts_menu"),
]
