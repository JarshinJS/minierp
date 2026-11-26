"""
urls.py for the Procurement app.

This module contains the urls logic for the Procurement functionality.
"""
from django.urls import path

from . import views

app_name = "procurement"

urlpatterns = [
	path("trigger-dashboard/", views.TriggerDashboardView.as_view(), name="trigger_dashboard"),
]
