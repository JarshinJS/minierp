from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from django.views import View
from django.views.generic import RedirectView



class RootRedirectView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return redirect(settings.LOGIN_URL)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls", namespace="api")),
    path("", RootRedirectView.as_view(), name="root_redirect"),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("audit/", include("apps.audit_logs.urls")),
    path("audit-logs/", RedirectView.as_view(pattern_name="audit_logs:list", permanent=False)),
    path("products/", include("apps.products.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("purchase/", include("apps.purchase.urls")),
    path("sales/", include("apps.sales.urls")),
    path("manufacturing/", include("apps.manufacturing.urls")),
    path("procurement/", include("apps.procurement.urls")),
    path("delivery/", include("apps.delivery.urls")),
    path("reports/", include("apps.reports.urls")),
    path("trade/", include("apps.foreign_trade.urls")),
    path("blockchain/", include("apps.blockchain.urls")),
    path("users/", RedirectView.as_view(pattern_name="accounts:user_list", permanent=False)),
    path("bom/", RedirectView.as_view(pattern_name="manufacturing:bom_list", permanent=False)),
]
