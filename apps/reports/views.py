"""
views.py for the Reports app.

This module contains the views logic for the Reports functionality.
"""
import csv
from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.views import View
from django.http import HttpResponse, HttpResponseBadRequest
from django.db.models import Sum, F, Count, Q
from django.db.models.functions import TruncMonth, TruncDay

from apps.accounts.permissions import RoleRequiredMixin
from apps.accounts.models import UserRole
from apps.sales.models import SalesOrder, SalesOrderLine
from apps.purchase.models import PurchaseOrder, PurchaseOrderLine
from apps.manufacturing.models import ManufacturingOrder
from apps.products.models import Product
from apps.inventory.models import InventoryLedgerEntry

class ReportsHomeView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    template_name = "reports/home.html"
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.ACCOUNTANT]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Gather basic stats for the reports dashboard overview
        context["sales_total"] = SalesOrder.objects.exclude(status="CANCELLED").count()
        context["purchase_total"] = PurchaseOrder.objects.exclude(status="CANCELLED").count()
        context["mo_total"] = ManufacturingOrder.objects.exclude(status="CANCELLED").count()
        context["inventory_value"] = sum(p.on_hand_qty * p.cost_price for p in Product.objects.filter(is_active=True))
        return context


class ExportSalesReportView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.ACCOUNTANT]

    def get(self, request, *args, **kwargs):
        report_type = request.GET.get("type", "daily")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="sales_report_{report_type}.csv"'

        writer = csv.writer(response)

        if report_type == "daily":
            writer.writerow(["Date", "Orders Count", "Total Revenue"])
            query = (
                SalesOrder.objects.exclude(status="CANCELLED")
                .annotate(date=TruncDay("created_at"))
                .values("date")
                .annotate(count=Count("id"))
                .order_by("-date")
            )
            for row in query:
                # Calculate revenue for that day
                day_orders = SalesOrder.objects.filter(created_at__date=row["date"].date())
                revenue = sum(
                    line.quantity * line.unit_price 
                    for order in day_orders 
                    for line in order.lines.all()
                )
                writer.writerow([row["date"].strftime("%Y-%m-%d"), row["count"], f"{revenue:.2f}"])

        elif report_type == "monthly":
            writer.writerow(["Month", "Orders Count", "Total Revenue"])
            query = (
                SalesOrder.objects.exclude(status="CANCELLED")
                .annotate(month=TruncMonth("created_at"))
                .values("month")
                .annotate(count=Count("id"))
                .order_by("-month")
            )
            for row in query:
                month_orders = SalesOrder.objects.filter(
                    created_at__year=row["month"].year,
                    created_at__month=row["month"].month
                )
                revenue = sum(
                    line.quantity * line.unit_price 
                    for order in month_orders 
                    for line in order.lines.all()
                )
                writer.writerow([row["month"].strftime("%Y-%m"), row["count"], f"{revenue:.2f}"])

        elif report_type == "customer":
            writer.writerow(["Customer Name", "Orders Count", "Total Revenue"])
            query = (
                SalesOrder.objects.exclude(status="CANCELLED")
                .values("customer_name")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            for row in query:
                cust_orders = SalesOrder.objects.filter(customer_name=row["customer_name"])
                revenue = sum(
                    line.quantity * line.unit_price 
                    for order in cust_orders 
                    for line in order.lines.all()
                )
                writer.writerow([row["customer_name"], row["count"], f"{revenue:.2f}"])
        else:
            return HttpResponseBadRequest("Invalid report type")

        return response


class ExportPurchaseReportView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.ACCOUNTANT]

    def get(self, request, *args, **kwargs):
        report_type = request.GET.get("type", "summary")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="purchase_report_{report_type}.csv"'

        writer = csv.writer(response)

        if report_type == "vendor":
            writer.writerow(["Vendor Name", "PO Count", "Total Purchase Value"])
            query = (
                PurchaseOrder.objects.exclude(status="CANCELLED")
                .values("vendor__name")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            for row in query:
                vendor_name = row["vendor__name"]
                pos = PurchaseOrder.objects.filter(vendor__name=vendor_name)
                total_val = sum(
                    line.quantity * line.unit_price 
                    for po in pos 
                    for line in po.lines.all()
                )
                writer.writerow([vendor_name, row["count"], f"{total_val:.2f}"])

        elif report_type == "summary":
            writer.writerow(["Month", "PO Count", "Total Purchase Value"])
            query = (
                PurchaseOrder.objects.exclude(status="CANCELLED")
                .annotate(month=TruncMonth("created_at"))
                .values("month")
                .annotate(count=Count("id"))
                .order_by("-month")
            )
            for row in query:
                month_pos = PurchaseOrder.objects.filter(
                    created_at__year=row["month"].year,
                    created_at__month=row["month"].month
                )
                total_val = sum(
                    line.quantity * line.unit_price 
                    for po in month_pos 
                    for line in po.lines.all()
                )
                writer.writerow([row["month"].strftime("%Y-%m"), row["count"], f"{total_val:.2f}"])
        else:
            return HttpResponseBadRequest("Invalid report type")

        return response


class ExportManufacturingReportView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.ACCOUNTANT]

    def get(self, request, *args, **kwargs):
        report_type = request.GET.get("type", "efficiency")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="manufacturing_report_{report_type}.csv"'

        writer = csv.writer(response)

        if report_type == "efficiency":
            writer.writerow(["MO Number", "Product SKU", "Product Name", "Qty Produced", "Status", "Created At"])
            mos = ManufacturingOrder.objects.all().select_related("product").order_by("-created_at")
            for mo in mos:
                writer.writerow([mo.reference, mo.product.sku, mo.product.name, mo.qty_to_produce, mo.status, mo.created_at.strftime("%Y-%m-%d %H:%M")])

        elif report_type == "consumption":
            writer.writerow(["Finished Product", "Raw Material SKU", "Raw Material Name", "BoM Quantity Needed"])
            products = Product.objects.filter(is_active=True, default_bom__isnull=False).select_related("default_bom")
            for p in products:
                bom = p.default_bom
                for line in bom.components.all():
                    writer.writerow([
                        p.name,
                        line.product.sku,
                        line.product.name,
                        line.quantity
                    ])
        else:
            return HttpResponseBadRequest("Invalid report type")

        return response


