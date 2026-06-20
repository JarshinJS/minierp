from decimal import Decimal
from core.exceptions import DomainError
from .models import Product

def create_product(
    name,
    sku,
    category,
    cost_price,
    selling_price,
    unit_of_measure,
    procure_on_demand=False,
    procurement_type="PURCHASE",
    default_vendor=None,
    default_bom=None,
    is_active=True
):
    """
    Creates a new product in the system.
    Enforces that stock quantities are always initialized to 0.0.
    """
    if not name:
        raise DomainError("Product name cannot be empty.")
    if not sku:
        raise DomainError("Product SKU cannot be empty.")
    if Product.objects.filter(sku=sku).exists():
        raise DomainError(f"A product with SKU '{sku}' already exists.")
        
    cost_price = Decimal(str(cost_price))
    selling_price = Decimal(str(selling_price))
    
    if cost_price < 0:
        raise DomainError("Cost price cannot be negative.")
    if selling_price < 0:
        raise DomainError("Selling price cannot be negative.")

    product = Product.objects.create(
        name=name,
        sku=sku,
        category=category,
        cost_price=cost_price,
        selling_price=selling_price,
        unit_of_measure=unit_of_measure,
        procure_on_demand=procure_on_demand,
        procurement_type=procurement_type,
        default_vendor=default_vendor,
        default_bom=default_bom,
        is_active=is_active,
        on_hand_qty=Decimal("0.0"),  # Read-only stock initialisation
        reserved_qty=Decimal("0.0")
    )
    return product


def update_product(product, **fields):
    """
    Updates an existing product.
    Strictly forbids updating 'on_hand_qty' and 'reserved_qty' stock fields.
    """
    # Enforce read-only constraint on stock levels
    for stock_field in ["on_hand_qty", "reserved_qty"]:
        if stock_field in fields:
            # We raise a DomainError if the caller tries to change it
            # (or we could just silently pop it, but raising an error enforces the rule)
            if Decimal(str(fields[stock_field])) != getattr(product, stock_field):
                raise DomainError(f"Cannot update stock quantity '{stock_field}' via the Product module.")
            fields.pop(stock_field)

    if "sku" in fields:
        new_sku = fields["sku"]
        if not new_sku:
            raise DomainError("Product SKU cannot be empty.")
        if Product.objects.filter(sku=new_sku).exclude(pk=product.pk).exists():
            raise DomainError(f"A product with SKU '{new_sku}' already exists.")

    if "cost_price" in fields:
        fields["cost_price"] = Decimal(str(fields["cost_price"]))
        if fields["cost_price"] < 0:
            raise DomainError("Cost price cannot be negative.")

    if "selling_price" in fields:
        fields["selling_price"] = Decimal(str(fields["selling_price"]))
        if fields["selling_price"] < 0:
            raise DomainError("Selling price cannot be negative.")

    for key, val in fields.items():
        setattr(product, key, val)

    product.save()
    return product


def deactivate_product(product):
    """
    Deactivates a product.
    """
    if not product.is_active:
        raise DomainError("Product is already inactive.")
    product.is_active = False
    product.save()
    return product
