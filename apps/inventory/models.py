from django.db import models
from core.models import UUIDBaseModel, TimeStampedModel
from apps.products.models import Product

class LedgerEntryType(models.TextChoices):
    RECEIPT = "RECEIPT", "Receipt (Stock In)"
    ISSUE = "ISSUE", "Issue (Stock Out)"
    RESERVATION = "RESERVATION", "Reservation"
    RELEASE = "RELEASE", "Reservation Release"


class InventoryLedgerEntry(UUIDBaseModel, TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="ledger_entries")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    entry_type = models.CharField(max_length=30, choices=LedgerEntryType.choices)
    reference = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.entry_type} | {self.product.sku} | {self.quantity}"
