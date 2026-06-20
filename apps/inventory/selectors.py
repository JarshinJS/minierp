from django.db.models import Sum

from .models import StockLedger


def _value(filters_data, key):
    if filters_data is None:
        return None
    if hasattr(filters_data, "get"):
        return filters_data.get(key)
    return filters_data[key] if key in filters_data else None


def get_ledger_entries(filters_data=None):
    queryset = StockLedger.objects.select_related("product").all()

    product = _value(filters_data, "product")
    if product:
        queryset = queryset.filter(product_id=product)

    movement_type = _value(filters_data, "movement_type")
    if movement_type:
        queryset = queryset.filter(movement_type=movement_type)

    direction = _value(filters_data, "direction")
    if direction:
        queryset = queryset.filter(direction=direction)

    reference_type = _value(filters_data, "reference_type")
    if reference_type:
        queryset = queryset.filter(reference_type=reference_type)

    reference_id = _value(filters_data, "reference_id")
    if reference_id:
        queryset = queryset.filter(reference_id=reference_id)

    return queryset.order_by("-created_at")


def get_stock_summary(filters_data=None):
    queryset = get_ledger_entries(filters_data)
    summary = queryset.aggregate(total_movement=Sum("quantity"))
    return {
        "total_products": queryset.values("product_id").distinct().count(),
        "ledger_entries": queryset.count(),
        "total_movement": summary["total_movement"] or 0,
    }