"""REST API for delivery notes."""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import UserRole
from apps.accounts.permissions import DRFRolePermission, roles_for_module
from core.exceptions import DomainError
from . import services
from .models import DeliveryNote, DeliveryNoteStatus
from .serializers import DeliveryNoteCreateSerializer, DeliveryNoteSerializer


@extend_schema(parameters=[OpenApiParameter("status", str, enum=DeliveryNoteStatus.values)])
class DeliveryNoteViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = DeliveryNoteSerializer
    permission_classes = [IsAuthenticated, DRFRolePermission]
    allowed_roles = roles_for_module("delivery")
    # Dispatching ships goods out of the warehouse: inventory roles only (matches the HTML view).
    action_roles = {
        "dispatch_note": [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.INVENTORY_MANAGER],
    }

    def get_queryset(self):
        qs = (DeliveryNote.objects
              .select_related("sales_order", "created_by")
              .prefetch_related("lines__sales_order_line__product")
              .order_by("-created_at"))
        if (status_filter := self.request.query_params.get("status")) in DeliveryNoteStatus.values:
            qs = qs.filter(status=status_filter)
        return qs

    @extend_schema(request=DeliveryNoteCreateSerializer, responses={201: DeliveryNoteSerializer})
    def create(self, request, *args, **kwargs):
        serializer = DeliveryNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order = data["sales_order"]
        lines = data.get("lines") or services.pending_delivery_lines(order)
        if not lines:
            raise DomainError("No items pending delivery on this order.")
        note = services.create_delivery_note(
            sales_order=order,
            lines_data=lines,
            created_by=request.user,
            notes=data["notes"] or f"Delivery Note for {order.order_number}",
        )
        return Response(self.get_serializer(self.get_queryset().get(pk=note.pk)).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=DeliveryNoteSerializer)
    # Not named `dispatch`: that would override APIView.dispatch().
    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_note(self, request, pk=None):
        note = self.get_object()
        services.dispatch_delivery_note(note, user=request.user)
        return Response(self.get_serializer(self.get_queryset().get(pk=note.pk)).data)

    @extend_schema(request=None, responses=DeliveryNoteSerializer)
    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        note = self.get_object()
        services.deliver_delivery_note(note, user=request.user)
        return Response(self.get_serializer(self.get_queryset().get(pk=note.pk)).data)
