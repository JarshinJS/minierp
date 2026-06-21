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