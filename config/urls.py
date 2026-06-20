from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from apps.dashboard.views import DashboardSummaryAPIView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("purchase/", include("apps.purchase.urls")),
    path("products/", include("apps.products.urls")),
    path("sales/", include("apps.sales.urls")),
    path("audit-logs/", include("apps.audit_logs.urls")),
    path("manufacturing/", include("apps.manufacturing.urls")),
    path("api/dashboard/summary", DashboardSummaryAPIView.as_view(), name="dashboard_api_summary"),
    path("", RedirectView.as_view(pattern_name="accounts:login", permanent=False)),
]
