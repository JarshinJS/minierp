from django.db.models import Q
from .models import Product

def get_products(search_query=None, category_id=None, is_active=None):
    """
    Retrieves and filters products based on search parameters, category, and status.
    """
    queryset = Product.objects.all().select_related("category", "default_vendor", "default_bom")

    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)

    if category_id:
        queryset = queryset.filter(category_id=category_id)

    if search_query:
        queryset = queryset.filter(
            Q(name__icontains=search_query) |
            Q(sku__icontains=search_query)
        )

    return queryset.order_by("name")


def get_product_stock(product):
    """
    Returns a structured dictionary of the stock levels for a product.
    """
    return {
        "product_id": product.id,
        "product_name": product.name,
        "sku": product.sku,
        "on_hand": product.on_hand_qty,
        "reserved": product.reserved_qty,
        "available": product.available_qty,
    }
