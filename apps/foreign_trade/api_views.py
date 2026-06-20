from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import DRFRolePermission
from core.exceptions import DomainError, WorkflowError
from apps.blockchain.services.verification_service import verify_document

from .models import ExportOrder, ImportOrder, TradeDocument, Shipment
from .serializers import (
    ExportOrderSerializer, ImportOrderSerializer,
    TradeDocumentSerializer, ShipmentSerializer,
)
from . import services


class ExportOrderViewSet(viewsets.ModelViewSet):
    queryset = ExportOrder.objects.select_related("customer", "country", "currency").prefetch_related("lines").order_by("-created_at")
    serializer_class = ExportOrderSerializer
    permission_classes = [permissions.IsAuthenticated, DRFRolePermission]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        lines_data = serializer.validated_data.pop("lines_data", [])
        if not lines_data:
            return Response({"detail": "At least one line item is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = services.create_export_order(
                customer=serializer.validated_data["customer"],
                country=serializer.validated_data["country"],
                currency=serializer.validated_data["currency"],
                lines_data=lines_data,
                created_by=request.user,
                **serializer.validated_data
            )
            return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)
        except DomainError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = self.get_object()
        try:
            order = services.confirm_export_order(order, user=request.user)
            return Response(self.get_serializer(order).data)
        except (DomainError, WorkflowError) as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def ship(self, request, pk=None):
        order = self.get_object()
        try:
            order, shipment = services.ship_export_order(order, request.data, user=request.user)
            return Response({
                "order": self.get_serializer(order).data,
                "shipment": ShipmentSerializer(shipment).data
            })
        except (DomainError, WorkflowError) as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)


class ImportOrderViewSet(viewsets.ModelViewSet):
    queryset = ImportOrder.objects.select_related("supplier", "country", "currency").prefetch_related("lines").order_by("-created_at")
    serializer_class = ImportOrderSerializer
    permission_classes = [permissions.IsAuthenticated, DRFRolePermission]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        lines_data = serializer.validated_data.pop("lines_data", [])
        if not lines_data:
            return Response({"detail": "At least one line item is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = services.create_import_order(
                supplier=serializer.validated_data["supplier"],
                country=serializer.validated_data["country"],
                currency=serializer.validated_data["currency"],
                lines_data=lines_data,
                created_by=request.user,
                **serializer.validated_data
            )
            return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)
        except DomainError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = self.get_object()
        try:
            order = services.confirm_import_order(order, user=request.user)
            return Response(self.get_serializer(order).data)
        except (DomainError, WorkflowError) as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)


class TradeDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for documents. Creation happens via standard views to handle file uploads properly."""
    queryset = TradeDocument.objects.select_related("uploaded_by").order_by("-created_at")
    serializer_class = TradeDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, DRFRolePermission]

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        doc = self.get_object()
        result = verify_document(doc)
        return Response(result)


class ShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Shipment.objects.select_related("created_by").order_by("-created_at")
    serializer_class = ShipmentSerializer
    permission_classes = [permissions.IsAuthenticated, DRFRolePermission]
