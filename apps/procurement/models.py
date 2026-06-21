"""
models.py for the Procurement app.

This module contains the models logic for the Procurement functionality.
"""
from django.conf import settings
from django.db import models

from core.models import UUIDBaseModel, TimeStampedModel
from apps.products.models import Product

class ProcurementStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED = "COMPLETED", "Completed"


class ProcurementTriggerStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class ProcurementDocumentType(models.TextChoices):
    PURCHASE_ORDER = "purchase_order", "Purchase Order"
    MANUFACTURING_ORDER = "manufacturing_order", "Manufacturing Order"


class ProcurementRequest(UUIDBaseModel, TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="procurement_requests")
    quantity_needed = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=30,
        choices=ProcurementStatus.choices,
        default=ProcurementStatus.PENDING
    )
    reference = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.product.sku} | {self.quantity_needed} | {self.status}"


class ProcurementTrigger(UUIDBaseModel, TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="procurement_triggers")
    quantity_needed = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="procurement_triggers",
    )
    status = models.CharField(max_length=30, choices=ProcurementTriggerStatus.choices, default=ProcurementTriggerStatus.QUEUED)
    document_type = models.CharField(max_length=40, choices=ProcurementDocumentType.choices, blank=True)
    document_id = models.UUIDField(null=True, blank=True)
    document_number = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.product.sku} | {self.quantity_needed} | {self.status}"
