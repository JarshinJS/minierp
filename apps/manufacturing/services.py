from decimal import Decimal

from django.db import transaction

from core.exceptions import DomainError
from apps.audit_logs.services import log_event
from apps.audit_logs.models import AuditLogAction

from .models import BoM, BOMComponent, BOMOperation, WorkCenter


# ===========================================================================
# WorkCenter Services
# ===========================================================================

@transaction.atomic
def create_work_center(name: str, code: str, cost_per_hour=Decimal("0.00")) -> WorkCenter:
    """Creates a new WorkCenter."""
    name = name.strip()
    code = code.strip().upper()
    if not name:
        raise DomainError("Work center name cannot be empty.")
    if not code:
        raise DomainError("Work center code cannot be empty.")
    if WorkCenter.objects.filter(code=code).exists():
        raise DomainError(f"A work center with code '{code}' already exists.")
    if WorkCenter.objects.filter(name=name).exists():
        raise DomainError(f"A work center named '{name}' already exists.")

    wc = WorkCenter.objects.create(
        name=name,
        code=code,
        cost_per_hour=Decimal(str(cost_per_hour)),
    )
    log_event(user=None, module="manufacturing", record=wc, action=AuditLogAction.CREATED)
    return wc


@transaction.atomic
def update_work_center(wc: WorkCenter, **fields) -> WorkCenter:
    """Updates an existing WorkCenter."""
    if "code" in fields:
        new_code = fields["code"].strip().upper()
        fields["code"] = new_code
        if WorkCenter.objects.filter(code=new_code).exclude(pk=wc.pk).exists():
            raise DomainError(f"A work center with code '{new_code}' already exists.")
    if "name" in fields:
        new_name = fields["name"].strip()
        fields["name"] = new_name
        if WorkCenter.objects.filter(name=new_name).exclude(pk=wc.pk).exists():
            raise DomainError(f"A work center named '{new_name}' already exists.")
    if "cost_per_hour" in fields:
        fields["cost_per_hour"] = Decimal(str(fields["cost_per_hour"]))
        if fields["cost_per_hour"] < 0:
            raise DomainError("Cost per hour cannot be negative.")

    for key, val in fields.items():
        setattr(wc, key, val)
    wc.save()
    log_event(user=None, module="manufacturing", record=wc, action=AuditLogAction.UPDATED)
    return wc


# ===========================================================================
# BOM Services
# ===========================================================================

def _validate_components(components: list):
    """Validate a list of component dicts."""
    from apps.products.models import Product
    validated = []
    for i, row in enumerate(components):
        try:
            product_id = row["component_id"]
            product = Product.objects.get(pk=product_id)
        except (KeyError, Product.DoesNotExist):
            raise DomainError(f"Component row {i+1}: invalid product ID.")
        try:
            qty = Decimal(str(row.get("quantity", 1)))
        except Exception:
            raise DomainError(f"Component row {i+1}: invalid quantity.")
        if qty <= 0:
            raise DomainError(f"Component row {i+1}: quantity must be positive.")
        uom = str(row.get("uom", product.unit_of_measure)).upper()
        seq = int(row.get("sequence", (i + 1) * 10))
        validated.append({"product": product, "quantity": qty, "uom": uom, "sequence": seq})
    return validated


def _validate_operations(operations: list):
    """Validate a list of operation dicts."""
    validated = []
    for i, row in enumerate(operations):
        try:
            wc = WorkCenter.objects.get(pk=row["work_center_id"])
        except (KeyError, WorkCenter.DoesNotExist):
            raise DomainError(f"Operation row {i+1}: invalid work center ID.")
        name = str(row.get("name", "")).strip()
        if not name:
            raise DomainError(f"Operation row {i+1}: name cannot be empty.")
        try:
            duration = Decimal(str(row.get("duration_minutes", 0)))
        except Exception:
            raise DomainError(f"Operation row {i+1}: invalid duration.")
        if duration < 0:
            raise DomainError(f"Operation row {i+1}: duration cannot be negative.")
        seq = int(row.get("sequence", (i + 1) * 10))
        validated.append({"work_center": wc, "name": name, "duration_minutes": duration, "sequence": seq})
    return validated


