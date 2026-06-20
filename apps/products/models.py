from decimal import Decimal
from django.db import models

from core.models import UUIDBaseModel, TimeStampedModel
from apps.purchase.models import Vendor
from apps.audit_logs.mixins import AuditableMixin

class UnitOfMeasure(models.TextChoices):
    PCS = "PCS", "Pieces"
    KG = "KG", "Kilograms"
    METER = "M", "Meters"
    BOX = "BOX", "Boxes"


class ProcurementType(models.TextChoices):
    PURCHASE = "PURCHASE", "Purchase"
    MANUFACTURING = "MANUFACTURING", "Manufacturing"


class Category(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    unit_of_measure = models.CharField(
        max_length=20,
        choices=UnitOfMeasure.choices,
        default=UnitOfMeasure.PCS
    )
    
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Read-only fields for product forms/services. Only inventory module can update these.
    on_hand_qty = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.0"))
    reserved_qty = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.0"))
    
    procure_on_demand = models.BooleanField(default=False)
    procurement_type = models.CharField(
        max_length=20,
        choices=ProcurementType.choices,
        default=ProcurementType.PURCHASE
    )
    
    default_vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_products"
    )
    default_bom = models.ForeignKey(
        "manufacturing.BoM",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_products"
    )
    
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def available_qty(self):
        return self.on_hand_qty - self.reserved_qty
