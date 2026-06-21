"""
services.py for the Manufacturing app.

This module contains the services logic for the Manufacturing functionality.
"""
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


# ===========================================================================
# Manufacturing Order Services
# ===========================================================================

from .models import ManufacturingOrder, MOComponent, WorkOrder, MOStatus, WorkOrderStatus  # noqa: E402


def _next_mo_reference() -> str:
    """Generate the next sequential MO reference (MO-0001, MO-0002, …)."""
    last = (
        ManufacturingOrder.objects
        .filter(reference__startswith="MO-")
        .order_by("-reference")
        .values_list("reference", flat=True)
        .first()
    )
    if last:
        try:
            num = int(last.split("-")[1]) + 1
        except (IndexError, ValueError):
            num = 1
    else:
        num = 1
    return f"MO-{num:04d}"


@transaction.atomic
def create_mo(
    product,
    qty_to_produce,
    bom=None,
    scheduled_date=None,
    notes: str = "",
) -> ManufacturingOrder:
    """
    Creates a new Manufacturing Order in DRAFT status.

    Args:
        product: Finished product to manufacture.
        qty_to_produce: How many units to make.
        bom: Optional source BOM (components/operations copied at confirmation).
        scheduled_date: Target production date.
        notes: Free-text notes.
    """
    from decimal import Decimal as _D
    qty_to_produce = _D(str(qty_to_produce))
    if qty_to_produce <= 0:
        raise DomainError("Quantity to produce must be positive.")
    if not product.is_active:
        raise DomainError("Cannot create an MO for an inactive product.")

    mo = ManufacturingOrder.objects.create(
        reference=_next_mo_reference(),
        bom=bom,
        product=product,
        qty_to_produce=qty_to_produce,
        scheduled_date=scheduled_date,
        notes=notes,
        status=MOStatus.DRAFT,
    )
    log_event(user=None, module="manufacturing", record=mo, action=AuditLogAction.CREATED)
    return mo


@transaction.atomic
def confirm_mo(mo: ManufacturingOrder) -> ManufacturingOrder:
    """
    Confirms a DRAFT MO:
    - Validates status transition.
    - Copies BOM components (scaled to qty_to_produce) → MOComponent rows.
    - Copies BOM operations → WorkOrder rows.
    - Transitions status to CONFIRMED.
    """
    if mo.status != MOStatus.DRAFT:
        raise DomainError(f"Cannot confirm an MO that is already {mo.get_status_display()}.")

    # Copy BOM components → MOComponent (scaled)
    if mo.bom:
        scale = mo.qty_to_produce / mo.bom.product_qty
        for bom_comp in mo.bom.components.select_related("component").order_by("sequence"):
            MOComponent.objects.create(
                mo=mo,
                product=bom_comp.component,
                qty_required=(bom_comp.quantity * scale).quantize(
                    bom_comp.quantity.__class__("0.0001")
                ),
                uom=bom_comp.uom,
                sequence=bom_comp.sequence,
            )
        # Copy BOM operations → WorkOrder
        for bom_op in mo.bom.operations.select_related("work_center").order_by("sequence"):
            WorkOrder.objects.create(
                mo=mo,
                work_center=bom_op.work_center,
                name=bom_op.name,
                sequence=bom_op.sequence,
                duration_expected=bom_op.duration_minutes,
                status=WorkOrderStatus.PENDING,
            )

    mo.status = MOStatus.CONFIRMED
    mo.save(update_fields=["status", "updated_at"])
    log_event(
        user=None, module="manufacturing", record=mo,
        action=AuditLogAction.STATUS_CHANGED,
        field="status", old=MOStatus.DRAFT, new=MOStatus.CONFIRMED,
    )
    return mo


@transaction.atomic
def start_mo(mo: ManufacturingOrder) -> ManufacturingOrder:
    """
    Moves a CONFIRMED MO to IN_PROGRESS.
    The first pending WorkOrder (if any) is also started.
    """
    if mo.status != MOStatus.CONFIRMED:
        raise DomainError(f"Can only start a Confirmed MO (current: {mo.get_status_display()}).")

    mo.status = MOStatus.IN_PROGRESS
    mo.save(update_fields=["status", "updated_at"])

    # Auto-start the first pending work order
    first_wo = mo.work_orders.filter(status=WorkOrderStatus.PENDING).order_by("sequence").first()
    if first_wo:
        first_wo.status = WorkOrderStatus.IN_PROGRESS
        first_wo.save(update_fields=["status", "updated_at"])

    log_event(
        user=None, module="manufacturing", record=mo,
        action=AuditLogAction.STATUS_CHANGED,
        field="status", old=MOStatus.CONFIRMED, new=MOStatus.IN_PROGRESS,
    )
    return mo


