"""
selectors.py for the Dashboard app.

This module contains the selectors logic for the Dashboard functionality.
"""
from decimal import Decimal

# pyrefly: ignore [missing-import]
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count, Q

from apps.audit_logs.models import AuditLog
from apps.manufacturing.models import ManufacturingOrder, MOStatus
from apps.products.models import Product
from apps.procurement.models import ProcurementRequest
from apps.purchase.models import PurchaseOrder, PurchaseOrderLine, PurchaseOrderStatus
from apps.sales.models import SalesOrderLine, SalesOrder, SalesOrderStatus
from apps.foreign_trade.models import ExportOrder, ImportOrder
from apps.blockchain.models import BlockchainDocument

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
        avail_qty=ExpressionWrapper(
            F("on_hand_qty") - F("reserved_qty"),
            output_field=DecimalField(max_digits=20, decimal_places=2),
        )
    ).filter(avail_qty__lte=LOW_STOCK_THRESHOLD).order_by("avail_qty", "name")[:limit]

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


def get_foreign_trade_summary():
    exports_count = ExportOrder.objects.count()
    imports_count = ImportOrder.objects.count()
    
    # Blockchain metrics
    bc_total = BlockchainDocument.objects.count()
    bc_verified = BlockchainDocument.objects.filter(verified=True).count()
    
    return {
        "exports_count": exports_count,
        "imports_count": imports_count,
        "blockchain_total": bc_total,
        "blockchain_verified": bc_verified,
        "verified_ratio": int((bc_verified / bc_total) * 100) if bc_total > 0 else 0,
    }



def get_ceo_kpis():
    # 1. Total Products
    total_products = Product.objects.filter(is_active=True).count()
    
    # 2. Inventory Value
    active_products = Product.objects.filter(is_active=True)
    inventory_value = sum(p.on_hand_qty * p.cost_price for p in active_products)
    
    # 3. Sales Orders
    sales_orders = SalesOrder.objects.count()
    
    # 4. Purchase Orders
    purchase_orders = PurchaseOrder.objects.count()
    
    # 5. Manufacturing Orders
    manufacturing_orders = ManufacturingOrder.objects.count()
    
    # 6. Revenue
    revenue = SalesOrderLine.objects.aggregate(total=Sum(_money_expression()))["total"] or Decimal("0.00")
    
    # 7. Pending Deliveries
    from apps.delivery.models import DeliveryNote, DeliveryNoteStatus
    pending_deliveries = DeliveryNote.objects.filter(status=DeliveryNoteStatus.PENDING).count()
    
    # 8. Low Stock Alerts
    low_stock = sum(1 for p in active_products if p.available_qty <= 5.00)

    # No historical snapshots exist, so no period-over-period trend is reported.
    return {
        "total_products": {"value": total_products},
        "inventory_value": {"value": float(inventory_value)},
        "sales_orders": {"value": sales_orders},
        "purchase_orders": {"value": purchase_orders},
        "manufacturing_orders": {"value": manufacturing_orders},
        "revenue": {"value": float(revenue)},
        "pending_deliveries": {"value": pending_deliveries},
        "low_stock_alerts": {"value": low_stock},
    }

def get_erp_workflow_status():
    from apps.delivery.models import DeliveryNote, DeliveryNoteStatus
    
    # Sales Order state
    so_pending = SalesOrder.objects.filter(status__in=[SalesOrderStatus.DRAFT, SalesOrderStatus.CONFIRMED]).exists()
    so_done = SalesOrder.objects.filter(status=SalesOrderStatus.FULLY_DELIVERED).exists()
    
    # Procurement state
    po_active = PurchaseOrder.objects.filter(status__in=[PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.CONFIRMED]).exists()
    
    # Manufacturing state
    mo_active = ManufacturingOrder.objects.filter(status=MOStatus.IN_PROGRESS).exists()
    mo_done = ManufacturingOrder.objects.filter(status=MOStatus.DONE).exists()
    
    # Delivery state
    delivery_active = DeliveryNote.objects.filter(status=DeliveryNoteStatus.PENDING).exists()

    def determine_status(active, done):
        if active: return "active"
        if done: return "completed"
        return "pending"

    return {
        "sales": determine_status(so_pending, so_done),
        "inventory_check": "completed", # Always completed conceptually if we pass sales
        "procurement": determine_status(po_active, False),
        "manufacturing": determine_status(mo_active, mo_done),
        "production": determine_status(mo_active, mo_done),
        "delivery": determine_status(delivery_active, False),
    }

