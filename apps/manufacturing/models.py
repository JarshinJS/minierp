from decimal import Decimal
from django.db import models

from core.models import UUIDBaseModel, TimeStampedModel
from apps.audit_logs.mixins import AuditableMixin


# ---------------------------------------------------------------------------
# WorkCenter
# ---------------------------------------------------------------------------

class WorkCenter(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    """
    Represents a physical or virtual production station (e.g. CNC, Assembly Bay).
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    cost_per_hour = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ---------------------------------------------------------------------------
# Bill of Materials (BOM)  — replaces the stub BoM model
# NOTE: Class kept as "BoM" so that the existing FK in products.Product
#       (default_bom = FK("manufacturing.BoM")) resolves without a data migration.
# ---------------------------------------------------------------------------

class BoM(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    """
    Top-level Bill of Materials header. Linked to the finished product it produces.
    """
    name = models.CharField(max_length=255)
    reference = models.CharField(max_length=50, unique=True, db_index=True, help_text="e.g. BOM-001")

    # The product this BOM produces
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="boms",
        null=True,
        blank=True,
        help_text="The finished product this BOM produces. Leave blank for templates."
    )
    product_qty = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("1.00"),
        help_text="Quantity of finished product produced by one run of this BOM."
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["reference"]
        verbose_name = "Bill of Materials"
        verbose_name_plural = "Bills of Materials"

    def __str__(self):
        return f"{self.reference} — {self.name}"

    @property
    def total_material_cost(self):
        """Sum of (component.cost_price × qty) for all BOMComponents."""
        total = Decimal("0.00")
        for line in self.components.select_related("component"):
            total += line.component.cost_price * line.quantity
        return total


# ---------------------------------------------------------------------------
# BOM Component line items
# ---------------------------------------------------------------------------

class BOMComponent(UUIDBaseModel, TimeStampedModel):
    """
    A single raw material or sub-assembly consumed by a BOM.
    """
    bom = models.ForeignKey(BoM, on_delete=models.CASCADE, related_name="components")
    component = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="used_in_boms",
        help_text="Raw material or sub-assembly consumed."
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("1.0000"))
    uom = models.CharField(
        max_length=20,
        help_text="Unit of Measure (copied from component default, can be overridden)."
    )
    sequence = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.bom.reference} → {self.component.sku} × {self.quantity}"


# ---------------------------------------------------------------------------
# BOM Operation (routing step)
# ---------------------------------------------------------------------------

class BOMOperation(UUIDBaseModel, TimeStampedModel):
    """
    A work operation performed as part of a BOM (defines the manufacturing routing).
    """
    bom = models.ForeignKey(BoM, on_delete=models.CASCADE, related_name="operations")
    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.PROTECT,
        related_name="operations"
    )
    name = models.CharField(max_length=255, help_text="e.g. 'Cut wood panels', 'Sand & finish'")
    duration_minutes = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"),
        help_text="Expected duration in minutes."
    )
    sequence = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.bom.reference} | Op{self.sequence}: {self.name}"


# ---------------------------------------------------------------------------
# Manufacturing Order status choices
# ---------------------------------------------------------------------------

class MOStatus(models.TextChoices):
    DRAFT       = "DRAFT",       "Draft"
    CONFIRMED   = "CONFIRMED",   "Confirmed"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    DONE        = "DONE",        "Done"
    CANCELLED   = "CANCELLED",   "Cancelled"


class WorkOrderStatus(models.TextChoices):
    PENDING     = "PENDING",     "Pending"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    DONE        = "DONE",        "Done"


# ---------------------------------------------------------------------------
# Manufacturing Order (MO)
# ---------------------------------------------------------------------------

class ManufacturingOrder(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    """
    A production order instructing the factory to produce a quantity of a
    finished product from a Bill of Materials.

    Lifecycle: DRAFT → CONFIRMED → IN_PROGRESS → DONE
                                ↘ CANCELLED
    """
    reference = models.CharField(
        max_length=50, unique=True, db_index=True,
        help_text="e.g. MO-0001 — auto-generated on save."
    )
    bom = models.ForeignKey(
        BoM,
        on_delete=models.PROTECT,
        related_name="manufacturing_orders",
        null=True, blank=True,
        help_text="Source BOM. Components & operations are copied at confirmation."
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="manufacturing_orders",
        help_text="The finished product to manufacture."
    )
    qty_to_produce = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Number of finished units to produce."
    )
    qty_produced = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Units actually produced so far."
    )
    status = models.CharField(
        max_length=20, choices=MOStatus.choices, default=MOStatus.DRAFT, db_index=True
    )
    scheduled_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Manufacturing Order"
        verbose_name_plural = "Manufacturing Orders"

    def __str__(self):
        return f"{self.reference} — {self.product.name} × {self.qty_to_produce}"

    @property
    def is_editable(self):
        return self.status == MOStatus.DRAFT

    @property
    def progress_pct(self):
        if not self.qty_to_produce:
            return 0
        return min(100, int((self.qty_produced / self.qty_to_produce) * 100))


# ---------------------------------------------------------------------------
# MO Component lines (copied from BOM at confirmation)
# ---------------------------------------------------------------------------

class MOComponent(UUIDBaseModel, TimeStampedModel):
    """
    A component line on a Manufacturing Order.
    Copied from BOMComponent at MO confirmation; qty_consumed updated at production.
    """
    mo = models.ForeignKey(
        ManufacturingOrder, on_delete=models.CASCADE, related_name="components"
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="mo_components",
        help_text="Raw material / sub-assembly to consume."
    )
    qty_required = models.DecimalField(
        max_digits=12, decimal_places=4,
        help_text="Total required (scaled to MO qty_to_produce)."
    )
    qty_consumed = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal("0.0000"),
        help_text="Quantity actually consumed (set at produce step)."
    )
    uom = models.CharField(max_length=20)
    sequence = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.mo.reference} ← {self.product.sku} × {self.qty_required}"


# ---------------------------------------------------------------------------
# Work Order (per-MO routing step, copied from BOM operations)
# ---------------------------------------------------------------------------

class WorkOrder(UUIDBaseModel, TimeStampedModel):
    """
    A single work operation step on a Manufacturing Order, mapped to a WorkCenter.
    Copied from BOMOperation at MO confirmation.
    """
    mo = models.ForeignKey(
        ManufacturingOrder, on_delete=models.CASCADE, related_name="work_orders"
    )
    work_center = models.ForeignKey(
        WorkCenter, on_delete=models.PROTECT, related_name="work_orders"
    )
    name = models.CharField(max_length=255)
    sequence = models.PositiveIntegerField(default=10)
    duration_expected = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"),
        help_text="Expected duration in minutes (copied from BOM operation)."
    )
    duration_actual = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Actual time taken in minutes (filled at completion)."
    )
    status = models.CharField(
        max_length=20, choices=WorkOrderStatus.choices,
        default=WorkOrderStatus.PENDING, db_index=True
    )

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.mo.reference} | WO{self.sequence}: {self.name} [{self.status}]"
