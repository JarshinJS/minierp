from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "foreign_trade"

urlpatterns = [
    # === Export Orders ===
    path("exports/", views.ExportOrderListView.as_view(), name="export_order_list"),
    path("exports/create/", views.ExportOrderCreateView.as_view(), name="export_order_create"),
    path("exports/<uuid:pk>/", views.ExportOrderDetailView.as_view(), name="export_order_detail"),
    path("exports/<uuid:pk>/edit/", views.ExportOrderUpdateView.as_view(), name="export_order_edit"),
    path("exports/<uuid:pk>/confirm/", views.ExportOrderConfirmView.as_view(), name="export_order_confirm"),
    path("exports/<uuid:pk>/ship/", views.ExportOrderShipView.as_view(), name="export_order_ship"),
    path("exports/<uuid:pk>/deliver/", views.ExportOrderDeliverView.as_view(), name="export_order_deliver"),
    path("exports/<uuid:pk>/cancel/", views.ExportOrderCancelView.as_view(), name="export_order_cancel"),
    path("exports/<uuid:pk>/invoice/", views.ExportInvoiceCreateView.as_view(), name="export_invoice_create"),

    # === Import Orders ===
    path("imports/", views.ImportOrderListView.as_view(), name="import_order_list"),
    path("imports/create/", views.ImportOrderCreateView.as_view(), name="import_order_create"),
    path("imports/<uuid:pk>/", views.ImportOrderDetailView.as_view(), name="import_order_detail"),
    path("imports/<uuid:pk>/edit/", views.ImportOrderUpdateView.as_view(), name="import_order_edit"),
    path("imports/<uuid:pk>/confirm/", views.ImportOrderConfirmView.as_view(), name="import_order_confirm"),
    path("imports/<uuid:pk>/transit/", views.ImportOrderTransitView.as_view(), name="import_order_transit"),
    path("imports/<uuid:pk>/customs/", views.ImportOrderCustomsView.as_view(), name="import_order_customs"),
    path("imports/<uuid:pk>/receive/", views.ImportOrderReceiveView.as_view(), name="import_order_receive"),
    path("imports/<uuid:pk>/cancel/", views.ImportOrderCancelView.as_view(), name="import_order_cancel"),

    # === Documents ===
    path("documents/<str:order_type>/<uuid:pk>/upload/", views.DocumentUploadView.as_view(), name="document_upload"),
    path("documents/<str:order_type>/<uuid:pk>/history/", views.DocumentHistoryView.as_view(), name="document_history"),
    path("documents/<uuid:pk>/verify/", views.DocumentVerifyView.as_view(), name="document_verify"),

    # === Shipments ===
    path("shipments/", views.ShipmentListView.as_view(), name="shipment_list"),
    path("shipments/<uuid:pk>/", views.ShipmentDetailView.as_view(), name="shipment_detail"),

    # === Customers & Suppliers ===
    path("customers/", views.TradeCustomerListView.as_view(), name="customer_list"),
    path("customers/create/", views.TradeCustomerCreateView.as_view(), name="customer_create"),
    path("suppliers/", views.TradeSupplierListView.as_view(), name="supplier_list"),
    path("suppliers/create/", views.TradeSupplierCreateView.as_view(), name="supplier_create"),
]

# API Router — will be added in Phase 5
try:
    from . import api_views
    router = DefaultRouter()
    router.register("exports", api_views.ExportOrderViewSet, basename="api_export")
    router.register("imports", api_views.ImportOrderViewSet, basename="api_import")
    router.register("documents", api_views.TradeDocumentViewSet, basename="api_document")
    router.register("shipments", api_views.ShipmentViewSet, basename="api_shipment")
    urlpatterns.append(path("api/", include(router.urls)))
except (ImportError, AttributeError):
    pass
