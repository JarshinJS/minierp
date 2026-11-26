"""
selectors.py for the Inventory app.

This module contains the selectors logic for the Inventory functionality.
"""
from django.db.models import Sum
from .models import InventoryLedgerEntry, LedgerEntryType


def _value(filters_data, key):
    if filters_data is None:
        return None
    if hasattr(filters_data, "get"):
        return filters_data.get(key)
    return filters_data[key] if key in filters_data else None


def get_ledger_entries(filters_data=None):
    queryset = InventoryLedgerEntry.objects.select_related("product").all()

    product = _value(filters_data, "product")
    if product:
        queryset = queryset.filter(product_id=product)

    entry_type = _value(filters_data, "entry_type")
    if entry_type:
        queryset = queryset.filter(entry_type=entry_type)

    reference = _value(filters_data, "reference")
    if reference:
        queryset = queryset.filter(reference__icontains=reference)

    return queryset.order_by("-created_at")


def get_stock_summary(filters_data=None):
    queryset = get_ledger_entries(filters_data)
    summary = queryset.aggregate(total_movement=Sum("quantity"))
    return {
        "total_products": queryset.values("product_id").distinct().count(),
        "ledger_entries": queryset.count(),
        "total_movement": summary["total_movement"] or 0,
    }

LOW_STOCK_THRESHOLD = 5


def get_stock_levels(search="", category_id="", stock_filter="", active_only=True):
    """
    Active products annotated with ``avail_qty`` (on hand - reserved) and
    ``cost_value`` (on hand * cost), filtered like the inventory screen.
    ``stock_filter`` is "", "low_stock" or "out_of_stock".
    """
    from django.db.models import DecimalField, ExpressionWrapper, F, Q
    from apps.products.models import Product

    products = Product.objects.select_related("category")
    if active_only:
        products = products.filter(is_active=True)
    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    if category_id:
        products = products.filter(category_id=category_id)

    products = products.annotate(
        avail_qty=ExpressionWrapper(F("on_hand_qty") - F("reserved_qty"), output_field=DecimalField()),
        cost_value=ExpressionWrapper(F("on_hand_qty") * F("cost_price"), output_field=DecimalField()),
    )
    if stock_filter == "low_stock":
        products = products.filter(avail_qty__lte=LOW_STOCK_THRESHOLD, avail_qty__gt=0)
    elif stock_filter == "out_of_stock":
        products = products.filter(avail_qty__lte=0)
    return products.order_by("sku")


def get_inventory_stats():
    """Headline numbers across all active products, computed in the database."""
    from decimal import Decimal
    from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q
    from apps.products.models import Product

    avail = ExpressionWrapper(F("on_hand_qty") - F("reserved_qty"), output_field=DecimalField())
    value = ExpressionWrapper(F("on_hand_qty") * F("cost_price"), output_field=DecimalField())
    stats = Product.objects.filter(is_active=True).annotate(avail=avail, value=value).aggregate(
        total_skus=Count("id"),
        total_items=Sum("on_hand_qty"),
        total_value=Sum("value"),
        out_of_stock=Count("id", filter=Q(avail__lte=0)),
        low_stock=Count("id", filter=Q(avail__gt=0, avail__lte=LOW_STOCK_THRESHOLD)),
    )
    stats["total_items"] = stats["total_items"] or Decimal("0")
    stats["total_value"] = stats["total_value"] or Decimal("0")
    return stats
