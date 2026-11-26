from django.utils import timezone
from apps.products.models import Product
from apps.delivery.models import DeliveryNote, DeliveryNoteStatus
from apps.manufacturing.models import ManufacturingOrder, MOStatus
from apps.procurement.models import ProcurementRequest, ProcurementStatus

def get_low_stock_alerts():
    """
    Returns products with available quantity <= 5.
    """
    # Load products and filter in Python because available_qty is a property
    active_products = Product.objects.filter(is_active=True).select_related("category")
    alerts = []
    for p in active_products:
        if p.available_qty <= 5.00:
            alerts.append({
                "sku": p.sku,
                "name": p.name,
                "available_qty": float(p.available_qty),
                "reorder_level": 5.00
            })
    return alerts[:10]  # Cap at 10 alerts


def get_pending_deliveries():
    """
    Returns pending delivery notes.
    """
    dns = DeliveryNote.objects.filter(status=DeliveryNoteStatus.PENDING).select_related("sales_order")[:10]
    return [
        {
            "id": str(dn.id),
            "delivery_number": dn.delivery_number,
            "order_number": dn.sales_order.order_number,
            "customer_name": dn.sales_order.customer_name,
            "created_at": dn.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for dn in dns
    ]


def get_delayed_manufacturing_orders():
    """
    Returns manufacturing orders past scheduled date.
    """
    today = timezone.now().date()
    mos = ManufacturingOrder.objects.filter(
        status__in=[MOStatus.DRAFT, MOStatus.CONFIRMED, MOStatus.IN_PROGRESS],
        scheduled_date__lt=today
    ).select_related("product")[:10]

    return [
        {
            "id": str(mo.id),
            "reference": mo.reference,
            "product_sku": mo.product.sku,
            "qty": float(mo.qty_to_produce),
            "scheduled_date": mo.scheduled_date.strftime("%Y-%m-%d") if mo.scheduled_date else "No Date",
            "status": mo.status
        }
        for mo in mos
    ]


def get_pending_procurement_requests():
    """
    Returns pending procurement requests.
    """
    reqs = ProcurementRequest.objects.filter(status=ProcurementStatus.PENDING).select_related("product")[:10]
    return [
        {
            "id": str(r.id),
            "product_sku": r.product.sku,
            "qty": float(r.quantity_needed),
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for r in reqs
    ]


def get_all_alerts():
    """
    Assembles all alert dictionaries.
    """
    return {
        "low_stock": get_low_stock_alerts(),
        "pending_deliveries": get_pending_deliveries(),
        "delayed_manufacturing": get_delayed_manufacturing_orders(),
        "pending_procurement": get_pending_procurement_requests()
    }


# key, label, module the alert belongs to, HTML url name, tone
ALERT_GROUPS = [
    ("low_stock", "Low stock", "inventory", "inventory:home", "amber"),
    ("pending_deliveries", "Pending deliveries", "delivery", "delivery:list", "blue"),
    ("delayed_manufacturing", "Overdue manufacturing orders", "manufacturing", "manufacturing:mo_list", "red"),
    ("pending_procurement", "Pending procurement requests", "procurement", "procurement:trigger_dashboard", "amber"),
]


def get_alert_summary_for_user(user):
    """
    Non-empty alert groups with counts. ``can_open`` says whether the user's role
    may open the related module (alerts are shown to everyone; links are not).
    """
    from apps.accounts.permissions import can_access_module

    alerts = get_all_alerts()
    items = []
    for key, label, module, url_name, tone in ALERT_GROUPS:
        count = len(alerts.get(key, []))
        if count:
            items.append({
                "key": key, "label": label, "count": count, "tone": tone,
                "module": module, "url_name": url_name,
                "can_open": can_access_module(user, module),
            })
    return {"total": sum(i["count"] for i in items), "items": items}
