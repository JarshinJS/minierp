"""
All REST endpoints, mounted at /api/ (namespace "api").

The Next.js frontend proxies /api/* to this backend. OpenAPI schema: /api/schema/,
interactive docs: /api/docs/ (both require login).
"""
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.accounts import api as accounts_api
from apps.audit_logs.views import AuditLogListAPIView
from apps.blockchain import api_views as blockchain_api
from apps.dashboard.api import DashboardAlertsAPIView, DashboardAnalyticsAPIView, DashboardOverviewAPIView
from apps.dashboard.views import DashboardSummaryAPIView
from apps.delivery.api import DeliveryNoteViewSet
from apps.foreign_trade import api_views as trade_api
from apps.inventory import api as inventory_api
from apps.manufacturing import views as manufacturing_views
from apps.procurement.api import ProcurementTriggerViewSet
from apps.products import views as products_views
from apps.purchase import views as purchase_views
from apps.reports import api as reports_api
from apps.sales import views as sales_views
from core.api_views import VoiceAssistantAPIView, VoiceExtractAPIView

app_name = "api"

router = DefaultRouter()
router.include_root_view = False

# Accounts
router.register("users", accounts_api.UserViewSet, basename="user")
# Catalogue & operations
router.register("products", products_views.ProductViewSet, basename="product")
router.register("categories", products_views.CategoryViewSet, basename="category")
router.register("vendors", purchase_views.VendorViewSet, basename="vendor")
router.register("purchase-orders", purchase_views.PurchaseOrderViewSet, basename="purchase-order")
router.register("sales-orders", sales_views.SalesOrderViewSet, basename="sales-order")
router.register("deliveries", DeliveryNoteViewSet, basename="delivery")
router.register("procurement/triggers", ProcurementTriggerViewSet, basename="procurement-trigger")
# Manufacturing
router.register("work-centers", manufacturing_views.WorkCenterViewSet, basename="work-center")
router.register("boms", manufacturing_views.BOMViewSet, basename="bom")
router.register("manufacturing-orders", manufacturing_views.ManufacturingOrderViewSet, basename="manufacturing-order")
router.register("work-orders", manufacturing_views.WorkOrderViewSet, basename="work-order")
# Foreign trade
router.register("trade/exports", trade_api.ExportOrderViewSet, basename="export-order")
router.register("trade/imports", trade_api.ImportOrderViewSet, basename="import-order")
router.register("trade/documents", trade_api.TradeDocumentViewSet, basename="trade-document")
router.register("trade/shipments", trade_api.ShipmentViewSet, basename="shipment")
router.register("trade/customers", trade_api.TradeCustomerViewSet, basename="trade-customer")
router.register("trade/suppliers", trade_api.TradeSupplierViewSet, basename="trade-supplier")
router.register("trade/countries", trade_api.CountryViewSet, basename="country")
router.register("trade/currencies", trade_api.CurrencyViewSet, basename="currency")
router.register("trade/incoterms", trade_api.IncotermViewSet, basename="incoterm")
# Blockchain
router.register("blockchain/documents", blockchain_api.BlockchainDocumentViewSet, basename="blockchain-document")
router.register("blockchain/audit-logs", blockchain_api.BlockchainAuditLogViewSet, basename="blockchain-audit-log")

urlpatterns = [
    # Auth
    path("auth/csrf/", accounts_api.CSRFTokenAPIView.as_view(), name="auth-csrf"),
    path("auth/login/", accounts_api.LoginAPIView.as_view(), name="auth-login"),
    path("auth/logout/", accounts_api.LogoutAPIView.as_view(), name="auth-logout"),
    path("auth/me/", accounts_api.CurrentUserAPIView.as_view(), name="auth-me"),
    path("auth/signup/", accounts_api.SignupAPIView.as_view(), name="auth-signup"),
    path("auth/signup/verify/", accounts_api.SignupVerifyAPIView.as_view(), name="auth-signup-verify"),
    path("auth/signup/resend/", accounts_api.SignupResendAPIView.as_view(), name="auth-signup-resend"),
    # Inventory
    path("inventory/stock/", inventory_api.StockLevelListAPIView.as_view(), name="inventory-stock"),
    path("inventory/stock/summary/", inventory_api.InventoryStatsAPIView.as_view(), name="inventory-stock-summary"),
    path("inventory/ledger/", inventory_api.LedgerEntryListAPIView.as_view(), name="inventory-ledger"),
    path("inventory/adjustments/", inventory_api.StockAdjustmentAPIView.as_view(), name="inventory-adjustments"),
    # Reports
    path("reports/", reports_api.ReportOverviewAPIView.as_view(), name="report-overview"),
    path("reports/<str:category>/<str:report_type>/", reports_api.ReportAPIView.as_view(), name="report-detail"),
    # Dashboard
    path("dashboard/", DashboardOverviewAPIView.as_view(), name="dashboard-overview"),
    path("dashboard/summary/", DashboardSummaryAPIView.as_view(), name="dashboard-summary"),
    path("dashboard/analytics/", DashboardAnalyticsAPIView.as_view(), name="dashboard-analytics"),
    path("dashboard/alerts/", DashboardAlertsAPIView.as_view(), name="dashboard-alerts"),
    # Audit trail
    path("audit-logs/", AuditLogListAPIView.as_view(), name="audit-log-list"),
    # Voice assistant
    path("voice/extract/", VoiceExtractAPIView.as_view(), name="voice-extract"),
    path("voice/assistant/", VoiceAssistantAPIView.as_view(), name="voice-assistant"),
    # OpenAPI
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    *router.urls,
]
