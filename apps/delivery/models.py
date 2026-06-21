"""
models.py for the Delivery app.

This module contains the models logic for the Delivery functionality.
"""
from django.db import models
from django.contrib.auth import get_user_model
from core.models import UUIDBaseModel, TimeStampedModel
from apps.sales.models import SalesOrder, SalesOrderLine
from apps.audit_logs.mixins import AuditableMixin

User = get_user_model()

class DeliveryNoteStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    DISPATCHED = "DISPATCHED", "Dispatched"
    DELIVERED = "DELIVERED", "Delivered"


class DeliveryNote(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    delivery_number = models.CharField(max_length=100, unique=True, db_index=True)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="delivery_notes")
    status = models.CharField(
        max_length=30,
        choices=DeliveryNoteStatus.choices,
        default=DeliveryNoteStatus.PENDING
    )
    dispatch_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="delivery_notes_created")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.delivery_number} ({self.status}) for {self.sales_order.order_number}"


class DeliveryNoteLine(UUIDBaseModel, TimeStampedModel):
    delivery_note = models.ForeignKey(DeliveryNote, on_delete=models.CASCADE, related_name="lines")
    sales_order_line = models.ForeignKey(SalesOrderLine, on_delete=models.CASCADE, related_name="delivery_lines")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.sales_order_line.product.sku} | Qty: {self.quantity}"