@transaction.atomic
def create_bom(
    name: str,
    reference: str,
    product=None,
    product_qty=Decimal("1.00"),
    notes: str = "",
    components: list = None,
    operations: list = None,
) -> BoM:
    """
    Creates a new Bill of Materials with its component lines and operations.

    Args:
        name: Human-readable BOM name.
        reference: Unique BOM code (e.g. BOM-001).
        product: Finished product FK (optional for template BOMs).
        product_qty: Quantity of finished product produced.
        notes: Free-text notes.
        components: List of dicts [{component_id, quantity, uom, sequence}, ...]
        operations: List of dicts [{work_center_id, name, duration_minutes, sequence}, ...]
    """
    name = name.strip()
    reference = reference.strip().upper()
    if not name:
        raise DomainError("BOM name cannot be empty.")
    if not reference:
        raise DomainError("BOM reference cannot be empty.")
    if BoM.objects.filter(reference=reference).exists():
        raise DomainError(f"A BOM with reference '{reference}' already exists.")

    product_qty = Decimal(str(product_qty))
    if product_qty <= 0:
        raise DomainError("Product quantity must be positive.")

    validated_components = _validate_components(components or [])
    validated_operations = _validate_operations(operations or [])

    bom = BoM.objects.create(
        name=name,
        reference=reference,
        product=product,
        product_qty=product_qty,
        notes=notes,
        is_active=True,
    )

    for comp in validated_components:
        BOMComponent.objects.create(
            bom=bom,
            component=comp["product"],
            quantity=comp["quantity"],
            uom=comp["uom"],
            sequence=comp["sequence"],
        )

    for op in validated_operations:
        BOMOperation.objects.create(
            bom=bom,
            work_center=op["work_center"],
            name=op["name"],
            duration_minutes=op["duration_minutes"],
            sequence=op["sequence"],
        )

    log_event(user=None, module="manufacturing", record=bom, action=AuditLogAction.CREATED)
    return bom


@transaction.atomic
def update_bom(
    bom: BoM,
    name: str = None,
    product=None,
    product_qty=None,
    notes: str = None,
    components: list = None,
    operations: list = None,
) -> BoM:
    """
    Updates an existing BOM header, and replaces all components/operations
    if those lists are provided.
    """
    if name is not None:
        name = name.strip()
        if not name:
            raise DomainError("BOM name cannot be empty.")
        bom.name = name

    if product is not None:
        bom.product = product

    if product_qty is not None:
        product_qty = Decimal(str(product_qty))
        if product_qty <= 0:
            raise DomainError("Product quantity must be positive.")
        bom.product_qty = product_qty

    if notes is not None:
        bom.notes = notes

    bom.save()

    # Replace components atomically
    if components is not None:
        validated_components = _validate_components(components)
        bom.components.all().delete()
        for comp in validated_components:
            BOMComponent.objects.create(
                bom=bom,
                component=comp["product"],
                quantity=comp["quantity"],
                uom=comp["uom"],
                sequence=comp["sequence"],
            )

    # Replace operations atomically
    if operations is not None:
        validated_operations = _validate_operations(operations)
        bom.operations.all().delete()
        for op in validated_operations:
            BOMOperation.objects.create(
                bom=bom,
                work_center=op["work_center"],
                name=op["name"],
                duration_minutes=op["duration_minutes"],
                sequence=op["sequence"],
            )

    log_event(user=None, module="manufacturing", record=bom, action=AuditLogAction.UPDATED)
    return bom


@transaction.atomic
def deactivate_bom(bom: BoM) -> BoM:
    """Deactivates a BOM so it can no longer be used for manufacturing orders."""
    if not bom.is_active:
        raise DomainError("BOM is already inactive.")
    bom.is_active = False
    bom.save()
    log_event(
        user=None, module="manufacturing", record=bom,
        action=AuditLogAction.STATUS_CHANGED,
        field="is_active", old=True, new=False,
    )
    return bom
