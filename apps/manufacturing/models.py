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
