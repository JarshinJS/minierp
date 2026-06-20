# pyrefly: ignore [missing-import]
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.dashboard.services import analytics_service

class DashboardAnalyticsAPIView(APIView):
    """
    API endpoint that returns real-time business metrics and transaction trends
    for visualization using Chart.js on the dashboard.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({
            "sales_trend": analytics_service.get_sales_trend(),
            "purchase_trend": analytics_service.get_purchase_trend(),
            "manufacturing_progress": analytics_service.get_manufacturing_progress(),
            "inventory_movement": analytics_service.get_inventory_movement(),
        })
