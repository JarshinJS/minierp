from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsHomeView.as_view(), name="home"),
    path("sales/", views.ExportSalesReportView.as_view(), name="sales"),
    path("purchase/", views.ExportPurchaseReportView.as_view(), name="purchase"),
    path("manufacturing/", views.ExportManufacturingReportView.as_view(), name="manufacturing"),
    path("inventory/", views.ExportInventoryReportView.as_view(), name="inventory"),
]
