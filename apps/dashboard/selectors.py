from decimal import Decimal

from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count, Q

from apps.audit_logs.models import AuditLog
from apps.manufacturing.models import ManufacturingOrder, MOStatus
from apps.products.models import Product
from apps.procurement.models import ProcurementRequest
from apps.purchase.models import PurchaseOrderLine, PurchaseOrderStatus
from apps.sales.models import SalesOrderLine, SalesOrder, SalesOrderStatus

LOW_STOCK_THRESHOLD = Decimal("10.00")
RECENT_ACTIVITY_LIMIT = 6
LOW_STOCK_LIMIT = 6


def _money_expression():
    return ExpressionWrapper(
        F("quantity") * F("unit_price"),
        output_field=DecimalField(max_digits=20, decimal_places=2),
    )


def _build_status_chart(choices, counts):
    max_value = max(counts.values()) if counts else 1
    if max_value == 0:
        max_value = 1

    chart = []
    for value, label in choices:
        count = int(counts.get(value, 0))
        ratio = int((count / max_value) * 100) if max_value else 0
        chart.append({
            "label": label,
            "count": count,
            "ratio": ratio,
        })
    return chart


def get_sales_summary():
    counts = SalesOrder.objects.aggregate(
        draft=Count("id", filter=Q(status=SalesOrderStatus.DRAFT)),
        confirmed=Count("id", filter=Q(status=SalesOrderStatus.CONFIRMED)),
        partially_delivered=Count("id", filter=Q(status=SalesOrderStatus.PARTIALLY_DELIVERED)),
        fully_delivered=Count("id", filter=Q(status=SalesOrderStatus.FULLY_DELIVERED)),
        cancelled=Count("id", filter=Q(status=SalesOrderStatus.CANCELLED)),
    )
    total_value = SalesOrderLine.objects.aggregate(
        total=Sum(_money_expression())
    )["total"] or Decimal("0.00")
    return {
        "order_count": SalesOrder.objects.count(),
        "total_value": str(total_value),
        "status_chart": _build_status_chart(SalesOrderStatus.choices, counts),
    }


def get_purchase_summary():
    counts = PurchaseOrderLine.objects.values("purchase_order__status").annotate(
        count=Count("purchase_order_id")
    )
    status_counts = {
        PurchaseOrderStatus.DRAFT: 0,
        PurchaseOrderStatus.CONFIRMED: 0,
        PurchaseOrderStatus.PARTIALLY_RECEIVED: 0,
        PurchaseOrderStatus.FULLY_RECEIVED: 0,
        PurchaseOrderStatus.CANCELLED: 0,
    }
    for row in counts:
        status = row["purchase_order__status"]
        status_counts[status] = row["count"]

    total_value = PurchaseOrderLine.objects.aggregate(
        total=Sum(_money_expression())
    )["total"] or Decimal("0.00")
    return {
        "order_count": PurchaseOrderLine.objects.values("purchase_order_id").distinct().count(),
        "total_value": str(total_value),
        "status_chart": _build_status_chart(PurchaseOrderStatus.choices, status_counts),
    }


def get_manufacturing_summary():
    counts = ManufacturingOrder.objects.aggregate(
        draft=Count("id", filter=Q(status=MOStatus.DRAFT)),
        confirmed=Count("id", filter=Q(status=MOStatus.CONFIRMED)),
        in_progress=Count("id", filter=Q(status=MOStatus.IN_PROGRESS)),
        done=Count("id", filter=Q(status=MOStatus.DONE)),
        cancelled=Count("id", filter=Q(status=MOStatus.CANCELLED)),
    )
    total_qty = ManufacturingOrder.objects.aggregate(total=Sum("qty_to_produce"))["total"] or Decimal("0.00")
    return {
        "order_count": ManufacturingOrder.objects.count(),
        "total_quantity": str(total_qty),
        "status_chart": _build_status_chart(MOStatus.choices, counts),
    }


def get_inventory_summary():
    totals = Product.objects.aggregate(
        total_products=Count("id"),
        total_on_hand=Sum("on_hand_qty"),
        total_reserved=Sum("reserved_qty"),
    )
    on_hand = totals["total_on_hand"] or Decimal("0.00")
    reserved = totals["total_reserved"] or Decimal("0.00")
    available = on_hand - reserved
    return {
        "total_products": totals["total_products"],
        "on_hand_qty": str(on_hand),
        "reserved_qty": str(reserved),
        "available_qty": str(available),
    }


def get_procurement_summary():
    counts = ProcurementRequest.objects.aggregate(
        pending=Count("id", filter=Q(status="PENDING")),
        in_progress=Count("id", filter=Q(status="IN_PROGRESS")),
        completed=Count("id", filter=Q(status="COMPLETED")),
    )
    return {
        "request_count": ProcurementRequest.objects.count(),
        "pending": counts["pending"],
        "in_progress": counts["in_progress"],
        "completed": counts["completed"],
    }


def get_recent_activity_queryset(limit=RECENT_ACTIVITY_LIMIT):
    return AuditLog.objects.select_related("user").order_by("-timestamp")[:limit]


def get_low_stock_products(limit=LOW_STOCK_LIMIT):
    annotated = Product.objects.filter(is_active=True).annotate(
        available_qty=ExpressionWrapper(
            F("on_hand_qty") - F("reserved_qty"),
            output_field=DecimalField(max_digits=20, decimal_places=2),
        )
    ).filter(available_qty__lte=LOW_STOCK_THRESHOLD).order_by("available_qty", "name")[:limit]

    return [
        {
            "id": str(product.id),
            "sku": product.sku,
            "name": product.name,
            "on_hand_qty": str(product.on_hand_qty),
            "reserved_qty": str(product.reserved_qty),
            "available_qty": str(product.available_qty),
            "procurement_type": product.get_procurement_type_display(),
        }
        for product in annotated
    ]


def serialize_recent_activity(activity):
    user_name = activity.user.full_name if activity.user else "System"
    return {
        "id": str(activity.id),
        "timestamp": activity.timestamp.isoformat(),
        "user": user_name,
        "module": activity.module,
        "record_type": activity.record_type,
        "action": activity.get_action_display(),
        "description": f"{activity.module}: {activity.record_type}",
    }


def get_dashboard_summary():
    return {
        "sales": get_sales_summary(),
        "purchase": get_purchase_summary(),
        "manufacturing": get_manufacturing_summary(),
        "inventory": get_inventory_summary(),
        "procurement": get_procurement_summary(),
        "recent_activities": [
            serialize_recent_activity(activity)
            for activity in get_recent_activity_queryset()
        ],
        "low_stock_products": get_low_stock_products(),
    }
