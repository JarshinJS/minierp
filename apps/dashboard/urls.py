from django.urls import path

from . import views
from .api import DashboardAnalyticsAPIView

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    path("refresh/", views.DashboardRefreshView.as_view(), name="refresh"),
    path("analytics/", DashboardAnalyticsAPIView.as_view(), name="analytics"),
    path("summary-partial/", views.DashboardSummaryPartialView.as_view(), name="summary_partial"),
    path("sse-summary/", views.DashboardSSESummaryView.as_view(), name="sse_summary"),
    path("run-demo/", views.RunSmartDemoView.as_view(), name="run_demo"),
]
