"""REST API for inventory: stock levels, ledger and manual adjustments."""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import DRFRolePermission, roles_for_capability, roles_for_module
from . import services
from .models import LedgerEntryType
from .selectors import get_inventory_stats, get_ledger_entries, get_stock_levels
from .serializers import (
    InventoryStatsSerializer, LedgerEntrySerializer, StockAdjustmentSerializer, StockLevelSerializer,
)

MODULE_ROLES = roles_for_module("inventory")


class _InventoryAccess:
    permission_classes = [IsAuthenticated, DRFRolePermission]
    allowed_roles = MODULE_ROLES


@extend_schema(parameters=[
    OpenApiParameter("search", str, description="Matches product name or SKU"),
    OpenApiParameter("category", str, description="Category id"),
    OpenApiParameter("stock", str, enum=["low_stock", "out_of_stock"]),
])
class StockLevelListAPIView(_InventoryAccess, generics.ListAPIView):
    """Current stock per active product."""
    serializer_class = StockLevelSerializer

    def get_queryset(self):
        params = self.request.query_params
        return get_stock_levels(
            search=params.get("search", "").strip(),
            category_id=params.get("category", ""),
            stock_filter=params.get("stock", ""),
        )


class InventoryStatsAPIView(_InventoryAccess, APIView):
    @extend_schema(responses=InventoryStatsSerializer)
    def get(self, request):
        return Response(InventoryStatsSerializer(get_inventory_stats()).data)


@extend_schema(parameters=[
    OpenApiParameter("product", str, description="Product id"),
    OpenApiParameter("entry_type", str, enum=LedgerEntryType.values),
    OpenApiParameter("reference", str),
])
class LedgerEntryListAPIView(_InventoryAccess, generics.ListAPIView):
    """Stock movement ledger, newest first."""
    serializer_class = LedgerEntrySerializer

    def get_queryset(self):
        params = self.request.query_params
        return get_ledger_entries({
            "product": params.get("product"),
            "entry_type": params.get("entry_type"),
            "reference": params.get("reference", "").strip(),
        })


class StockAdjustmentAPIView(_InventoryAccess, APIView):
    # Viewing stock is module-wide; manual adjustments are inventory managers only.
    allowed_roles = roles_for_capability("inventory.adjust")

    @extend_schema(request=StockAdjustmentSerializer, responses={201: StockLevelSerializer})
    def post(self, request):
        """Manually receive or issue stock; returns the product's updated stock level."""
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        product = data["product"]
        if data["adjustment_type"] == LedgerEntryType.RECEIPT:
            services.receive_stock(product, data["quantity"], data["reference"] or "Manual Adjustment (Receipt)")
        else:
            services.issue_stock(product, data["quantity"], data["reference"] or "Manual Adjustment (Issue)")
        updated = get_stock_levels(active_only=False).get(pk=product.pk)
        return Response(StockLevelSerializer(updated).data, status=status.HTTP_201_CREATED)
