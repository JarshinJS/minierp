"""REST API for procurement triggers (read-only; triggers are raised by stock shortages)."""
from django.db.models import Count
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import DRFRolePermission, roles_for_module
from .models import ProcurementTrigger, ProcurementTriggerStatus
from .serializers import ProcurementTriggerSerializer


@extend_schema(parameters=[OpenApiParameter("status", str, enum=ProcurementTriggerStatus.values)])
class ProcurementTriggerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProcurementTriggerSerializer
    permission_classes = [IsAuthenticated, DRFRolePermission]
    allowed_roles = roles_for_module("procurement")

    def get_queryset(self):
        qs = ProcurementTrigger.objects.select_related("product", "created_by").order_by("-created_at")
        if (status_filter := self.request.query_params.get("status")) in ProcurementTriggerStatus.values:
            qs = qs.filter(status=status_filter)
        return qs

    @extend_schema(responses=inline_serializer("ProcurementSummary", {
        value.lower(): serializers.IntegerField() for value in ProcurementTriggerStatus.values
    }))
    @action(detail=False, methods=["get"], pagination_class=None)
    def summary(self, request):
        """Trigger counts per status."""
        counts = dict(ProcurementTrigger.objects.values_list("status").annotate(n=Count("id")))
        return Response({value.lower(): counts.get(value, 0) for value in ProcurementTriggerStatus.values})
