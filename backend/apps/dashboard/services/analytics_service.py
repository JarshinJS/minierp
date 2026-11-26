from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.sales.models import SalesOrder, SalesOrderStatus
from apps.purchase.models import PurchaseOrder, PurchaseOrderStatus
from apps.manufacturing.models import ManufacturingOrder, MOStatus
from apps.inventory.models import InventoryLedgerEntry, LedgerEntryType

def get_sales_trend():
    """
    Returns monthly sales totals for the last 6 months.
    """
    six_months_ago = timezone.now() - timezone.timedelta(days=180)
    query = (
        SalesOrder.objects.filter(created_at__gte=six_months_ago)
        .exclude(status=SalesOrderStatus.CANCELLED)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )
    labels = []
    data = []
    for row in query:
        # Sum total invoices for that month
        month_orders = SalesOrder.objects.filter(
            created_at__year=row["month"].year,
            created_at__month=row["month"].month
        ).exclude(status=SalesOrderStatus.CANCELLED)
        val = sum(o.total_amount for o in month_orders)
        labels.append(row["month"].strftime("%b %Y"))
        data.append(float(val))
    
    # Fallback if no data
    if not labels:
        labels = ["Current Month"]
        data = [0.0]

    return {"labels": labels, "data": data}


def get_purchase_trend():
    """
    Returns monthly purchase totals for the last 6 months.
    """
    six_months_ago = timezone.now() - timezone.timedelta(days=180)
    query = (
        PurchaseOrder.objects.filter(created_at__gte=six_months_ago)
        .exclude(status=PurchaseOrderStatus.CANCELLED)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )
    labels = []
    data = []
    for row in query:
        month_pos = PurchaseOrder.objects.filter(
            created_at__year=row["month"].year,
            created_at__month=row["month"].month
        ).exclude(status=PurchaseOrderStatus.CANCELLED)
        val = sum(po.total_amount for po in month_pos)
        labels.append(row["month"].strftime("%b %Y"))
        data.append(float(val))

    if not labels:
        labels = ["Current Month"]
        data = [0.0]

    return {"labels": labels, "data": data}


def get_manufacturing_progress():
    """
    Returns counts of Manufacturing Orders by status.
    """
    counts = ManufacturingOrder.objects.aggregate(
        draft=Count("id", filter=Q(status=MOStatus.DRAFT)),
        confirmed=Count("id", filter=Q(status=MOStatus.CONFIRMED)),
        in_progress=Count("id", filter=Q(status=MOStatus.IN_PROGRESS)),
        done=Count("id", filter=Q(status=MOStatus.DONE)),
        cancelled=Count("id", filter=Q(status=MOStatus.CANCELLED)),
    )
    return {
        "labels": ["Draft", "Confirmed", "In Progress", "Completed", "Cancelled"],
        "data": [counts["draft"], counts["confirmed"], counts["in_progress"], counts["done"], counts["cancelled"]]
    }


def get_inventory_movement():
    """
    Returns total quantities of inventory ledger entries by type.
    """
    counts = InventoryLedgerEntry.objects.aggregate(
        receipts=Sum("quantity", filter=Q(entry_type=LedgerEntryType.RECEIPT)),
        issues=Sum("quantity", filter=Q(entry_type=LedgerEntryType.ISSUE)),
        reservations=Sum("quantity", filter=Q(entry_type=LedgerEntryType.RESERVATION)),
        releases=Sum("quantity", filter=Q(entry_type=LedgerEntryType.RELEASE)),
    )
    receipts = float(counts["receipts"] or 0)
    issues = float(counts["issues"] or 0)
    reservations = float(counts["reservations"] or 0)
    releases = float(counts["releases"] or 0)

    return {
        "labels": ["Receipts", "Issues", "Reservations", "Releases"],
        "data": [receipts, issues, reservations, releases]
    }
