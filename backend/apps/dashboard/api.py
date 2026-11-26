# pyrefly: ignore [missing-import]
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from apps.dashboard.services import analytics_service

class DashboardAnalyticsAPIView(APIView):
    """
    API endpoint that returns real-time business metrics and transaction trends
    for visualization using Chart.js on the dashboard.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, *args, **kwargs):
        return Response({
            "sales_trend": analytics_service.get_sales_trend(),
            "purchase_trend": analytics_service.get_purchase_trend(),
            "manufacturing_progress": analytics_service.get_manufacturing_progress(),
            "inventory_movement": analytics_service.get_inventory_movement(),
        })


class DashboardAlertsAPIView(APIView):
    """Operational alert counts for the header bell (same data as the HTML dropdown)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=inline_serializer("DashboardAlerts", {
        "total": serializers.IntegerField(),
        "items": inline_serializer("DashboardAlertItem", {
            "key": serializers.CharField(), "label": serializers.CharField(),
            "count": serializers.IntegerField(), "tone": serializers.CharField(),
            "module": serializers.CharField(),
            "can_open": serializers.BooleanField(help_text="Whether the user's role may open this module"),
        }, many=True),
    }))
    def get(self, request, *args, **kwargs):
        from apps.dashboard.services.alert_service import get_alert_summary_for_user

        summary = get_alert_summary_for_user(request.user)
        items = [{k: v for k, v in item.items() if k != "url_name"} for item in summary["items"]]
        return Response({"total": summary["total"], "items": items})


DashboardOverviewSerializer = inline_serializer("DashboardOverview", {
    "allowed_modules": serializers.ListField(child=serializers.CharField()),
    "widgets": inline_serializer("DashboardWidget", {
        "title": serializers.CharField(),
        "class_name": serializers.CharField(help_text="e.g. SalesWidget; decides how `data` is shown"),
        "data": serializers.DictField(),
    }, many=True),
    "intelligence_alerts": inline_serializer("DashboardInsight", {
        "type": serializers.ChoiceField(choices=["warning", "success", "info"]),
        "text": serializers.CharField(),
    }, many=True),
    "manufacturing_progress": inline_serializer("DashboardProduction", {
        "id": serializers.CharField(), "number": serializers.CharField(), "product": serializers.CharField(),
        "status": serializers.CharField(), "status_label": serializers.CharField(),
        "percentage": serializers.IntegerField(), "detail": serializers.CharField(),
    }, many=True),
    "recent_activities": inline_serializer("DashboardActivity", {
        "id": serializers.CharField(), "timestamp": serializers.DateTimeField(),
        "user": serializers.CharField(allow_null=True), "module": serializers.CharField(),
        "record_type": serializers.CharField(), "action": serializers.CharField(),
    }, many=True),
    "low_stock": inline_serializer("DashboardLowStock", {
        "sku": serializers.CharField(), "name": serializers.CharField(),
        "available_qty": serializers.FloatField(),
    }, many=True),
    "pending_deliveries": inline_serializer("DashboardPendingDelivery", {
        "id": serializers.CharField(), "delivery_number": serializers.CharField(),
        "order_number": serializers.CharField(), "customer_name": serializers.CharField(),
        "created_at": serializers.CharField(),
    }, many=True),
})


class DashboardOverviewAPIView(APIView):
    """
    Everything the dashboard page shows, filtered to the user's role: KPI widgets,
    insights, production progress, recent activity, low stock and pending deliveries.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DashboardOverviewSerializer)
    def get(self, request, *args, **kwargs):
        from apps.dashboard.services.dashboard_service import get_dashboard_data_for_user

        data = get_dashboard_data_for_user(request.user)
        modules = set(data["allowed_modules"])
        alerts = data["alerts"]
        return Response({
            "allowed_modules": data["allowed_modules"],
            "widgets": [{k: w[k] for k in ("title", "class_name", "data")} for w in data["widgets"]],
            "intelligence_alerts": data["intelligence_alerts"],
            "manufacturing_progress": data["manufacturing_progress"] if "manufacturing" in modules else [],
            "recent_activities": data["recent_activities"][:6],
            "low_stock": alerts.get("low_stock", [])[:6] if modules & {"inventory", "products"} else [],
            "pending_deliveries": alerts.get("pending_deliveries", [])[:6] if "delivery" in modules else [],
        })