class ExportInventoryReportView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.ACCOUNTANT]

    def get(self, request, *args, **kwargs):
        report_type = request.GET.get("type", "ledger")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="inventory_report_{report_type}.csv"'

        writer = csv.writer(response)

        if report_type == "ledger":
            writer.writerow(["Timestamp", "Product SKU", "Product Name", "Type", "Quantity", "Reference"])
            entries = InventoryLedgerEntry.objects.all().select_related("product").order_by("-created_at")
            for entry in entries:
                writer.writerow([
                    entry.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    entry.product.sku,
                    entry.product.name,
                    entry.entry_type,
                    entry.quantity,
                    entry.reference
                ])

        elif report_type == "valuation":
            writer.writerow(["SKU", "Product Name", "On Hand", "Cost Price", "Total Valuation"])
            products = Product.objects.filter(is_active=True).order_by("sku")
            for p in products:
                valuation = p.on_hand_qty * p.cost_price
                writer.writerow([p.sku, p.name, p.on_hand_qty, p.cost_price, f"{valuation:.2f}"])

        elif report_type == "low_stock":
            writer.writerow(["SKU", "Product Name", "On Hand", "Reserved", "Available Quantity"])
            products = Product.objects.filter(is_active=True).order_by("sku")
            for p in products:
                if p.available_qty <= 5.00:
                    writer.writerow([p.sku, p.name, p.on_hand_qty, p.reserved_qty, p.available_qty])
        else:
            return HttpResponseBadRequest("Invalid report type")

        return response
