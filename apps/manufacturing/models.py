from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import UUIDBaseModel, TimeStampedModel
from apps.products.models import Product


class ManufacturingOrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class BoM(UUIDBaseModel, TimeStampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class ManufacturingOrder(UUIDBaseModel, TimeStampedModel):
    order_number = models.CharField(max_length=100, unique=True, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="manufacturing_orders")
    bom = models.ForeignKey(BoM, on_delete=models.SET_NULL, null=True, blank=True, related_name="manufacturing_orders")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, choices=ManufacturingOrderStatus.choices, default=ManufacturingOrderStatus.DRAFT)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="manufacturing_orders",
    )

    def __str__(self):
        return f"{self.order_number} - {self.product.sku}"
