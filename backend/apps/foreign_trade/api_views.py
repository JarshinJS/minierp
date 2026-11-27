"""
REST API for Foreign Trade. Workflow steps go through ``workflows`` so they
record the same blockchain audit events as the HTML views.
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import DRFRolePermission
from core.exceptions import DomainError
from . import documents, roles, workflows
from .models import (
    Country, Currency, ExportOrder, ExportOrderStatus, ImportOrder, ImportOrderStatus,
    Incoterm, Shipment, TradeCustomer, TradeDocument, TradeSupplier,
)
from .serializers import (
    CountrySerializer, CurrencySerializer, ExportInvoiceCreateSerializer, ExportInvoiceSerializer,
    ExportOrderSerializer, ImportOrderSerializer, IncotermSerializer, ShipmentInputSerializer,
    ShipmentSerializer, TradeCustomerSerializer, TradeDocumentSerializer,
    TradeDocumentUploadSerializer, TradeSupplierSerializer,
)

logger = logging.getLogger(__name__)

NO_DELETE = ["get", "post", "put", "patch", "head", "options"]
VerificationResultSerializer = inline_serializer("DocumentVerification", {
    "verified": serializers.BooleanField(),
    "outcome": serializers.ChoiceField(
        choices=["VERIFIED", "TAMPERED", "UNVERIFIED", "PENDING", "UNAVAILABLE"],
        help_text="Result of this check. UNAVAILABLE = chain unreachable; stored status unchanged.",
    ),
    "status": serializers.CharField(),
    "message": serializers.CharField(),
    "stored_hash": serializers.CharField(allow_null=True),
    "current_hash": serializers.CharField(required=False),
    "blockchain_txn": serializers.CharField(required=False, allow_null=True),
    "block_number": serializers.IntegerField(required=False, allow_null=True),
    "network": serializers.CharField(required=False),
})


class _TradeAccess:
    permission_classes = [IsAuthenticated, DRFRolePermission]


class _OrderViewSet(_TradeAccess, viewsets.ModelViewSet):
    """Shared behaviour for export and import orders."""
    http_method_names = NO_DELETE  # orders are cancelled, never deleted
    read_roles = roles.ORDER_READ
    allowed_roles = roles.ORDER_WRITE
    party_field = None  # "customer" | "supplier"
    status_enum = None

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if search := params.get("search", "").strip():
            qs = qs.filter(Q(order_number__icontains=search) | Q(**{f"{self.party_field}__name__icontains": search}))
        if (status_filter := params.get("status")) in self.status_enum.values:
            qs = qs.filter(status=status_filter)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        lines = [dict(line) for line in data.pop("lines_data", [])]
        if not lines:
            raise DomainError("At least one line item is required.")
        order = self.create_order(
            request.user,
            **{self.party_field: data.pop(self.party_field)},
            country=data.pop("country"),
            currency=data.pop("currency"),
            lines_data=lines,
            **data,
        )
        return Response(self.get_serializer(self.get_queryset().get(pk=order.pk)).data,
                        status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        """Header fields only, and only while the order is still a draft."""
        if serializer.instance.status != self.status_enum.DRAFT:
            raise DomainError("Only DRAFT orders can be edited.")
        serializer.validated_data.pop("lines_data", None)
        serializer.save()

    def create_order(self, user, **fields):
        raise NotImplementedError

    def _respond(self, order):
        return Response(self.get_serializer(self.get_queryset().get(pk=order.pk)).data)


@extend_schema(parameters=[
    OpenApiParameter("search", str, description="Order number or customer name"),
    OpenApiParameter("status", str, enum=ExportOrderStatus.values),
])
class ExportOrderViewSet(_OrderViewSet):
    queryset = (ExportOrder.objects.select_related("customer__country", "country", "currency")
                .prefetch_related("lines").order_by("-created_at"))
    serializer_class = ExportOrderSerializer
    party_field = "customer"
    status_enum = ExportOrderStatus
    action_roles = {"invoices": roles.INVOICE_WRITE}

    def create_order(self, user, **fields):
        return workflows.create_export(user, **fields)

    @extend_schema(request=None, responses=ExportOrderSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._respond(workflows.confirm_export(self.get_object(), request.user))

    @extend_schema(request=ShipmentInputSerializer, responses=inline_serializer("ExportShipResult", {
        "order": ExportOrderSerializer(), "shipment": ShipmentSerializer(),
    }))
    @action(detail=True, methods=["post"])
    def ship(self, request, pk=None):
        data = ShipmentInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order, shipment = workflows.ship_export(self.get_object(), data.validated_data, request.user)
        return Response({"order": self._respond(order).data, "shipment": ShipmentSerializer(shipment).data})

    @extend_schema(request=None, responses=ExportOrderSerializer)
    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        return self._respond(workflows.deliver_export(self.get_object(), request.user))

    @extend_schema(request=None, responses=ExportOrderSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._respond(workflows.cancel_export(self.get_object(), request.user))

    @extend_schema(methods=["GET"], request=None, responses=ExportInvoiceSerializer(many=True))
    @extend_schema(methods=["POST"], request=ExportInvoiceCreateSerializer, responses={201: ExportInvoiceSerializer})
    @action(detail=True, methods=["get", "post"], pagination_class=None)
    def invoices(self, request, pk=None):
        """List this order's invoices, or raise a new one."""
        order = self.get_object()
        if request.method == "GET":
            invoices = order.invoices.select_related("currency").order_by("-created_at")
            return Response(ExportInvoiceSerializer(invoices, many=True).data)
        data = ExportInvoiceCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        invoice = workflows.create_invoice(order, request.user, **data.validated_data)
        return Response(ExportInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


@extend_schema(parameters=[
    OpenApiParameter("search", str, description="Order number or supplier name"),
    OpenApiParameter("status", str, enum=ImportOrderStatus.values),
])
class ImportOrderViewSet(_OrderViewSet):
    queryset = (ImportOrder.objects.select_related("supplier__country", "country", "currency")
                .prefetch_related("lines").order_by("-created_at"))
    serializer_class = ImportOrderSerializer
    party_field = "supplier"
    status_enum = ImportOrderStatus

    def create_order(self, user, **fields):
        return workflows.create_import(user, **fields)

    @extend_schema(request=None, responses=ImportOrderSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._respond(workflows.confirm_import(self.get_object(), request.user))

    @extend_schema(request=ShipmentInputSerializer, responses=inline_serializer("ImportTransitResult", {
        "order": ImportOrderSerializer(), "shipment": ShipmentSerializer(),
    }))
    @action(detail=True, methods=["post"])
    def transit(self, request, pk=None):
        data = ShipmentInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order, shipment = workflows.transit_import(self.get_object(), data.validated_data, request.user)
        return Response({"order": self._respond(order).data, "shipment": ShipmentSerializer(shipment).data})

    @extend_schema(request=None, responses=ImportOrderSerializer)
    @action(detail=True, methods=["post"])
    def customs(self, request, pk=None):
        return self._respond(workflows.customs_import(self.get_object(), request.user))

    @extend_schema(request=None, responses=ImportOrderSerializer)
    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        return self._respond(workflows.receive_import(self.get_object(), request.user))

    @extend_schema(request=None, responses=ImportOrderSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._respond(workflows.cancel_import(self.get_object(), request.user))


@extend_schema(parameters=[
    OpenApiParameter("order_type", str, enum=["export", "import"]),
    OpenApiParameter("order_id", str),
    OpenApiParameter("document_type", str),
])
class TradeDocumentViewSet(_TradeAccess, mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    """Trade documents. POST (multipart) uploads a new version for an order."""
    serializer_class = TradeDocumentSerializer
    read_roles = roles.DOCUMENT_READ
    allowed_roles = roles.DOCUMENT_WRITE
    action_roles = {"verify": roles.DOCUMENT_READ, "download": roles.DOCUMENT_READ}
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = TradeDocument.objects.select_related("uploaded_by", "content_type").order_by("-created_at")
        params = self.request.query_params
        model = {"export": ExportOrder, "import": ImportOrder}.get(params.get("order_type"))
        if model:
            qs = qs.filter(content_type=ContentType.objects.get_for_model(model))
        if order_id := params.get("order_id"):
            qs = qs.filter(object_id=order_id)
        if document_type := params.get("document_type"):
            qs = qs.filter(document_type=document_type)
        return qs

    @extend_schema(request={"multipart/form-data": TradeDocumentUploadSerializer},
                   responses={201: TradeDocumentSerializer})
    def create(self, request, *args, **kwargs):
        data = TradeDocumentUploadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        doc = workflows.upload_document(
            v["order"], request.user,
            file=v["file"], document_type=v["document_type"], title=v["title"], notes=v["notes"],
        )
        return Response(self.get_serializer(doc).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[OpenApiParameter("token", str, required=True,
                                     description="Signed token from the document's `file` URL")],
        responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
    )
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """
        Stream the stored file. Needs a DOCUMENT_READ role *and* the short-lived
        token issued to this user for this document (the `file` field of the
        document). The token is checked before the document is looked up, so a
        bad link reveals nothing about which documents exist.
        """
        try:
            documents.check_download_token(request.query_params.get("token"), pk, request.user)
        except documents.DownloadTokenError as e:
            return Response({"detail": e.message, "code": e.code}, status=status.HTTP_403_FORBIDDEN)

        doc = self.get_object()
        if not doc.file or not doc.file.storage.exists(doc.file.name):
            logger.error("Trade document %s: stored file is missing", doc.pk)
            raise Http404("File not found.")

        response = FileResponse(
            doc.file.open("rb"), as_attachment=True,
            filename=documents.download_filename(doc), content_type=documents.content_type_for(doc),
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        response["Referrer-Policy"] = "no-referrer"
        return response

    @extend_schema(request=None, responses=VerificationResultSerializer)
    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Check the stored file against its blockchain fingerprint."""
        return Response(workflows.verify(self.get_object(), request.user))


class ShipmentViewSet(_TradeAccess, viewsets.ReadOnlyModelViewSet):
    queryset = Shipment.objects.select_related("created_by").order_by("-created_at")
    serializer_class = ShipmentSerializer
    allowed_roles = roles.DOCUMENT_READ


class _PartnerViewSet(_TradeAccess, viewsets.ModelViewSet):
    http_method_names = NO_DELETE  # deactivate via PATCH {"is_active": false}
    allowed_roles = roles.PARTNERS

    def get_queryset(self):
        qs = super().get_queryset()
        if search := self.request.query_params.get("search", "").strip():
            qs = qs.filter(name__icontains=search)
        return qs


@extend_schema(parameters=[OpenApiParameter("search", str)])
class TradeCustomerViewSet(_PartnerViewSet):
    queryset = TradeCustomer.objects.select_related("country").order_by("name")
    serializer_class = TradeCustomerSerializer


@extend_schema(parameters=[OpenApiParameter("search", str)])
class TradeSupplierViewSet(_PartnerViewSet):
    queryset = TradeSupplier.objects.select_related("country").order_by("name")
    serializer_class = TradeSupplierSerializer


class _ReferenceViewSet(_TradeAccess, viewsets.ReadOnlyModelViewSet):
    """Small lookup tables for trade forms; unpaginated."""
    allowed_roles = roles.REFERENCE_READ
    pagination_class = None


class CountryViewSet(_ReferenceViewSet):
    queryset = Country.objects.order_by("name")
    serializer_class = CountrySerializer


class CurrencyViewSet(_ReferenceViewSet):
    queryset = Currency.objects.order_by("code")
    serializer_class = CurrencySerializer


class IncotermViewSet(_ReferenceViewSet):
    queryset = Incoterm.objects.order_by("code")
    serializer_class = IncotermSerializer
