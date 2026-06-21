"""
selectors.py for the Manufacturing app.

This module contains the selectors logic for the Manufacturing functionality.
"""
from decimal import Decimal
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import BoM, WorkCenter


def get_boms(search: str = None, product_id=None, active_only: bool = True):
    """
    Returns a queryset of BOMs with optional filters.

    Args:
        search: Filter by name or reference (case-insensitive).
        product_id: Filter by finished product.
        active_only: If True, only return active BOMs.
    """
    qs = BoM.objects.select_related("product").prefetch_related(
        "components__component",
        "operations__work_center",
    )
    if active_only:
        qs = qs.filter(is_active=True)
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(reference__icontains=search)
        )
    if product_id:
        qs = qs.filter(product_id=product_id)
    return qs.order_by("reference")


def get_bom(pk) -> BoM:
    """Returns a single BOM or raises 404."""
    return get_object_or_404(
        BoM.objects.select_related("product").prefetch_related(
            "components__component",
            "operations__work_center",
        ),
        pk=pk,
    )


def get_work_centers(active_only: bool = True):
    """Returns all work centers."""
    qs = WorkCenter.objects.all()
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.order_by("name")


def get_bom_cost(bom: BoM) -> Decimal:
    """
    Calculates the total material cost for one run of this BOM.
    = sum(component.cost_price × line.quantity) for all component lines.
    """
    total = Decimal("0.00")
    for line in bom.components.select_related("component").all():
        total += line.component.cost_price * line.quantity
    return total


def get_bom_operation_time(bom: BoM) -> Decimal:
    """Returns total estimated operation time in minutes."""
    total = Decimal("0.00")
    for op in bom.operations.all():
        total += op.duration_minutes
    return total


# ===========================================================================
# Manufacturing Order Selectors
# ===========================================================================

from django.db.models import Q  # already imported above, re-used here
from .models import ManufacturingOrder, WorkOrder, MOStatus


def get_manufacturing_orders(search: str = None, status: str = None):
    """Returns filtered MOs with related data prefetched."""
    qs = ManufacturingOrder.objects.select_related("product", "bom").prefetch_related(
        "components__product",
        "work_orders__work_center",
    )
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(reference__icontains=search) | Q(product__name__icontains=search)
        )
    return qs.order_by("-created_at")


def get_manufacturing_order(pk) -> ManufacturingOrder:
    """Returns a single MO or raises 404."""
    from django.shortcuts import get_object_or_404
    return get_object_or_404(
        ManufacturingOrder.objects.select_related("product", "bom").prefetch_related(
            "components__product",
            "work_orders__work_center",
        ),
        pk=pk,
    )


def get_work_orders_for_mo(mo: ManufacturingOrder):
    """Returns all work orders for an MO ordered by sequence."""
    return mo.work_orders.select_related("work_center").order_by("sequence")
