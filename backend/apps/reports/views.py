"""
views.py for the Reports app.

HTML overview page plus CSV downloads. The report queries live in
reports.selectors and are shared with the REST API (reports.api).
"""
import csv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.models import UserRole
from apps.accounts.permissions import RoleRequiredMixin
from .selectors import REPORTS, get_report, get_reports_overview

# Narrower than the "reports" entry in MODULE_ACCESS on purpose: the sidebar
# restricts Reports to these roles too (see navigation NAV_ITEMS["reports"]).
REPORT_ROLES = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.ACCOUNTANT]


class ReportsHomeView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    template_name = "reports/home.html"
    allowed_roles = REPORT_ROLES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        overview = get_reports_overview()
        context.update({
            "sales_total": overview["sales_total"],
            "purchase_total": overview["purchase_total"],
            "mo_total": overview["mo_total"],
            "inventory_value": overview["inventory_value"],
        })
        return context


class _CSVReportView(LoginRequiredMixin, RoleRequiredMixin, View):
    """Download ``?type=<report type>`` of ``category`` as CSV."""
    allowed_roles = REPORT_ROLES
    category = None

    def get(self, request, *args, **kwargs):
        default_type = next(iter(REPORTS[self.category]))
        report_type = request.GET.get("type", default_type)
        report = get_report(self.category, report_type)
        if report is None:
            return HttpResponseBadRequest("Invalid report type")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{self.category}_report_{report_type}.csv"'
        writer = csv.writer(response)
        writer.writerow(report["columns"])
        writer.writerows(report["rows"])
        return response


class ExportSalesReportView(_CSVReportView):
    category = "sales"


class ExportPurchaseReportView(_CSVReportView):
    category = "purchase"


class ExportManufacturingReportView(_CSVReportView):
    category = "manufacturing"


class ExportInventoryReportView(_CSVReportView):
    category = "inventory"
