from django.urls import path

from . import views

app_name = "procurement"

urlpatterns = [
	path("trigger-dashboard/", views.TriggerDashboardView.as_view(), name="trigger_dashboard"),
]
