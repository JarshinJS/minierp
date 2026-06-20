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
    path("rag-query/", views.DashboardRAGView.as_view(), name="rag_query"),
]
