"""
Report queries shared by the CSV downloads (reports.views) and the REST API (reports.api).

Each report function returns ``{"columns": [...], "rows": [[...], ...]}``.
Money values are formatted as strings with two decimals.
"""
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate, TruncMonth

from apps.inventory.models import InventoryLedgerEntry
from apps.manufacturing.models import BOMComponent, ManufacturingOrder, MOStatus
from apps.products.models import Product
from apps.purchase.models import PurchaseOrder, PurchaseOrderStatus
from apps.sales.models import SalesOrder, SalesOrderStatus

LOW_STOCK_THRESHOLD = Decimal("5.00")


def _money(value):
    return f"{(value or Decimal('0')):.2f}"


def _line_total(prefix="lines__"):
    return Sum(
        ExpressionWrapper(F(f"{prefix}quantity") * F(f"{prefix}unit_price"),
                          output_field=DecimalField(max_digits=18, decimal_places=2))
    )


def _active_sales():
    return SalesOrder.objects.exclude(status=SalesOrderStatus.CANCELLED)


def _active_purchases():
    return PurchaseOrder.objects.exclude(status=PurchaseOrderStatus.CANCELLED)


# --- Sales ------------------------------------------------------------------

def sales_daily():
    rows = (_active_sales().annotate(day=TruncDate("created_at")).values("day")
            .annotate(count=Count("id", distinct=True), revenue=_line_total()).order_by("-day"))
    return {"columns": ["Date", "Orders Count", "Total Revenue"],
            "rows": [[r["day"].isoformat(), r["count"], _money(r["revenue"])] for r in rows]}


def sales_monthly():
    rows = (_active_sales().annotate(month=TruncMonth("created_at")).values("month")
            .annotate(count=Count("id", distinct=True), revenue=_line_total()).order_by("-month"))
    return {"columns": ["Month", "Orders Count", "Total Revenue"],
            "rows": [[r["month"].strftime("%Y-%m"), r["count"], _money(r["revenue"])] for r in rows]}


def sales_by_customer():
    rows = (_active_sales().values("customer_name")
            .annotate(count=Count("id", distinct=True), revenue=_line_total()).order_by("-count", "customer_name"))
    return {"columns": ["Customer Name", "Orders Count", "Total Revenue"],
            "rows": [[r["customer_name"], r["count"], _money(r["revenue"])] for r in rows]}


# --- Purchase ---------------------------------------------------------------

def purchase_monthly_summary():
    rows = (_active_purchases().annotate(month=TruncMonth("created_at")).values("month")
            .annotate(count=Count("id", distinct=True), total=_line_total()).order_by("-month"))
    return {"columns": ["Month", "PO Count", "Total Purchase Value"],
            "rows": [[r["month"].strftime("%Y-%m"), r["count"], _money(r["total"])] for r in rows]}


def purchase_by_vendor():
    rows = (_active_purchases().values("vendor__name")
            .annotate(count=Count("id", distinct=True), total=_line_total()).order_by("-count", "vendor__name"))
    return {"columns": ["Vendor Name", "PO Count", "Total Purchase Value"],
            "rows": [[r["vendor__name"], r["count"], _money(r["total"])] for r in rows]}


# --- Manufacturing ------------------------------------------------------------

def manufacturing_efficiency():
    mos = ManufacturingOrder.objects.select_related("product").order_by("-created_at")
    return {"columns": ["MO Number", "Product SKU", "Product Name", "Qty Produced", "Status", "Created At"],
            "rows": [[mo.reference, mo.product.sku, mo.product.name, str(mo.qty_to_produce), mo.status,
                      mo.created_at.strftime("%Y-%m-%d %H:%M")] for mo in mos]}


def manufacturing_consumption():
    lines = (BOMComponent.objects
             .filter(bom__default_products__is_active=True)
             .select_related("component")
             .annotate(finished_name=F("bom__default_products__name"))
             .order_by("finished_name", "sequence"))
    return {"columns": ["Finished Product", "Raw Material SKU", "Raw Material Name", "BoM Quantity Needed"],
            "rows": [[line.finished_name, line.component.sku, line.component.name, str(line.quantity)]
                     for line in lines]}


# --- Inventory ----------------------------------------------------------------

def inventory_ledger():
    entries = InventoryLedgerEntry.objects.select_related("product").order_by("-created_at")
    return {"columns": ["Timestamp", "Product SKU", "Product Name", "Type", "Quantity", "Reference"],
            "rows": [[e.created_at.strftime("%Y-%m-%d %H:%M:%S"), e.product.sku, e.product.name,
                      e.entry_type, str(e.quantity), e.reference] for e in entries]}


def inventory_valuation():
    products = Product.objects.filter(is_active=True).order_by("sku")
    return {"columns": ["SKU", "Product Name", "On Hand", "Cost Price", "Total Valuation"],
            "rows": [[p.sku, p.name, str(p.on_hand_qty), str(p.cost_price), _money(p.on_hand_qty * p.cost_price)]
                     for p in products]}


def inventory_low_stock():
    products = (Product.objects.filter(is_active=True)
                .annotate(avail=ExpressionWrapper(F("on_hand_qty") - F("reserved_qty"), output_field=DecimalField()))
                .filter(avail__lte=LOW_STOCK_THRESHOLD).order_by("sku"))
    return {"columns": ["SKU", "Product Name", "On Hand", "Reserved", "Available Quantity"],
            "rows": [[p.sku, p.name, str(p.on_hand_qty), str(p.reserved_qty), str(p.avail)] for p in products]}


# category -> {report type -> function}; the first type is the default.
REPORTS = {
    "sales": {"daily": sales_daily, "monthly": sales_monthly, "customer": sales_by_customer},
    "purchase": {"summary": purchase_monthly_summary, "vendor": purchase_by_vendor},
    "manufacturing": {"efficiency": manufacturing_efficiency, "consumption": manufacturing_consumption},
    "inventory": {"ledger": inventory_ledger, "valuation": inventory_valuation, "low_stock": inventory_low_stock},
}


def get_report(category, report_type):
    """Run a report, or return None if the category/type is unknown."""
    fn = REPORTS.get(category, {}).get(report_type)
    return fn() if fn else None


def get_reports_overview():
    value = ExpressionWrapper(F("on_hand_qty") * F("cost_price"), output_field=DecimalField(max_digits=18, decimal_places=2))
    inventory_value = Product.objects.filter(is_active=True).aggregate(v=Sum(value))["v"] or Decimal("0")
    return {
        "sales_total": _active_sales().count(),
        "purchase_total": _active_purchases().count(),
        "mo_total": ManufacturingOrder.objects.exclude(status=MOStatus.CANCELLED).count(),
        "inventory_value": inventory_value,
        "available_reports": {category: list(types) for category, types in REPORTS.items()},
    }
