from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("", include("apps.audit_logs.urls")),
    path("", RedirectView.as_view(pattern_name="accounts:login", permanent=False)),
]
