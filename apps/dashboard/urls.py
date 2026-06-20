from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    path("summary-partial/", views.DashboardSummaryPartialView.as_view(), name="summary_partial"),
    path("sse-summary/", views.DashboardSSESummaryView.as_view(), name="sse_summary"),
]
