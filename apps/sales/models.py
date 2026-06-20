from django.db import models
from django.contrib.auth import get_user_model
from core.models import UUIDBaseModel, TimeStampedModel
from apps.products.models import Product
from apps.audit_logs.mixins import AuditableMixin

User = get_user_model()

class SalesOrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    PARTIALLY_DELIVERED = "PARTIALLY_DELIVERED", "Partially Delivered"
    FULLY_DELIVERED = "FULLY_DELIVERED", "Fully Delivered"
    CANCELLED = "CANCELLED", "Cancelled"


class SalesOrder(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    order_number = models.CharField(max_length=100, unique=True, db_index=True)
    customer_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=30,
        choices=SalesOrderStatus.choices,
        default=SalesOrderStatus.DRAFT
    )
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="sales_orders")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.order_number} - {self.customer_name}"

    @property
    def total_amount(self):
        return sum(line.subtotal for line in self.lines.all())


class SalesOrderLine(UUIDBaseModel, TimeStampedModel):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sales_order_lines")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    delivered_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.sku} | {self.quantity} @ {self.unit_price}"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def pending_delivery_qty(self):
        return self.quantity - self.delivered_qty