@transaction.atomic
def produce_mo(mo: ManufacturingOrder, qty_produced) -> ManufacturingOrder:
    """
    Records production for an IN_PROGRESS MO:
    1. Validates qty_produced ≤ remaining qty.
    2. Issues raw materials from inventory (ISSUE ledger entries).
    3. Receives finished goods into inventory (RECEIPT ledger entry).
    4. Updates MOComponent.qty_consumed.
    5. If fully produced → marks MO as DONE.
    """
    from decimal import Decimal as _D
    from apps.inventory.services import post_ledger_entry
    from apps.inventory.models import LedgerEntryType

    if mo.status != MOStatus.IN_PROGRESS:
        raise DomainError(f"Can only produce against an In Progress MO (current: {mo.get_status_display()}).")

    qty_produced = _D(str(qty_produced))
    if qty_produced <= 0:
        raise DomainError("Quantity to produce must be positive.")

    remaining = mo.qty_to_produce - mo.qty_produced
    if qty_produced > remaining:
        raise DomainError(
            f"Cannot produce {qty_produced}; only {remaining} remaining on MO {mo.reference}."
        )

    # Ratio of this partial production vs total BOM run
    ratio = qty_produced / mo.qty_to_produce

    # 1. Issue raw materials from inventory + update qty_consumed
    for comp in mo.components.select_related("product").all():
        consume_qty = (comp.qty_required * ratio).quantize(_D("0.0001"))
        if consume_qty > 0:
            post_ledger_entry(
                product=comp.product,
                entry_type=LedgerEntryType.ISSUE,
                quantity=consume_qty,
                reference=f"MO: {mo.reference}",
            )
            comp.qty_consumed = (comp.qty_consumed + consume_qty).quantize(_D("0.0001"))
            comp.save(update_fields=["qty_consumed", "updated_at"])

    # 2. Receive finished goods into inventory
    post_ledger_entry(
        product=mo.product,
        entry_type=LedgerEntryType.RECEIPT,
        quantity=qty_produced,
        reference=f"MO: {mo.reference}",
    )

    # 3. Update MO progress
    mo.qty_produced = mo.qty_produced + qty_produced
    if mo.qty_produced >= mo.qty_to_produce:
        mo.status = MOStatus.DONE
        # Mark all pending/in-progress work orders as done
        mo.work_orders.exclude(status=WorkOrderStatus.DONE).update(status=WorkOrderStatus.DONE)

    mo.save(update_fields=["qty_produced", "status", "updated_at"])
    log_event(
        user=None, module="manufacturing", record=mo,
        action=AuditLogAction.STOCK_ADJUSTED,
        field="qty_produced", old=mo.qty_produced - qty_produced, new=mo.qty_produced,
    )
    return mo


@transaction.atomic
def cancel_mo(mo: ManufacturingOrder) -> ManufacturingOrder:
    """
    Cancels a DRAFT or CONFIRMED MO.
    IN_PROGRESS MOs cannot be cancelled (must be produced or manually reversed).
    """
    if mo.status in (MOStatus.DONE, MOStatus.CANCELLED):
        raise DomainError(f"MO is already {mo.get_status_display()} and cannot be cancelled.")
    if mo.status == MOStatus.IN_PROGRESS:
        raise DomainError("Cannot cancel an In Progress MO. Produce remaining qty or contact admin.")

    mo.status = MOStatus.CANCELLED
    mo.save(update_fields=["status", "updated_at"])
    log_event(
        user=None, module="manufacturing", record=mo,
        action=AuditLogAction.STATUS_CHANGED,
        field="status", old=mo.status, new=MOStatus.CANCELLED,
    )
    return mo


@transaction.atomic
def start_work_order(wo: WorkOrder) -> WorkOrder:
    """Moves a PENDING WorkOrder to IN_PROGRESS."""
    if wo.status != WorkOrderStatus.PENDING:
        raise DomainError(f"Work order is already {wo.get_status_display()}.")
    if wo.mo.status not in (MOStatus.CONFIRMED, MOStatus.IN_PROGRESS):
        raise DomainError("Parent Manufacturing Order must be Confirmed or In Progress.")

    wo.status = WorkOrderStatus.IN_PROGRESS
    wo.save(update_fields=["status", "updated_at"])
    return wo


@transaction.atomic
def complete_work_order(wo: WorkOrder, duration_actual=None) -> WorkOrder:
    """
    Marks a WorkOrder as DONE.
    Optionally records the actual duration in minutes.
    """
    if wo.status != WorkOrderStatus.IN_PROGRESS:
        raise DomainError(f"Work order must be In Progress to complete (current: {wo.get_status_display()}).")

    from decimal import Decimal as _D
    wo.status = WorkOrderStatus.DONE
    if duration_actual is not None:
        dur = _D(str(duration_actual))
        if dur < 0:
            raise DomainError("Actual duration cannot be negative.")
        wo.duration_actual = dur
    wo.save(update_fields=["status", "duration_actual", "updated_at"])

    # Auto-start next pending work order on the same MO
    next_wo = (
        wo.mo.work_orders
        .filter(status=WorkOrderStatus.PENDING)
        .order_by("sequence")
        .first()
    )
    if next_wo:
        next_wo.status = WorkOrderStatus.IN_PROGRESS
        next_wo.save(update_fields=["status", "updated_at"])

    return wo
