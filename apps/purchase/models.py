from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models

from apps.audit_logs.mixins import AuditableMixin
from core.models import UUIDBaseModel, TimeStampedModel

User = get_user_model()


class Vendor(UUIDBaseModel, TimeStampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CONFIRMED = "confirmed", "Confirmed"
    PARTIALLY_RECEIVED = "partially_received", "Partially Received"
    FULLY_RECEIVED = "fully_received", "Fully Received"
    CANCELLED = "cancelled", "Cancelled"


class PurchaseOrder(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    order_number = models.CharField(max_length=100, unique=True, db_index=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=30, choices=PurchaseOrderStatus.choices, default=PurchaseOrderStatus.DRAFT)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="purchase_orders")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.order_number} - {self.vendor.name}"

    @property
    def total_amount(self):
        return sum((line.subtotal for line in self.lines.all()), Decimal("0.00"))


class PurchaseOrderLine(UUIDBaseModel, TimeStampedModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="purchase_order_lines")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    received_qty = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.0"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.sku} | {self.quantity} @ {self.unit_price}"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def pending_receive_qty(self):
        return self.quantity - self.received_qty
