from django.db import models
from core.models import UUIDBaseModel, TimeStampedModel
from apps.products.models import Product

class ProcurementStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED = "COMPLETED", "Completed"


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
