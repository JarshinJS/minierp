"""REST API for reports. Add ``?format=csv`` to any report to download it as CSV."""
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import DRFRolePermission
from core.api import CSVRenderer
from .selectors import REPORTS, get_report, get_reports_overview
from .views import REPORT_ROLES


class _ReportAccess:
    permission_classes = [IsAuthenticated, DRFRolePermission]
    allowed_roles = REPORT_ROLES


ReportOverviewSerializer = inline_serializer("ReportOverview", {
    "sales_total": serializers.IntegerField(),
    "purchase_total": serializers.IntegerField(),
    "mo_total": serializers.IntegerField(),
    "inventory_value": serializers.DecimalField(max_digits=18, decimal_places=2),
    "available_reports": serializers.DictField(child=serializers.ListField(child=serializers.CharField())),
})

ReportTableSerializer = inline_serializer("ReportTable", {
    "category": serializers.CharField(),
    "type": serializers.CharField(),
    "columns": serializers.ListField(child=serializers.CharField()),
    "rows": serializers.ListField(child=serializers.ListField()),
})


class ReportOverviewAPIView(_ReportAccess, APIView):
    @extend_schema(operation_id="reports_overview", responses=ReportOverviewSerializer)
    def get(self, request):
        """Headline totals plus the catalogue of available reports."""
        data = get_reports_overview()
        data["inventory_value"] = f"{data['inventory_value']:.2f}"
        return Response(data)


class ReportAPIView(_ReportAccess, APIView):
    renderer_classes = [JSONRenderer, CSVRenderer]

    @extend_schema(
        operation_id="reports_detail",
        parameters=[
            OpenApiParameter("category", str, OpenApiParameter.PATH, enum=list(REPORTS)),
            OpenApiParameter("report_type", str, OpenApiParameter.PATH,
                             enum=sorted({t for types in REPORTS.values() for t in types})),
            OpenApiParameter("format", str, enum=["json", "csv"]),
        ],
        responses=ReportTableSerializer,
    )
    def get(self, request, category, report_type, format=None):
        report = get_report(category, report_type)
        if report is None:
            raise NotFound(f"Unknown report '{category}/{report_type}'.")
        response = Response({"category": category, "type": report_type, **report})
        if request.accepted_renderer.format == "csv":
            response["Content-Disposition"] = f'attachment; filename="{category}_report_{report_type}.csv"'
        return response
