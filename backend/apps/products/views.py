"""
views.py for the Products app.

REST API for products and categories. The product pages are served by the
Next.js frontend.
"""
from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core.exceptions import DomainError
from .models import Product, Category
from .serializers import ProductSerializer, CategorySerializer
from . import services
from . import selectors
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import OpenApiParameter, extend_schema
from apps.accounts.permissions import DRFRolePermission, roles_for_capability, roles_for_module

MODULE_ROLES = roles_for_module("products")
# Everyone with the module may read the catalogue; only these roles may change it.
WRITE_ROLES = roles_for_capability("products.write")

# ==============================================================================
# DRF API ViewSets
# ==============================================================================

class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DRFRolePermission]
    read_roles = MODULE_ROLES
    allowed_roles = WRITE_ROLES
    # Records are cancelled/deactivated via services, never hard-deleted through the API.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    queryset = Product.objects.all().select_related("category", "default_vendor", "default_bom")
    serializer_class = ProductSerializer

    @extend_schema(parameters=[
        OpenApiParameter("search", str, description="Name or SKU"),
        OpenApiParameter("category", str, description="Category id"),
        OpenApiParameter("status", str, enum=["active", "inactive"]),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if self.action != "list":
            return super().get_queryset()
        params = self.request.query_params
        return selectors.get_products(
            search_query=params.get("search", "").strip() or None,
            category_id=params.get("category") or None,
            is_active={"active": True, "inactive": False}.get(params.get("status")),
        ).order_by("name")

    @extend_schema(request=None, responses=ProductSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Hide the product from new sales and purchase orders."""
        product = self.get_object()
        services.deactivate_product(product)
        product.refresh_from_db()
        return Response(ProductSerializer(product).data)

    def perform_create(self, serializer):
        try:
            # Delegate model creation strictly to the Service layer
            product = services.create_product(
                name=serializer.validated_data["name"],
                sku=serializer.validated_data["sku"],
                category=serializer.validated_data["category"],
                cost_price=serializer.validated_data["cost_price"],
                selling_price=serializer.validated_data["selling_price"],
                unit_of_measure=serializer.validated_data["unit_of_measure"],
                procure_on_demand=serializer.validated_data.get("procure_on_demand", False),
                procurement_type=serializer.validated_data.get("procurement_type", "PURCHASE"),
                default_vendor=serializer.validated_data.get("default_vendor"),
                default_bom=serializer.validated_data.get("default_bom"),
                is_active=serializer.validated_data.get("is_active", True)
            )
            serializer.instance = product
        except DomainError as e:
            raise serializers.ValidationError({"detail": e.message})

    def perform_update(self, serializer):
        try:
            # Delegate model updates strictly to the Service layer
            product = services.update_product(serializer.instance, **serializer.validated_data)
            serializer.instance = product
        except DomainError as e:
            raise serializers.ValidationError({"detail": e.message})

    @action(detail=True, methods=["get"])
    def stock(self, request, pk=None):
        """
        Stock Endpoint: Fetch read-only stock levels using selectors.
        """
        product = self.get_object()
        data = selectors.get_product_stock(product)
        return Response(data)


class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DRFRolePermission]
    read_roles = MODULE_ROLES
    allowed_roles = WRITE_ROLES
    # Records are cancelled/deactivated via services, never hard-deleted through the API.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
