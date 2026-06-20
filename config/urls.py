from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from django.views import View
from django.views.generic import RedirectView

from apps.dashboard.views import DashboardSummaryAPIView


class RootRedirectView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return redirect("accounts:login")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RootRedirectView.as_view(), name="root_redirect"),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("audit/", include("apps.audit_logs.urls")),
    path("audit-logs/", RedirectView.as_view(pattern_name="audit_logs:list", permanent=False)),
    path("products/", include("apps.products.urls")),
    path("purchase/", include("apps.purchase.urls")),
    path("sales/", include("apps.sales.urls")),
    path("manufacturing/", include("apps.manufacturing.urls")),
    path("procurement/", include("apps.procurement.urls")),
    path("users/", RedirectView.as_view(pattern_name="accounts:user_list", permanent=False)),
    path("bom/", RedirectView.as_view(pattern_name="manufacturing:bom_list", permanent=False)),
    path("login/", RedirectView.as_view(pattern_name="accounts:login", permanent=False)),
    path("signup/", RedirectView.as_view(pattern_name="accounts:signup", permanent=False)),
    path("logout/", RedirectView.as_view(pattern_name="accounts:logout", permanent=False)),
    path("api/dashboard/summary", DashboardSummaryAPIView.as_view(), name="dashboard_api_summary"),
]