def get_intelligence_alerts():
    """Rule-based operational insights derived only from live records."""
    from apps.delivery.models import DeliveryNote, DeliveryNoteStatus

    alerts = []
    active_products = Product.objects.filter(is_active=True)
    low_stock = [p for p in active_products if p.available_qty <= 5]
    for p in low_stock[:2]:
        alerts.append({"type": "warning", "text": f"Low stock: {p.name} ({p.available_qty} available)", "module": "inventory"})
    if len(low_stock) > 2:
        alerts.append({"type": "warning", "text": f"{len(low_stock) - 2} more products are at or below the reorder level", "module": "inventory"})

    draft_pos = PurchaseOrder.objects.filter(status=PurchaseOrderStatus.DRAFT).count()
    if draft_pos:
        alerts.append({"type": "info", "text": f"{draft_pos} draft purchase order{'s' if draft_pos != 1 else ''} awaiting confirmation", "module": "purchase"})

    pending_dn = DeliveryNote.objects.filter(status=DeliveryNoteStatus.PENDING).count()
    if pending_dn:
        alerts.append({"type": "info", "text": f"{pending_dn} delivery note{'s' if pending_dn != 1 else ''} pending dispatch", "module": "delivery"})

    if not low_stock:
        alerts.append({"type": "success", "text": "All active products are above the reorder level", "module": "inventory"})

    return alerts[:5]


def get_manufacturing_progress():
    """Active MOs with real progress: completed work orders / total work orders,
    falling back to produced quantity when an MO has no routing."""
    from apps.manufacturing.models import WorkOrderStatus

    mos = (
        ManufacturingOrder.objects.filter(status__in=[MOStatus.IN_PROGRESS, MOStatus.CONFIRMED])
        .select_related("product")
        .annotate(
            wo_total=Count("work_orders"),
            wo_done=Count("work_orders", filter=Q(work_orders__status=WorkOrderStatus.DONE)),
        )
        .order_by("-status", "scheduled_date")[:4]
    )
    progress_list = []
    for mo in mos:
        if mo.wo_total:
            pct = int(mo.wo_done * 100 / mo.wo_total)
            detail = f"{mo.wo_done}/{mo.wo_total} operations"
        else:
            pct = mo.progress_pct
            detail = f"{mo.qty_produced}/{mo.qty_to_produce} produced"
        progress_list.append({
            "id": str(mo.id),
            "number": mo.reference,
            "product": mo.product.name,
            "status": mo.status,
            "status_label": mo.get_status_display(),
            "detail": detail,
            "percentage": pct,
        })
    return progress_list


def get_dashboard_summary():
    return {
        "sales": get_sales_summary(),
        "purchase": get_purchase_summary(),
        "manufacturing": get_manufacturing_summary(),
        "inventory": get_inventory_summary(),
        "procurement": get_procurement_summary(),
        "foreign_trade": get_foreign_trade_summary(),
        "recent_activities": [
            serialize_recent_activity(activity)
            for activity in get_recent_activity_queryset()
        ],
        "low_stock_products": get_low_stock_products(),
        "ceo_kpis": get_ceo_kpis(),
        "erp_workflow": get_erp_workflow_status(),
        "intelligence_alerts": get_intelligence_alerts(),
        "manufacturing_progress": get_manufacturing_progress(),
    }
